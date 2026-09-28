from __future__ import annotations

import asyncio
import math
from collections import OrderedDict
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID, uuid4

import numpy as np
import rasterio
from rasterio.env import Env
from rasterio.features import geometry_mask, geometry_window
from rasterio.transform import array_bounds
from rasterio.warp import transform_geom
from rasterio.windows import Window
from rio_tiler.utils import render

from satquery.api.schemas.sar import (
    SarMaskStatistics,
    SarPreparationRequest,
    SarPreparationResponse,
)
from satquery.providers.catalog.inpe_sar import InpeSarProvider, InpeSarResolvedScene

SAR_PROCESSING_VERSION = "9B-inpe-rtc-1.0"
SAR_MAX_PIXELS = 1_000_000
SAR_DISPLAY_DB_MIN = -25.0
SAR_DISPLAY_DB_MAX = 0.0
_GDAL_OPTIONS = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_CONNECTTIMEOUT": "10",
    "GDAL_HTTP_TIMEOUT": "30",
    "GDAL_HTTP_MAX_RETRY": "1",
    "GDAL_CACHEMAX": 64,
}


class SarProcessingError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class SarAnalyticalRaster:
    values: np.ndarray
    valid_mask: np.ndarray
    inside_aoi_mask: np.ndarray
    layover_shadow_mask: np.ndarray
    crs: str
    transform: tuple[float, float, float, float, float, float]


@dataclass(frozen=True, slots=True)
class _PreparedSar:
    response: SarPreparationResponse
    raster: SarAnalyticalRaster
    preview_png: bytes


RasterOpener = Callable[[str], AbstractContextManager[Any]]


class SarRasterService:
    """Bounded AOI extraction of already-calibrated INPE Sentinel-1 RTC gamma0."""

    def __init__(
        self,
        provider: InpeSarProvider,
        *,
        opener: RasterOpener | None = None,
        max_pixels: int = SAR_MAX_PIXELS,
        cache_entries: int = 8,
        api_prefix: str = "/api/v1",
    ) -> None:
        self._provider = provider
        self._opener = opener or _open_remote_raster
        self._max_pixels = min(max_pixels, SAR_MAX_PIXELS)
        self._cache_entries = cache_entries
        self._api_prefix = api_prefix
        self._prepared: OrderedDict[UUID, _PreparedSar] = OrderedDict()

    async def prepare(self, request: SarPreparationRequest) -> SarPreparationResponse:
        resolved = await self._provider.resolve(request.scene, request.polarization)
        prepared = await asyncio.to_thread(self._extract, request, resolved)
        self._prepared[prepared.response.preparation_id] = prepared
        self._prepared.move_to_end(prepared.response.preparation_id)
        while len(self._prepared) > self._cache_entries:
            self._prepared.popitem(last=False)
        return prepared.response

    def preview(self, preparation_id: UUID) -> bytes:
        prepared = self._get(preparation_id)
        return prepared.preview_png

    def analytical_raster(self, preparation_id: UUID) -> SarAnalyticalRaster:
        return self._get(preparation_id).raster

    def _get(self, preparation_id: UUID) -> _PreparedSar:
        result = self._prepared.get(preparation_id)
        if result is None:
            raise SarProcessingError(
                "SAR_PREPARATION_NOT_FOUND",
                "The SAR preparation is unavailable or expired; prepare the selected scene again.",
                status_code=404,
            )
        self._prepared.move_to_end(preparation_id)
        return result

    def _extract(
        self, request: SarPreparationRequest, resolved: InpeSarResolvedScene
    ) -> _PreparedSar:
        try:
            with self._opener(resolved.backscatter.location) as data_set:
                _validate_dataset(data_set, "gamma0")
                geometry = transform_geom(
                    "EPSG:4326", data_set.crs, request.aoi.model_dump(mode="json"), precision=15
                )
                try:
                    raw_window = geometry_window(data_set, [geometry], boundless=False)
                except rasterio.errors.WindowError as exc:
                    raise SarProcessingError(
                        "EMPTY_SAR_INTERSECTION",
                        "The AOI does not intersect the selected Sentinel-1 RTC scene.",
                    ) from exc
                window = Window(
                    int(raw_window.col_off),
                    int(raw_window.row_off),
                    int(raw_window.width),
                    int(raw_window.height),
                )
                pixels = int(window.width * window.height)
                limit = min(request.max_pixels, self._max_pixels)
                if pixels < 1:
                    raise SarProcessingError(
                        "EMPTY_SAR_INTERSECTION", "The AOI contains no source pixel centres."
                    )
                if pixels > limit:
                    raise SarProcessingError(
                        "SAR_RESOURCE_LIMIT",
                        f"The AOI needs {pixels} pixels; the configured limit is {limit}.",
                    )
                transform = data_set.window_transform(window)
                shape = (int(window.height), int(window.width))
                inside = geometry_mask(
                    [geometry], out_shape=shape, transform=transform, invert=True, all_touched=False
                )
                source = data_set.read(1, window=window, masked=True)
                values = np.asarray(source.data, dtype=np.float32)
                source_valid = ~np.ma.getmaskarray(source)
                source_valid &= np.isfinite(values)
                source_valid &= values != resolved.backscatter.nodata
                crs = data_set.crs.to_string()
                source_transform = tuple(float(value) for value in tuple(data_set.transform)[:6])
                source_shape = data_set.shape
            with self._opener(resolved.layover_shadow_mask) as mask_set:
                _validate_dataset(mask_set, "layover/shadow mask")
                if (
                    mask_set.crs.to_string() != crs
                    or mask_set.shape != source_shape
                    or not np.allclose(tuple(mask_set.transform)[:6], source_transform, atol=1e-12)
                ):
                    raise SarProcessingError(
                        "SAR_MASK_GRID_MISMATCH",
                        "The provider terrain mask is not aligned with the gamma0 raster.",
                        status_code=502,
                    )
                terrain_mask = np.asarray(mask_set.read(1, window=window), dtype=np.uint8)
        except SarProcessingError:
            raise
        except (OSError, rasterio.errors.RasterioError, ValueError) as exc:
            raise SarProcessingError(
                "SAR_RASTER_UNAVAILABLE",
                "The trusted RTC raster could not be read; verify provider coverage "
                "and network access.",
                status_code=502,
            ) from exc

        terrain_valid = terrain_mask == 0
        valid = inside & source_valid & terrain_valid
        if not np.any(valid):
            raise SarProcessingError(
                "SAR_NO_VALID_DATA",
                "The AOI has no usable gamma0 pixels after nodata and layover/shadow exclusion.",
            )
        analytical = np.full(values.shape, np.nan, dtype=np.float32)
        analytical[valid] = values[valid]
        transform_tuple = cast(
            tuple[float, float, float, float, float, float],
            tuple(float(value) for value in tuple(transform)[:6]),
        )
        west, south, east, north = array_bounds(values.shape[0], values.shape[1], transform)
        aoi_pixels = int(np.count_nonzero(inside))
        preparation_id = uuid4()
        response = SarPreparationResponse(
            preparation_id=preparation_id,
            source=request.scene,
            acquisition_time=resolved.scene.acquisition.start,
            polarization=request.polarization,
            crs="EPSG:4326",
            transform=transform_tuple,
            width=values.shape[1],
            height=values.shape[0],
            bounds=(float(west), float(south), float(east), float(north)),
            native_resolution_metres=resolved.scene.native_resolution_metres,
            analysis_units="gamma0_power",
            calibration=(
                "Provider-supplied calibrated gamma0 power; identity conversion "
                "applied exactly once."
            ),
            geometric_processing=(
                "INPE Level-2 radiometric terrain correction derived from Sentinel-1 GRD."
            ),
            terrain_model=resolved.terrain_model,
            mask=SarMaskStatistics(
                aoi_pixels=aoi_pixels,
                valid_pixels=int(np.count_nonzero(valid)),
                nodata_pixels=int(np.count_nonzero(inside & ~source_valid)),
                layover_or_shadow_pixels=int(
                    np.count_nonzero(inside & source_valid & ~terrain_valid)
                ),
            ),
            display_scaling=(
                "Visualization only: 10*log10(gamma0 power), fixed -25 to 0 dB stretch; "
                "analysis retains linear gamma0 power."
            ),
            preview_url=f"{self._api_prefix}/sar/preparations/{preparation_id}/preview.png",
            processing_version=SAR_PROCESSING_VERSION,
            source_checksum=resolved.backscatter.checksum,
            warnings=[
                "Upslope/down-slope radiometry and residual geometric uncertainty "
                "remain terrain-dependent.",
                "The fixed dB preview is visualization only and must not be used as "
                "analytical input.",
            ],
        )
        raster = SarAnalyticalRaster(
            values=analytical,
            valid_mask=valid,
            inside_aoi_mask=inside,
            layover_shadow_mask=inside & source_valid & ~terrain_valid,
            crs=crs,
            transform=transform_tuple,
        )
        return _PreparedSar(
            response=response, raster=raster, preview_png=_preview(analytical, valid)
        )


