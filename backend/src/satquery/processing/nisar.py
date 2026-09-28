from __future__ import annotations

import asyncio
import math
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import h5py
import numpy as np
import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.features import geometry_mask, geometry_window
from rasterio.transform import array_bounds
from rasterio.warp import transform_geom

from satquery.api.schemas.nisar import (
    NisarIngestedResult,
    NisarIngestionRequest,
    NisarIngestionResponse,
    NisarIngestionUnavailable,
    NisarMaskStatistics,
)
from satquery.providers.catalog.nisar_cmr import NisarCmrProvider, NisarResolvedProduct

NISAR_PROCESSING_VERSION = "9C-nisar-gcov-provisional-h5py-1.1"
NISAR_MAX_PIXELS = 1_000_000
_POLARIZATION_BY_TERM = {
    "HHHH": "HH",
    "HVHV": "HV",
    "VHVH": "VH",
    "VVVV": "VV",
    "RHRH": "RH",
    "RVRV": "RV",
}


@dataclass(frozen=True, slots=True)
class NisarAnalyticalRaster:
    values: np.ndarray
    valid_mask: np.ndarray
    inside_aoi_mask: np.ndarray
    product_mask: np.ndarray
    crs: str
    transform: tuple[float, float, float, float, float, float]


@dataclass(frozen=True, slots=True)
class _NativeGrid:
    width: int
    height: int
    crs: CRS
    transform: Affine


