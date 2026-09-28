from __future__ import annotations

import math

import numpy as np
import pytest
from rasterio.features import bounds as geometry_bounds
from rasterio.transform import array_bounds, from_origin
from rasterio.warp import transform_bounds

from satquery.api.schemas.processing import PreparationRequest
from satquery.api.schemas.viewer import ResolvedImageryAssetIdentity, ViewerSceneIdentity
from satquery.processing import (
    AreaCoverageStatistic,
    BandCalibration,
    CalibratedRasterInput,
    CommonGridResult,
    CommonGridService,
    GridHarmonizationError,
    OpticalQualityMasks,
    ScenePreparationInput,
)
from satquery.processing.quality import SCL_CLASS_LABELS

SCENES = (
    ViewerSceneIdentity(
        provider="earth-search",
        collection="sentinel-2-c1-l2a",
        item="synthetic-grid-a",
    ),
    ViewerSceneIdentity(
        provider="earth-search",
        collection="sentinel-2-c1-l2a",
        item="synthetic-grid-b",
    ),
)
AOI: dict[str, object] = {
    "type": "Polygon",
    "coordinates": [
        [[3.001, 1.001], [3.004, 1.001], [3.004, 1.004], [3.001, 1.004], [3.001, 1.001]]
    ],
}


def _request(*, aoi: dict[str, object] = AOI) -> PreparationRequest:
    return PreparationRequest.model_validate(
        {
            "scenes": [scene.model_dump(mode="json") for scene in SCENES],
            "aoi": aoi,
            "required_bands": [
                {"role": "red", "common_name": "red"},
                {"role": "green", "common_name": "green"},
                {"role": "blue", "common_name": "blue"},
            ],
            "intended_task": "optical_pair",
            "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
            "options": {
                "grid_policy": "common_utm",
                "target_resolution_metres": 10.0,
                "continuous_resampling": "bilinear",
                "mask_resampling": "nearest",
                "calibration": "source_metadata",
                "clip_to_aoi": True,
                "preserve_originals": True,
                "max_output_pixels": 100_000,
            },
        }
    )


def _raster(
    scene: ViewerSceneIdentity,
    *,
    crs: str,
    resolution: float,
    value: float,
    validity_mode: str = "all",
) -> CalibratedRasterInput:
    source_bounds = transform_bounds("EPSG:4326", crs, *geometry_bounds(AOI), densify_pts=21)
    west = math.floor(source_bounds[0] / resolution) * resolution - 2 * resolution
    south = math.floor(source_bounds[1] / resolution) * resolution - 2 * resolution
    east = math.ceil(source_bounds[2] / resolution) * resolution + 2 * resolution
    north = math.ceil(source_bounds[3] / resolution) * resolution + 2 * resolution
    width = round((east - west) / resolution)
    height = round((north - south) / resolution)
    transform = from_origin(west, north, resolution, resolution)
    validity = np.ones((3, height, width), dtype=bool)
    if validity_mode == "left":
        validity[:, :, math.ceil(width * 0.7) :] = False
    elif validity_mode == "right":
        validity[:, :, : math.floor(width * 0.3)] = False
    elif validity_mode == "left_half":
        validity[:, :, math.ceil(width / 2) :] = False
    elif validity_mode == "right_half":
        validity[:, :, : math.ceil(width / 2)] = False
    identity = ResolvedImageryAssetIdentity(scene=scene, asset="synthetic", asset_version="v1")
    bands = tuple(
        BandCalibration(
            source=identity,
            role=role,
            band_name=role,
            band_index=index,
            units="1",
            native_resolution_metres=resolution,
            source_nodata=None,
            provider_scale=0.0001,
            provider_offset=0.0,
            applied_scale=0.0001,
            applied_offset=0.0,
            method="metadata_scale_offset",
        )
        for index, role in enumerate(("red", "green", "blue"), start=1)
    )
    raster_bounds = array_bounds(height, width, transform)
    return CalibratedRasterInput(
        scene=scene,
        data=np.full((3, height, width), value, dtype=np.float32),
        inside_aoi_mask=np.ones((height, width), dtype=bool),
        band_validity=validity,
        crs=crs,
        transform=tuple(transform)[:6],
        bounds=(
            float(raster_bounds[0]),
            float(raster_bounds[1]),
            float(raster_bounds[2]),
            float(raster_bounds[3]),
        ),
        width=width,
        height=height,
        band_order=("red", "green", "blue"),
        bands=bands,
    )


def _quality(
    raster: CalibratedRasterInput, classes: np.ndarray | None = None
) -> OpticalQualityMasks:
    shape = (raster.height, raster.width)
    scl = np.full(shape, 4, dtype=np.uint8) if classes is None else classes
    empty = np.zeros(shape, dtype=bool)
    valid = np.all(raster.band_validity, axis=0)
    usable = valid & np.isin(scl, [4, 5, 6])
    return OpticalQualityMasks(
        quality_information="available",
        unavailable_reason=None,
        source_asset="scl",
        processing_baseline="05.11",
        catalogue_scene_cloud_percent=12.0,
        scl_classes=scl,
        class_labels=dict(SCL_CLASS_LABELS),
        outside_aoi=empty.copy(),
        missing_or_invalid=~valid,
        clouds_or_cirrus=np.isin(scl, [8, 9, 10]),
        cloud_shadows=scl == 3,
        cast_shadows=scl == 2,
        snow_or_ice=scl == 11,
        unknown_quality=scl == 7,
        usable=usable,
        excluded_any=~usable,
        coverage=(),
    )


