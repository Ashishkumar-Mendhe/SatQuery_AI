from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window, from_bounds

from satquery.api.schemas.asset_resolution import AssetResolutionRequest
from satquery.processing.raster import CalibratedRasterInput
from satquery.providers.catalog import (
    CatalogueProvider,
    ResolvedQualityRasterSource,
    ResolvedQualitySourceSet,
)
from satquery.tiles.service import (
    _GDAL_OPTIONS,
    _RENDER_IO_DEADLINE_SECONDS,
    _HttpRangeReader,
    _RangeBudget,
    _validate_source_location,
)

SCL_UNKNOWN = np.uint8(255)
SCL_CLASS_LABELS: dict[int, str] = {
    0: "no_data",
    1: "saturated_or_defective",
    2: "cast_shadow",
    3: "cloud_shadow",
    4: "vegetation",
    5: "not_vegetated",
    6: "water",
    7: "unclassified",
    8: "cloud_medium_probability",
    9: "cloud_high_probability",
    10: "thin_cirrus",
    11: "snow_or_ice",
    255: "quality_unavailable",
}


class QualityMaskError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class CoverageStatistic:
    name: str
    pixel_count: int
    denominator_name: str
    denominator_pixels: int
    percent: float | None


@dataclass(frozen=True, slots=True)
class OpticalQualityMasks:
    quality_information: Literal["available", "unavailable"]
    unavailable_reason: str | None
    source_asset: str | None
    processing_baseline: str | None
    catalogue_scene_cloud_percent: float | None
    scl_classes: np.ndarray
    class_labels: dict[int, str]
    outside_aoi: np.ndarray
    missing_or_invalid: np.ndarray
    clouds_or_cirrus: np.ndarray
    cloud_shadows: np.ndarray
    cast_shadows: np.ndarray
    snow_or_ice: np.ndarray
    unknown_quality: np.ndarray
    usable: np.ndarray
    excluded_any: np.ndarray
    coverage: tuple[CoverageStatistic, ...]


QualityDatasetOpener = Callable[[ResolvedQualityRasterSource], AbstractContextManager[Any]]


class QualityMaskService:
    """Decode Sentinel-2 SCL into explicit, non-overloaded analytical masks."""

    def __init__(
        self,
        provider: CatalogueProvider,
        *,
        dataset_opener: QualityDatasetOpener | None = None,
    ) -> None:
        self._provider = provider
        self._dataset_opener = dataset_opener or _open_trusted_quality_raster

    async def decode(self, raster: CalibratedRasterInput) -> OpticalQualityMasks:
        resolved = await self._provider.resolve_quality_source(
            AssetResolutionRequest(scene=raster.scene)
        )
        if resolved.scene != raster.scene:
            raise QualityMaskError(
                "QUALITY_SOURCE_MISMATCH",
                "The trusted resolver returned quality metadata for a different scene.",
            )
        if resolved.state == "unavailable" or resolved.source is None:
            return _unavailable_masks(raster, resolved)
        if resolved.source.expires_at is not None and resolved.source.expires_at <= datetime.now(
            UTC
        ):
            return _unavailable_masks(
                raster,
                ResolvedQualitySourceSet(
                    scene=resolved.scene,
                    state="unavailable",
                    source=None,
                    processing_baseline=resolved.processing_baseline,
                    catalogue_scene_cloud_percent=resolved.catalogue_scene_cloud_percent,
                    reason="The resolved Scene Classification access has expired.",
                ),
            )
        classes = await asyncio.to_thread(self._read_classes, raster, resolved.source)
        return _decode_classes(raster, resolved, classes)

    def _read_classes(
        self,
        raster: CalibratedRasterInput,
        source: ResolvedQualityRasterSource,
    ) -> np.ndarray:
        try:
            with self._dataset_opener(source) as dataset:
                _validate_quality_metadata(dataset, source)
                target_transform = Affine(*raster.transform)
                source_bounds = transform_bounds(
                    raster.crs,
                    dataset.crs,
                    *raster.bounds,
                    densify_pts=21,
                )
                window = _bounded_window(dataset, source_bounds)
                source_transform = dataset.window_transform(window)
                masked = dataset.read(source.metadata.band_index, window=window, masked=True)
                gdal_valid = dataset.read_masks(source.metadata.band_index, window=window) != 0
                numpy_invalid = np.ma.getmaskarray(masked)
                if not np.array_equal(gdal_valid, ~numpy_invalid):
                    raise QualityMaskError(
                        "QA_MASK_CONVENTION_MISMATCH",
                        "GDAL valid-data and NumPy invalid-data masks are not inverse.",
                    )
                raw = np.asarray(masked.data, dtype=np.uint8)
                classes = np.full((raster.height, raster.width), SCL_UNKNOWN, dtype=np.uint8)
                reproject(
                    source=raw,
                    destination=classes,
                    src_transform=source_transform,
                    src_crs=dataset.crs,
                    dst_transform=target_transform,
                    dst_crs=raster.crs,
                    src_nodata=None,
                    dst_nodata=int(SCL_UNKNOWN),
                    resampling=Resampling.nearest,
                )
                valid_source = gdal_valid.astype(np.uint8)
                valid_target = np.zeros((raster.height, raster.width), dtype=np.uint8)
                reproject(
                    source=valid_source,
                    destination=valid_target,
                    src_transform=source_transform,
                    src_crs=dataset.crs,
                    dst_transform=target_transform,
                    dst_crs=raster.crs,
                    src_nodata=None,
                    dst_nodata=0,
                    resampling=Resampling.nearest,
                )
                classes[(valid_target == 0) & (classes != 0)] = SCL_UNKNOWN
                return classes
        except QualityMaskError:
            raise
        except (OSError, rasterio.errors.RasterioError, ValueError) as exc:
            raise QualityMaskError(
                "QUALITY_RASTER_READ_FAILED",
                "The Sentinel-2 Scene Classification raster could not be read safely.",
            ) from exc