class NisarGcovIngestionService:
    """Windowed GCOV extraction from a trusted, operator-staged HDF5 granule."""

    def __init__(
        self,
        provider: NisarCmrProvider,
        cache_root: Path,
        *,
        max_pixels: int = NISAR_MAX_PIXELS,
        cache_entries: int = 4,
    ) -> None:
        self._provider = provider
        self._cache_root = cache_root.resolve()
        self._max_pixels = min(max_pixels, NISAR_MAX_PIXELS)
        self._cache_entries = cache_entries
        self._ingested: OrderedDict[str, NisarAnalyticalRaster] = OrderedDict()

    async def ingest(self, request: NisarIngestionRequest) -> NisarIngestionResponse:
        resolved = await self._provider.resolve(request.scene)
        frequency = next(
            (item for item in resolved.scene.frequencies if item.frequency == request.frequency),
            None,
        )
        if frequency is None or request.covariance_term not in frequency.diagonal_covariance_terms:
            return _unavailable(
                request,
                "requested_layer_unavailable",
                "The granule does not report the requested frequency and diagonal "
                "covariance layer.",
                "Choose a frequency/polarization layer returned by discovery.",
            )
        product_path = self._product_path(resolved)
        if not product_path.is_file():
            return _unavailable(
                request,
                "earthdata_authentication_required",
                "The public CMR record is available, but the ASF HDF5 pixels have not been "
                "staged. Download requires NASA Earthdata Login.",
                "On the server host, authenticate with earthaccess.login(), download the "
                "exact CMR granule into NISAR_PRODUCT_CACHE_ROOT/<concept-id>/ under its "
                "original filename, then retry. Keep credentials out of source and logs.",
            )
        try:
            with product_path.open("rb") as staged_file:
                signature = staged_file.read(8)
        except OSError:
            return _unavailable(
                request,
                "invalid_product",
                "The staged HDF5 product cannot be opened by the backend.",
                "Check host file permissions and stage a complete ASF HDF5 granule.",
            )
        if signature != b"\x89HDF\r\n\x1a\n":
            return _unavailable(
                request,
                "invalid_product",
                "The staged product does not have an HDF5 signature.",
                "Stage the complete ASF HDF5 granule under its original CMR filename.",
            )
        return await asyncio.to_thread(self._extract, request, resolved, product_path)

    def analytical_raster(self, request: NisarIngestionRequest) -> NisarAnalyticalRaster | None:
        key = request.model_dump_json()
        raster = self._ingested.get(key)
        if raster is not None:
            self._ingested.move_to_end(key)
        return raster

    def _product_path(self, resolved: NisarResolvedProduct) -> Path:
        if Path(resolved.filename).name != resolved.filename:
            raise ValueError("provider returned an invalid NISAR filename")
        concept_directory = (self._cache_root / resolved.scene.concept_id).resolve()
        if concept_directory.parent != self._cache_root:
            raise ValueError("provider returned an invalid NISAR concept identifier")
        path = (concept_directory / resolved.filename).resolve()
        if path.parent != concept_directory:
            raise ValueError("resolved NISAR product escaped the configured cache")
        return path

    def _extract(
        self,
        request: NisarIngestionRequest,
        resolved: NisarResolvedProduct,
        product_path: Path,
    ) -> NisarIngestionResponse:
        base = f"/science/LSAR/GCOV/grids/frequency{request.frequency}"
        data_path = f"{base}/{request.covariance_term}"
        mask_path = f"{base}/mask"
        try:
            with h5py.File(product_path, "r") as product:
                group = product[base]
                if not isinstance(group, h5py.Group):
                    raise ValueError("GCOV frequency group is unavailable")
                data = group[request.covariance_term]
                mask = group["mask"]
                if not isinstance(data, h5py.Dataset) or not isinstance(mask, h5py.Dataset):
                    raise ValueError("GCOV covariance or mask dataset is unavailable")
                grid = _native_grid(group, data, mask)
                geometry = transform_geom(
                    "EPSG:4326", grid.crs, request.aoi.model_dump(mode="json"), precision=15
                )
                try:
                    window = geometry_window(grid, [geometry], boundless=False)
                except rasterio.errors.WindowError:
                    return _unavailable(
                        request,
                        "empty_intersection",
                        "The AOI does not intersect the selected GCOV grid.",
                        "Choose an AOI inside the discovered granule footprint.",
                    )
                row = int(window.row_off)
                col = int(window.col_off)
                height = int(window.height)
                width = int(window.width)
                pixels = height * width
                limit = min(request.max_pixels, self._max_pixels)
                if pixels < 1:
                    return _unavailable(
                        request,
                        "empty_intersection",
                        "The AOI contains no GCOV pixel centres.",
                        "Use a larger AOI inside the granule footprint.",
                    )
                if pixels > limit:
                    return _unavailable(
                        request,
                        "resource_limit",
                        f"The AOI requires {pixels} pixels; the limit is {limit}.",
                        "Reduce the AOI or select a coarser reported frequency.",
                    )
                window_transform = grid.transform * Affine.translation(col, row)
                inside = geometry_mask(
                    [geometry],
                    out_shape=(height, width),
                    transform=window_transform,
                    invert=True,
                    all_touched=False,
                )
                values = np.asarray(data[row : row + height, col : col + width], dtype=np.float32)
                product_mask = np.asarray(
                    mask[row : row + height, col : col + width], dtype=np.uint8
                )
                fill_value = data.attrs.get("_FillValue")
        except (OSError, KeyError, TypeError, ValueError, rasterio.errors.RasterioError) as exc:
            return _unavailable(
                request,
                "invalid_product",
                f"The staged GCOV HDF5 structure or native grid is invalid ({type(exc).__name__}).",
                "Check the full ASF granule, its projection/coordinate axes, and requested "
                "covariance/mask layers.",
            )

        source_valid = np.isfinite(values)
        if fill_value is not None and np.isfinite(fill_value):
            source_valid &= values != fill_value
        # This is the product's categorical subswath mask, not GDAL's 0/255 validity mask.
        product_valid = (product_mask >= 1) & (product_mask <= 254)
        valid = inside & source_valid & product_valid
        if not np.any(valid):
            return _unavailable(
                request,
                "invalid_product",
                "The AOI has no valid gamma-0 pixels after product-mask and nodata exclusion.",
                "Choose another acquisition/AOI and inspect the granule QA summary.",
            )
        analytical = np.full(values.shape, np.nan, dtype=np.float32)
        analytical[valid] = values[valid]
        transform_tuple = cast(
            tuple[float, float, float, float, float, float],
            tuple(float(value) for value in tuple(window_transform)[:6]),
        )
        west, south, east, north = array_bounds(height, width, window_transform)
        warnings = list(resolved.scene.quality.provisional_known_limitations)
        if not resolved.scene.quality.qa_summary_available:
            warnings.append("The granule has no linked QA summary in CMR metadata.")
        if not resolved.scene.quality.full_frame:
            warnings.append("CMR does not identify this granule as a full frame.")
        response = NisarIngestionResponse(
            outcome=NisarIngestedResult(
                state="ingested",
                source=request.scene,
                acquisition_time=resolved.scene.acquisition.start,
                frequency=request.frequency,
                covariance_term=request.covariance_term,
                polarization=_POLARIZATION_BY_TERM[request.covariance_term],
                crs=grid.crs.to_string(),
                transform=transform_tuple,
                bounds=(float(west), float(south), float(east), float(north)),
                width=width,
                height=height,
                pixel_spacing_metres=math.sqrt(abs(grid.transform.a * grid.transform.e)),
                units="gamma0_power",
                calibration="source_calibrated_rtc_gamma0_no_additional_scale",
                product_maturity="provisional",
                composite_release_id=resolved.scene.composite_release_id,
                product_version=resolved.scene.product_version,
                pge_version=resolved.scene.pge_version,
                mask=NisarMaskStatistics(
                    aoi_pixels=int(np.count_nonzero(inside)),
                    valid_pixels=int(np.count_nonzero(valid)),
                    invalid_ensemble_pixels=int(np.count_nonzero(inside & (product_mask == 0))),
                    outside_acquisition_pixels=int(
                        np.count_nonzero(inside & (product_mask == 255))
                    ),
                    nodata_or_nonfinite_backscatter_pixels=int(
                        np.count_nonzero(inside & ~source_valid)
                    ),
                ),
                quality=resolved.scene.quality,
                available_dataset_paths=[data_path, mask_path],
                quality_warnings=warnings,
                processing_version=NISAR_PROCESSING_VERSION,
            )
        )
        key = request.model_dump_json()
        self._ingested[key] = NisarAnalyticalRaster(
            values=analytical,
            valid_mask=valid,
            inside_aoi_mask=inside,
            product_mask=product_mask,
            crs=grid.crs.to_string(),
            transform=transform_tuple,
        )
        self._ingested.move_to_end(key)
        while len(self._ingested) > self._cache_entries:
            self._ingested.popitem(last=False)
        return response


