from __future__ import annotations

import asyncio
import io
import math
import time
from collections import OrderedDict
from collections.abc import Buffer, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any, Literal
from urllib.parse import unquote, urlsplit
from uuid import UUID, uuid4

import httpx2
import numpy as np
import rasterio
from rasterio.env import Env
from rio_tiler.io import Reader
from rio_tiler.utils import render

from satquery.api.schemas.asset_resolution import AssetResolutionRequest
from satquery.api.schemas.viewer import (
    TileAccess,
    TileMetadata,
    TileMetadataRequest,
    ViewerBounds,
)
from satquery.providers.catalog import (
    CatalogueProvider,
    CatalogueProviderError,
    ResolvedImagerySourceSet,
    ResolvedRasterSource,
)

_ALLOWED_RASTER_HOST = "e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com"
_ALLOWED_RASTER_PREFIX = "/sentinel-2-c1-l2a/"
_RANGE_BLOCK_SIZE = 1024 * 1024
_RANGE_CACHE_MAX_BYTES = 8 * 1024 * 1024
_RANGE_REQUEST_MAX_COUNT = 192
_RANGE_REQUEST_MAX_BYTES = 32 * 1024 * 1024
_RENDER_IO_DEADLINE_SECONDS = 28.0
_NATURAL_COLOR_REFLECTANCE_MAX = 0.30
_RENDER_PRESET_ROLES: dict[str, tuple[str, ...]] = {
    "natural-color": ("red", "green", "blue"),
}
_GDAL_OPTIONS: dict[str, str | int] = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "CPL_VSIL_CURL_USE_S3_REDIRECT": "NO",
    "GDAL_HTTP_CONNECTTIMEOUT": "5",
    "GDAL_HTTP_TIMEOUT": "12",
    "GDAL_HTTP_MAX_RETRY": "0",
    "GDAL_HTTP_PROXY": "",
    "GDAL_CACHEMAX": 32,
    "VSI_CACHE": "FALSE",
    "CPL_VSIL_CURL_CACHE_SIZE": "5242880",
}


class TileServiceError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class RenderedTile:
    body: bytes
    media_type: Literal["image/png"] = "image/png"


@dataclass(frozen=True, slots=True)
class _TileSetEntry:
    metadata: TileMetadata
    source_set: ResolvedImagerySourceSet
    access_scope: str
    cache_key: str
    expires_monotonic: float


TileRenderer = Callable[
    [tuple[ResolvedRasterSource, ...], int, int, int, int],
    bytes,
]


@dataclass(slots=True)
class _RangeBudget:
    deadline: float
    request_count: int = 0
    downloaded_bytes: int = 0

    def reserve(self, size: int) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("raster range-read deadline exceeded")
        if self.request_count >= _RANGE_REQUEST_MAX_COUNT:
            raise OSError("raster range-read request limit exceeded")
        if self.downloaded_bytes + size > _RANGE_REQUEST_MAX_BYTES:
            raise OSError("raster range-read byte limit exceeded")
        self.request_count += 1
        return min(remaining, 5.0)

    def record(self, size: int) -> None:
        self.downloaded_bytes += size


