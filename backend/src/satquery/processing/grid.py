from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, cast

import numpy as np
from rasterio.enums import Resampling
from rasterio.features import bounds as geometry_bounds
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from rasterio.warp import reproject, transform_geom

from satquery.api.schemas.processing import OutputGrid, PreparationRequest
from satquery.api.schemas.viewer import ViewerSceneIdentity
from satquery.processing.quality import SCL_UNKNOWN, OpticalQualityMasks
from satquery.processing.raster import (
    MAX_CALIBRATED_INPUT_PIXELS,
    BandCalibration,
    CalibratedRasterInput,
)


class GridHarmonizationError(RuntimeError):
    """A safe failure while preparing one deterministic common grid."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ScenePreparationInput:
    raster: CalibratedRasterInput
    quality: OpticalQualityMasks


@dataclass(frozen=True, slots=True)
class AreaCoverageStatistic:
    name: str
    pixel_count: int
    denominator_name: str
    denominator_pixels: int
    percent: float | None
    area_square_metres: float


@dataclass(frozen=True, slots=True)
class HarmonizedQualityMasks:
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


@dataclass(frozen=True, slots=True)
class HarmonizedScene:
    scene: ViewerSceneIdentity
    data: np.ndarray
    band_validity: np.ndarray
    valid_data: np.ndarray
    quality: HarmonizedQualityMasks
    band_order: tuple[str, ...]
    bands: tuple[BandCalibration, ...]
    native_resolutions_metres: tuple[float, ...]
    output_resolution_metres: float
    continuous_resampling: Literal["nearest", "bilinear", "cubic"]
    upsampled: bool
    upsampling_explanation: str | None
    coverage: tuple[AreaCoverageStatistic, ...]


@dataclass(frozen=True, slots=True)
class CommonGridResult:
    grid: OutputGrid
    aoi_mask: np.ndarray
    scenes: tuple[HarmonizedScene, ...]
    joint_valid_data: np.ndarray | None
    joint_usable: np.ndarray | None
    pair_coverage: tuple[AreaCoverageStatistic, ...]
    area_method: Literal["projected_pixel_count"]
    registration_status: Literal["not_assessed"]
    registration_explanation: str
    radiometric_harmonization: Literal["none"]


class CommonGridService:
    """Reproject calibrated optical inputs and masks onto one AOI-derived UTM grid."""

    def __init__(self, *, max_pixels: int = MAX_CALIBRATED_INPUT_PIXELS) -> None:
        if max_pixels < 1 or max_pixels > MAX_CALIBRATED_INPUT_PIXELS:
            raise ValueError(f"max_pixels must be between 1 and {MAX_CALIBRATED_INPUT_PIXELS}")
        self._max_pixels = max_pixels

    def prepare(
        self,
        request: PreparationRequest,
        inputs: tuple[ScenePreparationInput, ...],
    ) -> CommonGridResult:
        _validate_inputs(request, inputs)
        grid, target_geometry = _define_grid(request, self._max_pixels)
        transform = Affine(*grid.transform)
        aoi_mask = geometry_mask(
            [target_geometry],
            out_shape=(grid.height, grid.width),
            transform=transform,
            invert=True,
            all_touched=False,
        )
        if not np.any(aoi_mask):
            raise GridHarmonizationError(
                "EMPTY_AOI_GRID", "The common grid contains no pixel centres inside the AOI."
            )
        scenes = tuple(_harmonize_scene(item, request, grid, aoi_mask) for item in inputs)
        joint_valid: np.ndarray | None = None
        joint_usable: np.ndarray | None = None
        pair_coverage: tuple[AreaCoverageStatistic, ...] = ()
        if len(scenes) == 2:
            joint_valid = scenes[0].valid_data & scenes[1].valid_data
            joint_usable = scenes[0].quality.usable & scenes[1].quality.usable
            aoi_pixels = int(aoi_mask.sum())
            joint_valid_pixels = int(joint_valid.sum())
            pixel_area = grid.resolution_metres[0] * grid.resolution_metres[1]
            pair_coverage = (
                _stat(
                    "joint_valid_overlap",
                    joint_valid,
                    "inside_aoi",
                    aoi_pixels,
                    pixel_area,
                ),
                _stat(
                    "joint_usable_inside_aoi",
                    joint_usable,
                    "inside_aoi",
                    aoi_pixels,
                    pixel_area,
                ),
                _stat(
                    "joint_usable_within_valid_overlap",
                    joint_usable,
                    "joint_valid_overlap",
                    joint_valid_pixels,
                    pixel_area,
                ),
            )
        return CommonGridResult(
            grid=grid,
            aoi_mask=aoi_mask,
            scenes=scenes,
            joint_valid_data=joint_valid,
            joint_usable=joint_usable,
            pair_coverage=pair_coverage,
            area_method="projected_pixel_count",
            registration_status="not_assessed",
            registration_explanation=(
                "A shared CRS, affine transform, and dimensions do not establish feature-level "
                "co-registration; registration was not assessed."
            ),
            radiometric_harmonization="none",
        )


def _validate_inputs(
    request: PreparationRequest, inputs: tuple[ScenePreparationInput, ...]
) -> None:
    if request.options.grid_policy != "common_utm":
        raise GridHarmonizationError(
            "UNSUPPORTED_GRID_POLICY", "Task 6D requires the common_utm grid policy."
        )
    if len(inputs) != len(request.scenes):
        raise GridHarmonizationError(
            "INPUT_COUNT_MISMATCH",
            "One calibrated raster and quality result is required per scene.",
        )
    expected_roles = tuple(band.role for band in request.required_bands)
    for expected_scene, item in zip(request.scenes, inputs, strict=True):
        raster = item.raster
        if raster.scene != expected_scene or raster.band_order != expected_roles:
            raise GridHarmonizationError(
                "INPUT_IDENTITY_MISMATCH",
                "Prepared inputs must match the requested scene order and band roles.",
            )
        expected_shape = (raster.height, raster.width)
        if (
            raster.data.shape != (len(expected_roles), *expected_shape)
            or raster.band_validity.shape != raster.data.shape
            or raster.inside_aoi_mask.shape != expected_shape
        ):
            raise GridHarmonizationError(
                "INVALID_INPUT_SHAPE", "Calibrated raster arrays do not match their declared grid."
            )
        quality_arrays = (
            item.quality.scl_classes,
            item.quality.outside_aoi,
            item.quality.missing_or_invalid,
            item.quality.clouds_or_cirrus,
            item.quality.cloud_shadows,
            item.quality.cast_shadows,
            item.quality.snow_or_ice,
            item.quality.unknown_quality,
            item.quality.usable,
            item.quality.excluded_any,
        )
        if any(array.shape != expected_shape for array in quality_arrays):
            raise GridHarmonizationError(
                "INVALID_MASK_SHAPE", "Quality masks must match their calibrated raster grid."
            )


def _define_grid(
    request: PreparationRequest, service_limit: int
) -> tuple[OutputGrid, dict[str, object]]:
    geometry = request.aoi.model_dump(mode="json")
    west, south, east, north = geometry_bounds(geometry)
    if south < -80 or north > 84:
        raise GridHarmonizationError(
            "UNSUPPORTED_GEOGRAPHIC_EXTENT",
            "Task 6D supports AOIs only within the UTM latitude range of 80°S to 84°N.",
        )
    west_zone = _utm_zone(west)
    east_zone = _utm_zone(math.nextafter(east, west))
    if west_zone != east_zone or (south < 0 < north):
        raise GridHarmonizationError(
            "UNSUPPORTED_GEOGRAPHIC_EXTENT",
            "The AOI must fit within one UTM zone and one hemisphere.",
        )
    hemisphere_north = (south + north) / 2 >= 0
    epsg = (32600 if hemisphere_north else 32700) + west_zone
    target_crs = f"EPSG:{epsg}"
    target_geometry = cast(
        dict[str, object], transform_geom("EPSG:4326", target_crs, geometry, precision=15)
    )
    min_x, min_y, max_x, max_y = geometry_bounds(target_geometry)
    resolution = request.options.target_resolution_metres
    aligned_west = math.floor(min_x / resolution) * resolution
    aligned_south = math.floor(min_y / resolution) * resolution
    aligned_east = math.ceil(max_x / resolution) * resolution
    aligned_north = math.ceil(max_y / resolution) * resolution
    width = round((aligned_east - aligned_west) / resolution)
    height = round((aligned_north - aligned_south) / resolution)
    pixels = width * height
    limit = min(request.options.max_output_pixels, service_limit)
    if width < 1 or height < 1:
        raise GridHarmonizationError("EMPTY_AOI_GRID", "The AOI produced an empty common grid.")
    if pixels > limit:
        raise GridHarmonizationError(
            "GRID_RESOURCE_LIMIT",
            f"The common grid contains {pixels} pixels; the Task 6D limit is {limit}.",
        )
    grid = OutputGrid(
        crs=target_crs,
        transform=(resolution, 0.0, aligned_west, 0.0, -resolution, aligned_north),
        width=width,
        height=height,
        resolution_metres=(resolution, resolution),
        bounds=(aligned_west, aligned_south, aligned_east, aligned_north),
    )
    return grid, target_geometry


def _utm_zone(longitude: float) -> int:
    if longitude == 180:
        return 60
    return max(1, min(60, math.floor((longitude + 180) / 6) + 1))


def _harmonize_scene(
    item: ScenePreparationInput,
    request: PreparationRequest,
    grid: OutputGrid,
    aoi_mask: np.ndarray,
) -> HarmonizedScene:
    raster = item.raster
    source_transform = Affine(*raster.transform)
    target_transform = Affine(*grid.transform)
    method = request.options.continuous_resampling
    resampling = {
        "nearest": Resampling.nearest,
        "bilinear": Resampling.bilinear,
        "cubic": Resampling.cubic,
    }[method]
    shape = (grid.height, grid.width)
    output_data = np.full((len(raster.band_order), *shape), np.nan, dtype=np.float32)
    output_validity = np.zeros(output_data.shape, dtype=bool)
    for index in range(len(raster.band_order)):
        source_valid = raster.band_validity[index].astype(bool, copy=False)
        source_data = np.where(source_valid, raster.data[index], np.nan).astype(
            np.float32, copy=False
        )
        reproject(
            source=source_data,
            destination=output_data[index],
            src_transform=source_transform,
            src_crs=raster.crs,
            src_nodata=np.nan,
            dst_transform=target_transform,
            dst_crs=grid.crs,
            dst_nodata=np.nan,
            resampling=resampling,
            init_dest_nodata=True,
        )
        output_validity[index] = _warp_bool(source_valid, raster, grid, destination_shape=shape)
        output_validity[index] &= aoi_mask & np.isfinite(output_data[index])
        output_data[index, ~output_validity[index]] = np.nan
    valid_data = aoi_mask & np.all(output_validity, axis=0)
    quality = _harmonize_quality(item.quality, raster, grid, aoi_mask, valid_data)
    pixel_area = grid.resolution_metres[0] * grid.resolution_metres[1]
    aoi_pixels = int(aoi_mask.sum())
    native_resolutions = tuple(band.native_resolution_metres for band in raster.bands)
    upsampled = any(grid.resolution_metres[0] < native for native in native_resolutions)
    return HarmonizedScene(
        scene=raster.scene,
        data=output_data,
        band_validity=output_validity,
        valid_data=valid_data,
        quality=quality,
        band_order=raster.band_order,
        bands=raster.bands,
        native_resolutions_metres=native_resolutions,
        output_resolution_metres=grid.resolution_metres[0],
        continuous_resampling=method,
        upsampled=upsampled,
        upsampling_explanation=(
            "Smaller output pixels are interpolated samples and do not add spatial detail."
            if upsampled
            else None
        ),
        coverage=(
            _stat("valid_data", valid_data, "inside_aoi", aoi_pixels, pixel_area),
            _stat("usable", quality.usable, "inside_aoi", aoi_pixels, pixel_area),
        ),
    )


def _harmonize_quality(
    quality: OpticalQualityMasks,
    raster: CalibratedRasterInput,
    grid: OutputGrid,
    aoi_mask: np.ndarray,
    valid_data: np.ndarray,
) -> HarmonizedQualityMasks:
    shape = aoi_mask.shape
    classes = np.full(shape, SCL_UNKNOWN, dtype=np.uint8)
    reproject(
        source=quality.scl_classes,
        destination=classes,
        src_transform=Affine(*raster.transform),
        src_crs=raster.crs,
        src_nodata=None,
        dst_transform=Affine(*grid.transform),
        dst_crs=grid.crs,
        dst_nodata=int(SCL_UNKNOWN),
        resampling=Resampling.nearest,
        init_dest_nodata=True,
    )

    def warp(source: np.ndarray) -> np.ndarray:
        return cast(
            np.ndarray,
            aoi_mask & _warp_bool(source, raster, grid, destination_shape=shape),
        )

    missing = (~valid_data & aoi_mask) | warp(quality.missing_or_invalid)
    clouds = warp(quality.clouds_or_cirrus)
    cloud_shadows = warp(quality.cloud_shadows)
    cast_shadows = warp(quality.cast_shadows)
    snow = warp(quality.snow_or_ice)
    unknown = warp(quality.unknown_quality)
    usable = valid_data & warp(quality.usable)
    excluded = aoi_mask & (missing | clouds | cloud_shadows | cast_shadows | snow | unknown)
    classes[~aoi_mask] = SCL_UNKNOWN
    return HarmonizedQualityMasks(
        quality_information=quality.quality_information,
        unavailable_reason=quality.unavailable_reason,
        source_asset=quality.source_asset,
        processing_baseline=quality.processing_baseline,
        catalogue_scene_cloud_percent=quality.catalogue_scene_cloud_percent,
        scl_classes=classes,
        class_labels=dict(quality.class_labels),
        outside_aoi=~aoi_mask,
        missing_or_invalid=missing,
        clouds_or_cirrus=clouds,
        cloud_shadows=cloud_shadows,
        cast_shadows=cast_shadows,
        snow_or_ice=snow,
        unknown_quality=unknown,
        usable=usable,
        excluded_any=excluded,
    )


def _warp_bool(
    source: np.ndarray,
    raster: CalibratedRasterInput,
    grid: OutputGrid,
    *,
    destination_shape: tuple[int, int],
) -> np.ndarray:
    destination = np.zeros(destination_shape, dtype=np.uint8)
    reproject(
        source=source.astype(np.uint8, copy=False),
        destination=destination,
        src_transform=Affine(*raster.transform),
        src_crs=raster.crs,
        src_nodata=None,
        dst_transform=Affine(*grid.transform),
        dst_crs=grid.crs,
        # Zero is a valid False category, not nodata. Passing dst_nodata=0 causes GDAL
        # to remap zero-valued source pixels and can turn an all-False exclusion mask true.
        dst_nodata=None,
        resampling=Resampling.nearest,
        init_dest_nodata=False,
    )
    return cast(np.ndarray, destination != 0)


def _stat(
    name: str,
    mask: np.ndarray,
    denominator_name: str,
    denominator: int,
    pixel_area: float,
) -> AreaCoverageStatistic:
    count = int(mask.sum())
    return AreaCoverageStatistic(
        name=name,
        pixel_count=count,
        denominator_name=denominator_name,
        denominator_pixels=denominator,
        percent=None if denominator == 0 else count / denominator * 100.0,
        area_square_metres=count * pixel_area,
    )