def _decode_classes(
    raster: CalibratedRasterInput,
    resolved: ResolvedQualitySourceSet,
    classes: np.ndarray,
) -> OpticalQualityMasks:
    inside = raster.inside_aoi_mask.astype(bool, copy=False)
    outside = ~inside
    source_valid = np.all(raster.band_validity, axis=0)
    missing = inside & (~source_valid | np.isin(classes, [0, 1]))
    clouds = inside & np.isin(classes, [8, 9, 10])
    cloud_shadows = inside & (classes == 3)
    cast_shadows = inside & (classes == 2)
    snow = inside & (classes == 11)
    recognized = np.isin(classes, list(range(12)))
    unknown = inside & ((classes == 7) | ~recognized)
    usable = inside & source_valid & np.isin(classes, [4, 5, 6])
    excluded = inside & (missing | clouds | cloud_shadows | cast_shadows | snow | unknown)
    assessed = inside & np.isin(classes, [2, 3, 4, 5, 6, 8, 9, 10, 11])
    return OpticalQualityMasks(
        quality_information="available",
        unavailable_reason=None,
        source_asset=(
            resolved.source.metadata.identity.asset if resolved.source is not None else None
        ),
        processing_baseline=resolved.processing_baseline,
        catalogue_scene_cloud_percent=resolved.catalogue_scene_cloud_percent,
        scl_classes=classes,
        class_labels=dict(SCL_CLASS_LABELS),
        outside_aoi=outside,
        missing_or_invalid=missing,
        clouds_or_cirrus=clouds,
        cloud_shadows=cloud_shadows,
        cast_shadows=cast_shadows,
        snow_or_ice=snow,
        unknown_quality=unknown,
        usable=usable,
        excluded_any=excluded,
        coverage=_coverage(
            raster,
            missing=missing,
            clouds=clouds,
            cloud_shadows=cloud_shadows,
            cast_shadows=cast_shadows,
            snow=snow,
            unknown=unknown,
            usable=usable,
            excluded=excluded,
            assessed=assessed,
        ),
    )


def _unavailable_masks(
    raster: CalibratedRasterInput, resolved: ResolvedQualitySourceSet
) -> OpticalQualityMasks:
    inside = raster.inside_aoi_mask.astype(bool, copy=False)
    outside = ~inside
    missing = inside & ~np.all(raster.band_validity, axis=0)
    empty = np.zeros(inside.shape, dtype=bool)
    unknown = inside.copy()
    excluded = missing | unknown
    classes = np.full(inside.shape, SCL_UNKNOWN, dtype=np.uint8)
    return OpticalQualityMasks(
        quality_information="unavailable",
        unavailable_reason=resolved.reason or "Scene quality information is unavailable.",
        source_asset=None,
        processing_baseline=resolved.processing_baseline,
        catalogue_scene_cloud_percent=resolved.catalogue_scene_cloud_percent,
        scl_classes=classes,
        class_labels=dict(SCL_CLASS_LABELS),
        outside_aoi=outside,
        missing_or_invalid=missing,
        clouds_or_cirrus=empty.copy(),
        cloud_shadows=empty.copy(),
        cast_shadows=empty.copy(),
        snow_or_ice=empty.copy(),
        unknown_quality=unknown,
        usable=empty.copy(),
        excluded_any=excluded,
        coverage=_coverage(
            raster,
            missing=missing,
            clouds=empty,
            cloud_shadows=empty,
            cast_shadows=empty,
            snow=empty,
            unknown=unknown,
            usable=empty,
            excluded=excluded,
            assessed=empty,
        ),
    )