class _HttpRangeReader(io.RawIOBase):
    """Small seekable HTTP range adapter for Rasterio's Python VSI opener."""

    def __init__(self, location: str, size: int, budget: _RangeBudget) -> None:
        super().__init__()
        _validate_source_location(location)
        if size <= 0:
            raise OSError("resolved raster size is unavailable")
        self._location = location
        self._size = size
        self._position = 0
        self._budget = budget
        self._client = httpx2.Client(follow_redirects=False, trust_env=False)
        self._blocks: OrderedDict[int, bytes] = OrderedDict()
        self._cached_bytes = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            position = offset
        elif whence == io.SEEK_CUR:
            position = self._position + offset
        elif whence == io.SEEK_END:
            position = self._size + offset
        else:
            raise ValueError("unsupported seek origin")
        if position < 0:
            raise ValueError("negative seek position")
        self._position = min(position, self._size)
        return self._position

    def read(self, size: int = -1) -> bytes:
        if self.closed:
            raise ValueError("read from closed raster source")
        if self._position >= self._size or size == 0:
            return b""
        requested = (
            self._size - self._position if size < 0 else min(size, self._size - self._position)
        )
        if requested > _RANGE_REQUEST_MAX_BYTES:
            raise OSError("unbounded raster read rejected")
        start = self._position
        end = start + requested
        chunks: list[bytes] = []
        while start < end:
            block_start = start // _RANGE_BLOCK_SIZE * _RANGE_BLOCK_SIZE
            block = self._block(block_start)
            within = start - block_start
            take = min(len(block) - within, end - start)
            if take <= 0:
                raise OSError("provider returned a truncated raster range")
            chunks.append(block[within : within + take])
            start += take
        body = b"".join(chunks)
        self._position += len(body)
        return body

    def readinto(self, buffer: Buffer) -> int:
        view = memoryview(buffer)
        body = self.read(len(view))
        view[: len(body)] = body
        return len(body)

    def close(self) -> None:
        if not self.closed:
            self._client.close()
            self._blocks.clear()
            self._cached_bytes = 0
        super().close()

    def _block(self, start: int) -> bytes:
        cached = self._blocks.get(start)
        if cached is not None:
            self._blocks.move_to_end(start)
            return cached
        end = min(start + _RANGE_BLOCK_SIZE, self._size) - 1
        timeout = self._budget.reserve(end - start + 1)
        response = self._client.get(
            self._location,
            headers={
                "Accept": "image/tiff",
                "Accept-Encoding": "identity",
                "Range": f"bytes={start}-{end}",
            },
            timeout=timeout,
        )
        if response.status_code != 206:
            raise OSError("provider did not honor the bounded raster range request")
        expected_range = f"bytes {start}-{end}/{self._size}"
        if response.headers.get("content-range") != expected_range:
            raise OSError("provider returned an invalid raster content range")
        body = response.content
        if len(body) != end - start + 1:
            raise OSError("provider returned an incomplete raster range")
        self._budget.record(len(body))
        self._blocks[start] = body
        self._cached_bytes += len(body)
        while self._cached_bytes > _RANGE_CACHE_MAX_BYTES:
            _old_start, old_body = self._blocks.popitem(last=False)
            self._cached_bytes -= len(old_body)
        return body


