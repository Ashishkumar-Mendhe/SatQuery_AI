from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

import numpy as np
import rasterio
from rasterio.env import Env
from rasterio.errors import WindowError
from rasterio.features import geometry_mask, geometry_window
from rasterio.transform import array_bounds
from rasterio.warp import transform_geom
from rasterio.windows import Window

from satquery.api.schemas.asset_resolution import AssetResolutionRequest, ResolvedRasterComponent
from satquery.api.schemas.processing import PreparationRequest
from satquery.api.schemas.viewer import ResolvedImageryAssetIdentity, ViewerSceneIdentity
from satquery.providers.catalog import CatalogueProvider, ResolvedRasterSource
from satquery.tiles.service import (
    _GDAL_OPTIONS,
    _RENDER_IO_DEADLINE_SECONDS,
    _HttpRangeReader,
    _RangeBudget,
    _validate_raster_metadata,
    _validate_source_location,
)

MAX_CALIBRATED_INPUT_PIXELS = 4_000_000
_OUTPUT_UNITS = "1"


class RasterInputError(RuntimeError):
    """Safe bounded-raster preparation failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class BandCalibration:
    source: ResolvedImageryAssetIdentity
    role: str
    band_name: str
    band_index: int
    units: str
    native_resolution_metres: float
    source_nodata: float | Literal["nan", "inf", "-inf"] | None
    provider_scale: float | None
    provider_offset: float | None
    applied_scale: float
    applied_offset: float
    method: Literal["metadata_scale_offset", "identity"]


@dataclass(frozen=True, slots=True)
class CalibratedRasterInput:
    scene: ViewerSceneIdentity
    data: np.ndarray
    inside_aoi_mask: np.ndarray
    band_validity: np.ndarray
    crs: str
    transform: tuple[float, float, float, float, float, float]
    bounds: tuple[float, float, float, float]
    width: int
    height: int
    band_order: tuple[str, ...]
    bands: tuple[BandCalibration, ...]


RasterDatasetOpener = Callable[[ResolvedRasterSource], AbstractContextManager[Any]]


class RasterInputService:
    """Resolve trusted scene assets and extract calibrated, AOI-bounded source pixels."""

    def __init__(
        self,
        provider: CatalogueProvider,
        *,
        dataset_opener: RasterDatasetOpener | None = None,
        max_pixels: int = MAX_CALIBRATED_INPUT_PIXELS,
    ) -> None:
        if max_pixels < 1 or max_pixels > MAX_CALIBRATED_INPUT_PIXELS:
            raise ValueError(f"max_pixels must be between 1 and {MAX_CALIBRATED_INPUT_PIXELS}")
        self._provider = provider
        self._dataset_opener = dataset_opener or _open_trusted_raster
        self._max_pixels = max_pixels

    async def extract(self, request: PreparationRequest) -> CalibratedRasterInput:
        _validate_request_profile(request)
        source_set = await self._provider.resolve_imagery_sources(
            AssetResolutionRequest(scene=request.scenes[0])
        )
        resolution = source_set.resolution
        if resolution.status.state != "supported" or resolution.resolved_asset is None:
            raise RasterInputError(
                "RASTER_SOURCE_UNAVAILABLE",
                resolution.status.reason or "The selected scene has no supported raster source.",
            )
        if tuple(source.component for source in source_set.sources) != tuple(resolution.components):
            raise RasterInputError(
                "RASTER_SOURCE_MISMATCH",
                "The trusted resolver returned raster sources inconsistent with its metadata.",
            )
        sources_by_role: dict[str, ResolvedRasterSource] = {
            source.component.common_name: source for source in source_set.sources
        }
        if any(
            source.expires_at is not None and source.expires_at <= datetime.now(UTC)
            for source in source_set.sources
        ):
            raise RasterInputError(
                "RASTER_SOURCE_EXPIRED", "The trusted raster access has expired."
            )
        requested_roles = tuple(band.common_name for band in request.required_bands)
        if len(sources_by_role) != len(source_set.sources):
            raise RasterInputError(
                "RASTER_SOURCE_MISMATCH", "The trusted resolver returned duplicate band roles."
            )
        try:
            ordered_sources = tuple(sources_by_role[role] for role in requested_roles)
        except KeyError as exc:
            raise RasterInputError(
                "UNSUPPORTED_BAND",
                f"The selected scene does not expose the required '{exc.args[0]}' band.",
            ) from None
        return await asyncio.to_thread(
            self._extract_sources,
            request,
            ordered_sources,
        )

    def _extract_sources(
        self,
        request: PreparationRequest,
        sources: tuple[ResolvedRasterSource, ...],
    ) -> CalibratedRasterInput:
        first = sources[0]
        try:
            with self._dataset_opener(first) as dataset:
                _validate_source_grid(request, first.component, dataset)
                _validate_raster_metadata(dataset, first)
                geometry = transform_geom(
                    "EPSG:4326",
                    dataset.crs,
                    request.aoi.model_dump(mode="json"),
                    precision=15,
                )
                window = _geometry_window(dataset, geometry)
                width, height = int(window.width), int(window.height)
                _validate_pixel_limit(request, width, height, self._max_pixels)
                transform = dataset.window_transform(window)
                inside_aoi = geometry_mask(
                    [geometry],
                    out_shape=(height, width),
                    transform=transform,
                    invert=True,
                    all_touched=False,
                )
                if not np.any(inside_aoi):
                    raise RasterInputError(
                        "EMPTY_AOI_INTERSECTION",
                        "The AOI contains no source pixel centres in the selected scene.",
                    )
                first_data, first_validity = _read_and_calibrate(
                    dataset, first.component, window, inside_aoi
                )
                crs = dataset.crs.to_string()
        except RasterInputError:
            raise
        except (OSError, rasterio.errors.RasterioError, ValueError) as exc:
            raise RasterInputError(
                "RASTER_READ_FAILED",
                "The selected raster could not be read with its trusted georeferencing.",
            ) from exc

        data = [first_data]
        validity = [first_validity]
        for source in sources[1:]:
            _require_same_grid(first.component, source.component)
            try:
                with self._dataset_opener(source) as dataset:
                    if dataset.crs is None or dataset.transform is None:
                        raise RasterInputError(
                            "MISSING_GEOREFERENCING",
                            "Every source band requires a CRS and affine transform.",
                        )
                    _validate_raster_metadata(dataset, source)
                    band_data, band_validity = _read_and_calibrate(
                        dataset, source.component, window, inside_aoi
                    )
            except RasterInputError:
                raise
            except (OSError, rasterio.errors.RasterioError, ValueError) as exc:
                raise RasterInputError(
                    "RASTER_READ_FAILED",
                    "A selected raster band could not be read on the common source grid.",
                ) from exc
            data.append(band_data)
            validity.append(band_validity)

        transform_tuple = cast(
            tuple[float, float, float, float, float, float],
            tuple(float(value) for value in tuple(transform)[:6]),
        )
        west, south, east, north = array_bounds(height, width, transform)
        return CalibratedRasterInput(
            scene=request.scenes[0],
            data=np.stack(data),
            inside_aoi_mask=inside_aoi,
            band_validity=np.stack(validity),
            crs=crs,
            transform=transform_tuple,
            bounds=(float(west), float(south), float(east), float(north)),
            width=width,
            height=height,
            band_order=tuple(band.role for band in request.required_bands),
            bands=tuple(
                _calibration_metadata(band.role, source.component)
                for band, source in zip(request.required_bands, sources, strict=True)
            ),
        )


def _validate_request_profile(request: PreparationRequest) -> None:
    if request.intended_task != "optical_single_scene" or len(request.scenes) != 1:
        raise RasterInputError(
            "UNSUPPORTED_PROCESSING_TASK", "Task 6B accepts one optical scene only."
        )
    unsupported = sorted(
        {band.common_name for band in request.required_bands} - {"red", "green", "blue"}
    )
    if unsupported:
        raise RasterInputError(
            "UNSUPPORTED_BAND",
            f"Task 6B supports only resolved RGB bands; unsupported: {', '.join(unsupported)}.",
        )
    if request.options.grid_policy != "source_aligned":
        raise RasterInputError(
            "UNSUPPORTED_GRID_POLICY",
            (
                "Task 6B preserves the native source grid; common-grid reprojection "
                "is not implemented."
            ),
        )


def _validate_source_grid(
    request: PreparationRequest, component: ResolvedRasterComponent, dataset: Any
) -> None:
    if dataset.crs is None or dataset.transform is None or not dataset.crs.is_projected:
        raise RasterInputError(
            "MISSING_GEOREFERENCING", "The source requires a projected CRS and affine transform."
        )
    if not math.isclose(
        request.options.target_resolution_metres,
        component.resolution_metres,
        rel_tol=0,
        abs_tol=1e-6,
    ):
        raise RasterInputError(
            "UNSUPPORTED_RESAMPLING",
            "Task 6B does not resample; target resolution must equal native resolution.",
        )


def _geometry_window(dataset: Any, geometry: dict[str, Any]) -> Window:
    try:
        window = geometry_window(dataset, [geometry], boundless=False)
    except WindowError as exc:
        raise RasterInputError(
            "EMPTY_AOI_INTERSECTION", "The AOI does not intersect the selected scene."
        ) from exc
    return Window(
        int(window.col_off),
        int(window.row_off),
        int(window.width),
        int(window.height),
    )


def _validate_pixel_limit(
    request: PreparationRequest, width: int, height: int, service_limit: int
) -> None:
    pixels = width * height
    limit = min(request.options.max_output_pixels, service_limit)
    if pixels < 1:
        raise RasterInputError(
            "EMPTY_AOI_INTERSECTION", "The AOI does not intersect a source pixel."
        )
    if pixels > limit:
        raise RasterInputError(
            "RASTER_RESOURCE_LIMIT",
            f"The AOI window contains {pixels} pixels; the Task 6B limit is {limit}.",
        )


def _require_same_grid(
    reference: ResolvedRasterComponent, component: ResolvedRasterComponent
) -> None:
    if (
        component.crs != reference.crs
        or component.shape != reference.shape
        or component.transform is None
        or reference.transform is None
        or not np.allclose(component.transform[:6], reference.transform[:6], rtol=0, atol=1e-7)
    ):
        raise RasterInputError(
            "INCOMPATIBLE_SOURCE_GRIDS",
            "Task 6B requires selected source bands on one identical native grid.",
        )


def _read_and_calibrate(
    dataset: Any,
    component: ResolvedRasterComponent,
    window: Window,
    inside_aoi: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    source = dataset.read(component.band_index, window=window, masked=True)
    raw = np.asarray(source.data)
    valid = ~np.ma.getmaskarray(source)
    nodata = component.nodata
    if isinstance(nodata, float):
        valid &= raw != nodata
    elif nodata == "nan":
        valid &= ~np.isnan(raw)
    elif nodata == "inf":
        valid &= raw != np.inf
    elif nodata == "-inf":
        valid &= raw != -np.inf
    valid &= np.isfinite(raw)
    valid &= inside_aoi
    scale = component.scale if component.scale is not None else 1.0
    offset = component.offset if component.offset is not None else 0.0
    calibrated = np.full(raw.shape, np.nan, dtype=np.float32)
    calibrated[valid] = raw[valid].astype(np.float32) * scale + offset
    return calibrated, valid


def _calibration_metadata(role: str, component: ResolvedRasterComponent) -> BandCalibration:
    scale = component.scale if component.scale is not None else 1.0
    offset = component.offset if component.offset is not None else 0.0
    method: Literal["metadata_scale_offset", "identity"] = (
        "identity" if scale == 1.0 and offset == 0.0 else "metadata_scale_offset"
    )
    return BandCalibration(
        source=component.identity,
        role=role,
        band_name=component.band_name,
        band_index=component.band_index,
        units=_OUTPUT_UNITS,
        native_resolution_metres=component.resolution_metres,
        source_nodata=component.nodata,
        provider_scale=component.scale,
        provider_offset=component.offset,
        applied_scale=scale,
        applied_offset=offset,
        method=method,
    )


@contextmanager
def _open_trusted_raster(source: ResolvedRasterSource) -> Iterator[Any]:
    _validate_source_location(source.location)
    content_length = source.component.content_length_bytes
    if content_length is None or content_length <= 0:
        raise OSError("resolved raster content length is unavailable")
    budget = _RangeBudget(deadline=time.monotonic() + _RENDER_IO_DEADLINE_SECONDS)

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

    with Env(**_GDAL_OPTIONS):
        with rasterio.open(
            source.location,
            mode="r",
            driver="GTiff",
            sharing=False,
            opener=opener,
        ) as dataset:
            yield dataset