def _coverage(
    raster: CalibratedRasterInput,
    *,
    missing: np.ndarray,
    clouds: np.ndarray,
    cloud_shadows: np.ndarray,
    cast_shadows: np.ndarray,
    snow: np.ndarray,
    unknown: np.ndarray,
    usable: np.ndarray,
    excluded: np.ndarray,
    assessed: np.ndarray,
) -> tuple[CoverageStatistic, ...]:
    aoi_pixels = int(raster.inside_aoi_mask.sum())
    assessed_pixels = int(assessed.sum())
    window_pixels = raster.width * raster.height
    return (
        _stat("outside_aoi", ~raster.inside_aoi_mask, "output_window", window_pixels),
        _stat("missing_or_invalid", missing, "inside_aoi", aoi_pixels),
        _stat("clouds_or_cirrus", clouds, "quality_assessed", assessed_pixels),
        _stat("cloud_shadows", cloud_shadows, "quality_assessed", assessed_pixels),
        _stat("cast_shadows", cast_shadows, "quality_assessed", assessed_pixels),
        _stat("snow_or_ice", snow, "quality_assessed", assessed_pixels),
        _stat("unknown_quality", unknown, "inside_aoi", aoi_pixels),
        _stat("excluded_any", excluded, "inside_aoi", aoi_pixels),
        _stat("usable", usable, "inside_aoi", aoi_pixels),
    )


def _stat(
    name: str, mask: np.ndarray, denominator_name: str, denominator: int
) -> CoverageStatistic:
    count = int(mask.sum())
    percent = None if denominator == 0 else count / denominator * 100.0
    return CoverageStatistic(
        name=name,
        pixel_count=count,
        denominator_name=denominator_name,
        denominator_pixels=denominator,
        percent=percent,
    )


def _bounded_window(dataset: Any, bounds: tuple[float, float, float, float]) -> Window:
    candidate = from_bounds(*bounds, transform=dataset.transform)
    col_start = max(0, math.floor(candidate.col_off))
    row_start = max(0, math.floor(candidate.row_off))
    col_stop = min(dataset.width, math.ceil(candidate.col_off + candidate.width))
    row_stop = min(dataset.height, math.ceil(candidate.row_off + candidate.height))
    if col_stop <= col_start or row_stop <= row_start:
        raise QualityMaskError(
            "EMPTY_QUALITY_INTERSECTION",
            "The Scene Classification raster does not intersect the prepared AOI grid.",
        )
    return Window(col_start, row_start, col_stop - col_start, row_stop - row_start)


def _validate_quality_metadata(dataset: Any, source: ResolvedQualityRasterSource) -> None:
    metadata = source.metadata
    expected_height, expected_width = metadata.shape
    if (
        dataset.driver != "GTiff"
        or dataset.count < metadata.band_index
        or dataset.width != expected_width
        or dataset.height != expected_height
        or dataset.crs is None
        or dataset.crs != rasterio.crs.CRS.from_string(metadata.crs)
        or not np.allclose(tuple(dataset.transform)[:6], metadata.transform[:6], rtol=0, atol=1e-7)
    ):
        raise QualityMaskError(
            "QUALITY_RASTER_METADATA_MISMATCH",
            "The Scene Classification header does not match trusted provider metadata.",
        )


@contextmanager
def _open_trusted_quality_raster(source: ResolvedQualityRasterSource) -> Iterator[Any]:
    _validate_source_location(source.location)
    content_length = source.metadata.content_length_bytes
    if content_length is None or content_length <= 0:
        raise OSError("resolved quality-raster content length is unavailable")
    budget = _RangeBudget(deadline=time.monotonic() + _RENDER_IO_DEADLINE_SECONDS)

    def opener(
        path: str,
        mode: str = "rb",
        *,
        expected_location: str = source.location,
        expected_size: int = content_length,
    ) -> _HttpRangeReader:
        if path != expected_location or mode not in {"r", "rb"}:
            raise OSError("quality-raster opener rejected an unexpected path or mode")
        return _HttpRangeReader(expected_location, expected_size, budget)

    with rasterio.Env(**_GDAL_OPTIONS):
        with rasterio.open(
            source.location,
            mode="r",
            driver="GTiff",
            sharing=False,
            opener=opener,
        ) as dataset:
            yield dataset