class ImageryTileService:
    """Stable-identity facade over bounded rio-tiler COG reads."""

    def __init__(
        self,
        provider: CatalogueProvider,
        *,
        api_prefix: str = "/api/v1",
        max_zoom: int = 16,
        request_timeout_seconds: float = 30.0,
        max_concurrency: int = 2,
        tile_set_ttl_seconds: int = 300,
        tile_set_cache_max_entries: int = 32,
        tile_byte_cache_max_bytes: int = 16 * 1024 * 1024,
        renderer: TileRenderer | None = None,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._provider = provider
        self._api_prefix = api_prefix
        self._max_zoom = max_zoom
        self._timeout = request_timeout_seconds
        self._ttl = tile_set_ttl_seconds
        self._set_limit = tile_set_cache_max_entries
        self._byte_limit = tile_byte_cache_max_bytes
        self._clock = clock
        self._now = now or (lambda: datetime.now(UTC))
        self._renderer = renderer or _render_natural_color
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrency,
            thread_name_prefix="satquery-imagery-tile",
        )
        self._slots = asyncio.Semaphore(max_concurrency)
        self._sets_by_id: OrderedDict[UUID, _TileSetEntry] = OrderedDict()
        self._set_id_by_key: dict[str, UUID] = {}
        self._tiles: OrderedDict[tuple[str, UUID, int, int, int], bytes] = OrderedDict()
        self._tile_bytes = 0

    async def aclose(self) -> None:
        await asyncio.to_thread(self._executor.shutdown, wait=True, cancel_futures=True)

    async def metadata(self, request: TileMetadataRequest, *, access_scope: str) -> TileMetadata:
        cache_key = (
            f"{access_scope}:{request.scene.provider}:{request.scene.collection}:"
            f"{request.scene.item}:{request.render_preset}:{request.tile_size}"
        )
        cached = self._cached_set(cache_key)
        if cached is not None:
            return cached.metadata

        try:
            source_set = await self._provider.resolve_imagery_sources(
                AssetResolutionRequest(scene=request.scene)
            )
        except CatalogueProviderError:
            raise
        resolution = source_set.resolution
        if resolution.status.state != "supported" or resolution.resolved_asset is None:
            status_code = 403 if resolution.status.state == "access_credentials_required" else 422
            raise TileServiceError(
                "IMAGERY_ACCESS_DENIED" if status_code == 403 else "IMAGERY_NOT_RENDERABLE",
                resolution.status.reason or "The selected scene is not renderable.",
                status_code=status_code,
            )
        if len(source_set.sources) != 3 or tuple(
            source.component for source in source_set.sources
        ) != tuple(resolution.components):
            raise TileServiceError(
                "UPSTREAM_INVALID_RESPONSE",
                "The asset resolver did not return the required RGB sources.",
                status_code=502,
            )
        expected_roles = _RENDER_PRESET_ROLES[request.render_preset]
        if tuple(
            source.component.render_role for source in source_set.sources
        ) != expected_roles or not any(
            preset.id == request.render_preset
            and tuple(preset.bands)
            == tuple(source.component.identity.asset for source in source_set.sources)
            for preset in resolution.resolved_asset.render_presets
        ):
            raise TileServiceError(
                "UPSTREAM_INVALID_RESPONSE",
                "The resolved assets do not match the approved rendering preset.",
                status_code=502,
            )
        for source in source_set.sources:
            _validate_source_location(source.location)

        tile_set_id = uuid4()
        current_time = self._now()
        expires_at = min(
            [
                current_time + timedelta(seconds=self._ttl),
                *[
                    source.expires_at
                    for source in source_set.sources
                    if source.expires_at is not None
                ],
            ]
        )
        effective_ttl = (expires_at - current_time).total_seconds()
        if effective_ttl <= 0:
            raise TileServiceError(
                "IMAGERY_ACCESS_EXPIRED",
                "The resolved imagery access has expired.",
                status_code=410,
            )
        metadata = TileMetadata(
            tile_set_id=tile_set_id,
            asset=resolution.resolved_asset.identity,
            render_preset=request.render_preset,
            bounds=resolution.resolved_asset.bounds,
            min_zoom=0,
            max_zoom=self._max_zoom,
            tile_size=request.tile_size,
            media_type="image/png",
            url_template=(f"{self._api_prefix}/imagery/tiles/{tile_set_id}/{{z}}/{{x}}/{{y}}.png"),
            expires_at=expires_at,
            attributions=resolution.attributions,
            access=TileAccess(state="available"),
        )
        entry = _TileSetEntry(
            metadata=metadata,
            source_set=source_set,
            access_scope=access_scope,
            cache_key=cache_key,
            expires_monotonic=self._clock() + effective_ttl,
        )
        self._store_set(entry)
        return metadata

    async def tile(
        self,
        tile_set_id: UUID,
        z: int,
        x: int,
        y: int,
        *,
        access_scope: str,
    ) -> RenderedTile:
        entry = self._set_by_id(tile_set_id)
        if entry.access_scope != access_scope:
            raise TileServiceError(
                "TILE_ACCESS_DENIED",
                "This tile set is not available to this access scope.",
                status_code=403,
            )
        _validate_tile_coordinates(z, x, y, max_zoom=self._max_zoom)
        if not _tile_intersects_bounds(z, x, y, entry.metadata.bounds):
            raise TileServiceError(
                "TILE_OUTSIDE_COVERAGE",
                "The requested tile does not intersect the scene coverage.",
                status_code=404,
            )
        cache_key = (access_scope, tile_set_id, z, x, y)
        cached = self._tiles.get(cache_key)
        if cached is not None:
            self._tiles.move_to_end(cache_key)
            return RenderedTile(cached)

        await self._slots.acquire()
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(
            self._executor,
            partial(
                self._renderer,
                entry.source_set.sources,
                z,
                x,
                y,
                entry.metadata.tile_size,
            ),
        )
        release_in_finally = True
        try:
            done, _pending = await asyncio.wait({future}, timeout=self._timeout)
            if not done:
                release_in_finally = False

                def release_slot(completed: asyncio.Future[bytes]) -> None:
                    if not completed.cancelled():
                        completed.exception()
                    loop.call_soon_threadsafe(self._slots.release)

                future.add_done_callback(release_slot)
                raise TileServiceError(
                    "TILE_RENDER_TIMEOUT",
                    "The imagery tile could not be rendered within the request limit.",
                    status_code=504,
                    retryable=True,
                )
            try:
                body = future.result()
            except TileServiceError:
                raise
            except Exception as exc:
                raise TileServiceError(
                    "TILE_RENDER_FAILED",
                    "The imagery tile renderer could not read the resolved provider assets.",
                    status_code=502,
                    retryable=True,
                ) from exc
        finally:
            if release_in_finally:
                self._slots.release()

        self._store_tile(cache_key, body)
        return RenderedTile(body)

    def _cached_set(self, cache_key: str) -> _TileSetEntry | None:
        tile_set_id = self._set_id_by_key.get(cache_key)
        if tile_set_id is None:
            return None
        try:
            entry = self._set_by_id(tile_set_id)
        except TileServiceError:
            return None
        self._sets_by_id.move_to_end(tile_set_id)
        return entry

    def _set_by_id(self, tile_set_id: UUID) -> _TileSetEntry:
        entry = self._sets_by_id.get(tile_set_id)
        if entry is None:
            raise TileServiceError(
                "TILE_SET_NOT_FOUND", "The imagery tile set was not found.", status_code=404
            )
        if self._clock() >= entry.expires_monotonic:
            self._remove_set(tile_set_id)
            raise TileServiceError(
                "TILE_SET_EXPIRED", "The imagery tile set has expired.", status_code=410
            )
        self._sets_by_id.move_to_end(tile_set_id)
        return entry

    def _store_set(self, entry: _TileSetEntry) -> None:
        self._sets_by_id[entry.metadata.tile_set_id] = entry
        self._set_id_by_key[entry.cache_key] = entry.metadata.tile_set_id
        while len(self._sets_by_id) > self._set_limit:
            oldest_id = next(iter(self._sets_by_id))
            self._remove_set(oldest_id)

    def _remove_set(self, tile_set_id: UUID) -> None:
        entry = self._sets_by_id.pop(tile_set_id, None)
        if entry is not None and self._set_id_by_key.get(entry.cache_key) == tile_set_id:
            del self._set_id_by_key[entry.cache_key]
        for cache_key in [key for key in self._tiles if key[1] == tile_set_id]:
            self._tile_bytes -= len(self._tiles.pop(cache_key))

    def _store_tile(self, key: tuple[str, UUID, int, int, int], body: bytes) -> None:
        if len(body) > self._byte_limit:
            return
        previous = self._tiles.pop(key, None)
        if previous is not None:
            self._tile_bytes -= len(previous)
        self._tiles[key] = body
        self._tile_bytes += len(body)
        while self._tile_bytes > self._byte_limit:
            _old_key, old_body = self._tiles.popitem(last=False)
            self._tile_bytes -= len(old_body)