def _preview(values: np.ndarray, valid: np.ndarray) -> bytes:
    db = np.full(values.shape, SAR_DISPLAY_DB_MIN, dtype=np.float32)
    positive = valid & (values > 0)
    db[positive] = 10.0 * np.log10(values[positive])
    scaled = np.clip(
        (db - SAR_DISPLAY_DB_MIN) / (SAR_DISPLAY_DB_MAX - SAR_DISPLAY_DB_MIN), 0.0, 1.0
    )
    display = np.rint(scaled * 255.0).astype(np.uint8)
    return render(display[np.newaxis, ...], mask=valid.astype(np.uint8) * 255, img_format="PNG")


def _validate_dataset(dataset: Any, label: str) -> None:
    if dataset.crs is None or dataset.transform is None or dataset.count != 1:
        raise SarProcessingError(
            "SAR_GEOREFERENCING_UNAVAILABLE",
            f"The {label} asset lacks required single-band georeferencing.",
            status_code=502,
        )
    if dataset.crs.to_string() != "EPSG:4326":
        raise SarProcessingError(
            "SAR_CRS_UNSUPPORTED",
            f"The {label} asset is not in the documented INPE EPSG:4326 grid.",
            status_code=502,
        )
    if not all(math.isfinite(float(value)) for value in tuple(dataset.transform)[:6]):
        raise SarProcessingError(
            "SAR_GEOREFERENCING_UNAVAILABLE", f"The {label} transform is invalid.", status_code=502
        )


@contextmanager
def _open_remote_raster(location: str) -> Iterator[Any]:
    with Env(**_GDAL_OPTIONS):
        with rasterio.open(location, mode="r", driver="GTiff", sharing=False) as dataset:
            yield dataset