def _native_grid(group: h5py.Group, data: h5py.Dataset, mask: h5py.Dataset) -> _NativeGrid:
    if data.ndim != 2 or mask.shape != data.shape or data.dtype.kind != "f":
        raise ValueError("GCOV diagonal covariance and mask must share a two-dimensional grid")
    if mask.dtype.kind not in {"u", "i"} or mask.dtype.itemsize != 1:
        raise ValueError("GCOV product mask is not categorical UByte")
    if _text(data.attrs.get("units")) != "1":
        raise ValueError("GCOV covariance units are not documented dimensionless gamma0 power")
    if _text(data.attrs.get("grid_mapping")) != "projection":
        raise ValueError("GCOV covariance lacks the expected projection mapping")
    if _text(mask.attrs.get("grid_mapping")) != "projection":
        raise ValueError("GCOV mask lacks the expected projection mapping")
    if data.attrs.get("scale_factor", 1) != 1 or data.attrs.get("add_offset", 0) != 0:
        raise ValueError("unexpected GCOV source scale/offset requires explicit calibration")
    projection = group["projection"]
    x = group["xCoordinates"]
    y = group["yCoordinates"]
    if not all(isinstance(item, h5py.Dataset) for item in (projection, x, y)):
        raise ValueError("GCOV projection or coordinate axes are unavailable")
    if x.ndim != 1 or y.ndim != 1 or x.shape[0] != data.shape[1] or y.shape[0] != data.shape[0]:
        raise ValueError("GCOV coordinate axes do not match the covariance grid")
    if x.shape[0] < 2 or y.shape[0] < 2:
        raise ValueError("GCOV coordinate axes need at least two samples")
    epsg = int(projection[()])
    if epsg != int(projection.attrs.get("epsg_code", -1)):
        raise ValueError("GCOV projection EPSG values disagree")
    crs = CRS.from_epsg(epsg)
    if not crs.is_projected or not math.isclose(crs.linear_units_factor[1], 1.0, abs_tol=1e-9):
        raise ValueError("GCOV CRS must use projected metre coordinates")
    x_first, x_second, x_last = float(x[0]), float(x[1]), float(x[-1])
    y_first, y_second, y_last = float(y[0]), float(y[1]), float(y[-1])
    x_step = x_second - x_first
    y_step = y_second - y_first
    if (
        x_step <= 0
        or y_step >= 0
        or not all(
            math.isfinite(value) for value in (x_first, x_last, y_first, y_last, x_step, y_step)
        )
    ):
        raise ValueError("GCOV coordinate axes have unsupported orientation or values")
    if not math.isclose(x_last, x_first + (x.shape[0] - 1) * x_step, abs_tol=0.01):
        raise ValueError("GCOV x coordinate axis is not regular")
    if not math.isclose(y_last, y_first + (y.shape[0] - 1) * y_step, abs_tol=0.01):
        raise ValueError("GCOV y coordinate axis is not regular")
    if not math.isclose(float(group["xCoordinateSpacing"][()]), x_step, abs_tol=0.01):
        raise ValueError("GCOV x spacing disagrees with its coordinate axis")
    if not math.isclose(float(group["yCoordinateSpacing"][()]), y_step, abs_tol=0.01):
        raise ValueError("GCOV y spacing disagrees with its coordinate axis")
    return _NativeGrid(
        width=data.shape[1],
        height=data.shape[0],
        crs=crs,
        transform=Affine(x_step, 0, x_first - x_step / 2, 0, y_step, y_first - y_step / 2),
    )


def _text(value: Any) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _unavailable(
    request: NisarIngestionRequest,
    code: str,
    reason: str,
    action: str,
) -> NisarIngestionResponse:
    return NisarIngestionResponse(
        outcome=NisarIngestionUnavailable(
            state="unavailable",
            source=request.scene,
            reason_code=code,
            retryable=False,
            reason=reason,
            corrective_action=action,
        )
    )