def _validate_source_location(value: str) -> None:
    parsed = urlsplit(value)
    decoded_path = unquote(parsed.path)
    if (
        parsed.scheme != "https"
        or parsed.hostname != _ALLOWED_RASTER_HOST
        or parsed.port not in {None, 443}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not decoded_path.startswith(_ALLOWED_RASTER_PREFIX)
        or not decoded_path.lower().endswith(".tif")
        or any(segment in {"", ".", ".."} for segment in decoded_path.split("/")[1:])
    ):
        raise TileServiceError(
            "UPSTREAM_INVALID_ASSET_LOCATION",
            "The asset resolver returned an unapproved raster location.",
            status_code=502,
        )


def _validate_tile_coordinates(z: int, x: int, y: int, *, max_zoom: int) -> None:
    if z < 0 or z > max_zoom or x < 0 or y < 0 or x >= 2**z or y >= 2**z:
        raise TileServiceError(
            "INVALID_TILE_COORDINATES",
            "Tile coordinates are outside the supported WebMercatorQuad matrix.",
            status_code=422,
        )


def _tile_intersects_bounds(z: int, x: int, y: int, bounds: ViewerBounds) -> bool:
    count = 2**z
    west = x / count * 360.0 - 180.0
    east = (x + 1) / count * 360.0 - 180.0
    north = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / count))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * (y + 1) / count))))
    scene_west, scene_south, scene_east, scene_north = bounds
    return west < scene_east and east > scene_west and south < scene_north and north > scene_south