def _inputs(
    *, modes: tuple[str, str] = ("all", "all")
) -> tuple[ScenePreparationInput, ScenePreparationInput]:
    first = _raster(SCENES[0], crs="EPSG:32631", resolution=10, value=0.2, validity_mode=modes[0])
    second = _raster(SCENES[1], crs="EPSG:3857", resolution=20, value=0.4, validity_mode=modes[1])
    return ScenePreparationInput(first, _quality(first)), ScenePreparationInput(
        second, _quality(second)
    )


def _pair_stat(result: CommonGridResult, name: str) -> AreaCoverageStatistic:
    return next(item for item in result.pair_coverage if item.name == name)


def test_differing_crs_resolution_and_origins_share_one_explicit_grid() -> None:
    result = CommonGridService().prepare(_request(), _inputs())

    assert result.grid.crs == "EPSG:32631"
    assert result.grid.transform[0] == result.grid.transform[4] * -1 == 10
    assert result.grid.transform[2] % 10 == result.grid.transform[5] % 10 == 0
    assert all(scene.data.shape[1:] == result.aoi_mask.shape for scene in result.scenes)
    assert result.scenes[0].native_resolutions_metres == (10, 10, 10)
    assert result.scenes[1].native_resolutions_metres == (20, 20, 20)
    assert result.scenes[1].upsampled
    assert "do not add spatial detail" in (result.scenes[1].upsampling_explanation or "")
    assert result.registration_status == "not_assessed"
    assert result.radiometric_harmonization == "none"
    assert np.nanmean(result.scenes[0].data) == pytest.approx(0.2)
    assert np.nanmean(result.scenes[1].data) == pytest.approx(0.4)


def test_partial_overlap_reports_aoi_and_overlap_denominators_and_area() -> None:
    result = CommonGridService().prepare(_request(), _inputs(modes=("left", "right")))
    overlap = _pair_stat(result, "joint_valid_overlap")
    usable = _pair_stat(result, "joint_usable_within_valid_overlap")

    assert 0 < overlap.pixel_count < overlap.denominator_pixels
    assert overlap.denominator_name == "inside_aoi"
    assert overlap.area_square_metres == overlap.pixel_count * 100
    assert usable.denominator_name == "joint_valid_overlap"
    assert usable.denominator_pixels == overlap.pixel_count
    assert usable.percent == 100.0


def test_no_overlap_is_reported_without_fabricating_joint_usable_pixels() -> None:
    result = CommonGridService().prepare(_request(), _inputs(modes=("left_half", "right_half")))
    within_overlap = _pair_stat(result, "joint_usable_within_valid_overlap")

    assert result.joint_valid_data is not None and not result.joint_valid_data.any()
    assert result.joint_usable is not None and not result.joint_usable.any()
    assert within_overlap.denominator_pixels == 0
    assert within_overlap.percent is None


def test_categorical_masks_use_nearest_and_preserve_source_labels() -> None:
    inputs = list(_inputs())
    raster = inputs[1].raster
    classes = np.resize(np.array([[3, 4], [8, 11]], dtype=np.uint8), (raster.height, raster.width))
    inputs[1] = ScenePreparationInput(raster, _quality(raster, classes))

    result = CommonGridService().prepare(_request(), tuple(inputs))
    labels = set(np.unique(result.scenes[1].quality.scl_classes).tolist())

    assert labels <= {3, 4, 8, 11, 255}
    assert result.scenes[1].quality.cloud_shadows.dtype == np.bool_
    assert result.scenes[1].quality.snow_or_ice.dtype == np.bool_


def test_all_false_quality_exclusions_remain_false_after_reprojection() -> None:
    result = CommonGridService().prepare(_request(), _inputs())

    for scene in result.scenes:
        assert not scene.quality.clouds_or_cirrus.any()
        assert not scene.quality.cloud_shadows.any()
        assert not scene.quality.cast_shadows.any()
        assert not scene.quality.snow_or_ice.any()
        assert not scene.quality.unknown_quality.any()
        assert np.array_equal(scene.quality.usable, scene.valid_data)
    assert result.joint_usable is not None
    assert result.joint_valid_data is not None
    assert np.array_equal(result.joint_usable, result.joint_valid_data)


@pytest.mark.parametrize(
    "aoi",
    [
        {
            "type": "Polygon",
            "coordinates": [[[5.9, 1], [6.1, 1], [6.1, 1.1], [5.9, 1.1], [5.9, 1]]],
        },
        {
            "type": "Polygon",
            "coordinates": [[[3, 84.1], [3.1, 84.1], [3.1, 84.2], [3, 84.2], [3, 84.1]]],
        },
    ],
)
def test_unsupported_geographic_extents_are_explicit(aoi: dict[str, object]) -> None:
    request = _request(aoi=aoi)
    with pytest.raises(GridHarmonizationError, match="AOI") as exc_info:
        CommonGridService().prepare(request, _inputs())

    assert exc_info.value.code == "UNSUPPORTED_GEOGRAPHIC_EXTENT"