def _render_natural_color(
    sources: tuple[ResolvedRasterSource, ...], z: int, x: int, y: int, tile_size: int
) -> bytes:
    if [source.component.render_role for source in sources] != ["red", "green", "blue"]:
        raise TileServiceError(
            "INVALID_RENDER_RECIPE",
            "Natural colour rendering requires ordered red, green, and blue assets.",
            status_code=502,
        )
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="satquery-imagery-band") as pool:
        results = list(
            pool.map(
                lambda source: _render_component(source, z, x, y, tile_size),
                sources,
            )
        )
    bands = [result[0] for result in results]
    masks = [result[1] for result in results]
    combined_mask = np.minimum.reduce(masks)
    if not np.any(combined_mask):
        raise TileServiceError(
            "TILE_HAS_NO_DATA",
            "The requested tile contains no valid source pixels.",
            status_code=404,
        )
    return render(np.stack(bands), mask=combined_mask, img_format="PNG")


def _render_component(
    source: ResolvedRasterSource, z: int, x: int, y: int, tile_size: int
) -> tuple[np.ndarray, np.ndarray]:
    component = source.component
    budget = _RangeBudget(deadline=time.monotonic() + _RENDER_IO_DEADLINE_SECONDS)
    with Env(**_GDAL_OPTIONS):
        if source.location.startswith("https://"):
            content_length = component.content_length_bytes
            if content_length is None:
                raise OSError("resolved raster content length is unavailable")

            def opener(
                path: str,
                mode: str = "rb",
                *,
                expected_location: str = source.location,
                expected_size: int = content_length,
            ) -> _HttpRangeReader:
                if path != expected_location or mode not in {"r", "rb"}:
                    raise OSError("raster opener rejected an unexpected path or mode")
                return _HttpRangeReader(expected_location, expected_size, budget)

            dataset_context = rasterio.open(
                source.location,
                mode="r",
                driver="GTiff",
                sharing=False,
                opener=opener,
            )
        else:
            # Production sources pass the HTTPS allow-list before reaching the renderer.
            # The local branch exists only for isolated raster/mask tests.
            dataset_context = rasterio.open(source.location, mode="r", driver="GTiff")
        with dataset_context as dataset:
            _validate_raster_metadata(dataset, source)
            with Reader(None, dataset=dataset) as cog:
                image = cog.tile(
                    x,
                    y,
                    z,
                    indexes=component.band_index,
                    tilesize=tile_size,
                    nodata=component.nodata,
                    resampling_method="bilinear",
                )
    raw = np.asarray(image.array.filled(0), dtype=np.float32)[0]
    if component.scale is not None:
        physical = raw * component.scale + (component.offset or 0.0)
        display = np.clip(physical / _NATURAL_COLOR_REFLECTANCE_MAX, 0.0, 1.0)
    else:
        display = np.clip(raw / 3000.0, 0.0, 1.0)
    return (
        np.rint(display * 255.0).astype(np.uint8),
        np.asarray(image.mask, dtype=np.uint8),
    )


def _validate_raster_metadata(dataset: Any, source: ResolvedRasterSource) -> None:
    component = source.component
    if component.shape is None or component.transform is None:
        raise OSError("resolved raster metadata is incomplete")
    expected_height, expected_width = component.shape
    expected_transform = component.transform[:6]
    if (
        dataset.driver != "GTiff"
        or dataset.count < component.band_index
        or dataset.width != expected_width
        or dataset.height != expected_height
        or dataset.crs is None
        or dataset.crs != rasterio.crs.CRS.from_string(component.crs)
        or not np.allclose(tuple(dataset.transform)[:6], expected_transform, rtol=0, atol=1e-7)
    ):
        raise OSError("raster header does not match the trusted catalogue metadata")
