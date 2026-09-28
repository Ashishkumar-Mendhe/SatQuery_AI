from __future__ import annotations

import numpy as np

from satquery.api.schemas.processing import OutputGrid
from satquery.api.schemas.viewer import ViewerSceneIdentity
from satquery.processing import (
    CommonGridResult,
    HarmonizedQualityMasks,
    HarmonizedScene,
    RegistrationService,
)
from satquery.processing.quality import SCL_CLASS_LABELS

SHAPE = (126, 126)
SCENES = (
    ViewerSceneIdentity(
        provider="earth-search",
        collection="sentinel-2-c1-l2a",
        item="synthetic-registration-reference",
    ),
    ViewerSceneIdentity(
        provider="earth-search",
        collection="sentinel-2-c1-l2a",
        item="synthetic-registration-moving",
    ),
)


def _translate(source: np.ndarray, row_shift: int, column_shift: int, fill: float) -> np.ndarray:
    destination = np.full(source.shape, fill, dtype=source.dtype)
    height, width = source.shape
    dr0, dr1 = max(0, row_shift), min(height, height + row_shift)
    dc0, dc1 = max(0, column_shift), min(width, width + column_shift)
    sr0, sr1 = dr0 - row_shift, dr1 - row_shift
    sc0, sc1 = dc0 - column_shift, dc1 - column_shift
    destination[dr0:dr1, dc0:dc1] = source[sr0:sr1, sc0:sc1]
    return destination


def _quality(valid: np.ndarray) -> HarmonizedQualityMasks:
    empty = np.zeros(SHAPE, dtype=bool)
    missing = ~valid
    classes = np.full(SHAPE, 4, dtype=np.uint8)
    classes[missing] = 0
    return HarmonizedQualityMasks(
        quality_information="available",
        unavailable_reason=None,
        source_asset="scl",
        processing_baseline="05.11",
        catalogue_scene_cloud_percent=0.0,
        scl_classes=classes,
        class_labels=dict(SCL_CLASS_LABELS),
        outside_aoi=empty.copy(),
        missing_or_invalid=missing,
        clouds_or_cirrus=empty.copy(),
        cloud_shadows=empty.copy(),
        cast_shadows=empty.copy(),
        snow_or_ice=empty.copy(),
        unknown_quality=empty.copy(),
        usable=valid.copy(),
        excluded_any=missing.copy(),
    )


def _scene(index: int, data: np.ndarray) -> HarmonizedScene:
    valid = np.isfinite(data)
    return HarmonizedScene(
        scene=SCENES[index],
        data=data[np.newaxis, :, :].astype(np.float32),
        band_validity=valid[np.newaxis, :, :],
        valid_data=valid,
        quality=_quality(valid),
        band_order=("red",),
        bands=(),
        native_resolutions_metres=(10.0,),
        output_resolution_metres=10.0,
        continuous_resampling="bilinear",
        upsampled=False,
        upsampling_explanation=None,
        coverage=(),
    )


def _pair(reference: np.ndarray, moving: np.ndarray) -> CommonGridResult:
    aoi = np.ones(SHAPE, dtype=bool)
    first = _scene(0, reference)
    second = _scene(1, moving)
    return CommonGridResult(
        grid=OutputGrid(
            crs="EPSG:32631",
            transform=(10.0, 0.0, 500_000.0, 0.0, -10.0, 1_001_260.0),
            width=SHAPE[1],
            height=SHAPE[0],
            resolution_metres=(10.0, 10.0),
            bounds=(500_000.0, 1_000_000.0, 501_260.0, 1_001_260.0),
        ),
        aoi_mask=aoi,
        scenes=(first, second),
        joint_valid_data=first.valid_data & second.valid_data,
        joint_usable=first.quality.usable & second.quality.usable,
        pair_coverage=(),
        area_method="projected_pixel_count",
        registration_status="not_assessed",
        registration_explanation="Synthetic common grid only.",
        radiometric_harmonization="none",
    )


def _texture() -> np.ndarray:
    random = np.random.default_rng(20260923)
    return random.uniform(0.05, 0.45, SHAPE).astype(np.float32)


def test_known_translation_is_recorded_and_applied_after_independent_improvement() -> None:
    reference = _texture()
    expected_shift = (2, -3)
    moving = _translate(reference, -expected_shift[0], -expected_shift[1], np.nan)
    original = moving.copy()

    result = RegistrationService().assess_and_correct(_pair(reference, moving))

    assert result.assessment.state == "reliable"
    assert result.assessment.correction_state == "applied"
    assert result.assessment.estimated_row_shift_pixels == 2
    assert result.assessment.estimated_column_shift_pixels == -3
    assert result.assessment.estimated_x_shift_map_units == -30.0
    assert result.assessment.estimated_y_shift_map_units == -20.0
    assert result.assessment.map_displacement_units == "metres"
    assert result.assessment.agreement.agrees
    assert result.assessment.residual.improved
    assert result.assessment.residual.median_correlation_after == 1.0
    assert result.corrected_moving_scene is not None
    corrected = result.corrected_moving_scene
    valid = corrected.valid_data
    assert np.allclose(corrected.data[0][valid], reference[valid])
    assert np.array_equal(moving, original, equal_nan=True)
    assert result.corrected_joint_usable is not None
    assert np.array_equal(result.corrected_joint_usable, corrected.quality.usable)


def test_invalid_borders_are_excluded_and_remain_missing_after_translation() -> None:
    reference = _texture()
    moving = _translate(reference, -4, 2, np.nan)

    result = RegistrationService().assess_and_correct(_pair(reference, moving))

    assert result.assessment.state == "reliable"
    assert result.assessment.estimated_row_shift_pixels == 4
    assert result.assessment.estimated_column_shift_pixels == -2
    assert result.corrected_moving_scene is not None
    corrected = result.corrected_moving_scene
    assert corrected.quality.missing_or_invalid[:4].all()
    assert corrected.quality.missing_or_invalid[:, -2:].all()
    assert not corrected.quality.usable[:4].any()
    assert not corrected.quality.usable[:, -2:].any()


def test_low_texture_pair_is_inconclusive_and_never_corrected() -> None:
    reference = np.full(SHAPE, 0.2, dtype=np.float32)
    moving = _translate(reference, -2, 3, np.nan)

    result = RegistrationService().assess_and_correct(_pair(reference, moving))

    assert result.assessment.state == "inconclusive"
    assert result.assessment.correction_state == "rejected"
    assert result.assessment.distribution.usable_patches == 0
    assert result.corrected_moving_scene is None


def test_substantial_changed_region_does_not_override_distributed_consensus() -> None:
    reference = _texture()
    moving = _translate(reference, -2, -2, np.nan)
    random = np.random.default_rng(7)
    moving[:, :42] = random.uniform(0.05, 0.45, (SHAPE[0], 42))

    result = RegistrationService().assess_and_correct(_pair(reference, moving))

    assert result.assessment.state == "reliable"
    assert result.assessment.correction_state == "applied"
    assert result.assessment.estimated_row_shift_pixels == 2
    assert result.assessment.estimated_column_shift_pixels == 2
    assert result.assessment.agreement.inlier_count >= 3
    assert result.assessment.distribution.represented_columns >= 2


def test_conflicting_patch_translations_are_rejected_as_unreliable() -> None:
    reference = _texture()
    moving = np.full(SHAPE, np.nan, dtype=np.float32)
    edges = np.linspace(0, SHAPE[0], 4, dtype=int)
    shifts = [(-3, -3), (-2, 2), (3, -2), (2, 3), (0, -4)]
    estimate_index = 0
    for row in range(3):
        for column in range(3):
            r0, r1 = edges[row], edges[row + 1]
            c0, c1 = edges[column], edges[column + 1]
            if (row + column) % 2 == 0:
                correction = shifts[estimate_index]
                estimate_index += 1
            else:
                correction = (1, 1)
            shifted = _translate(reference, -correction[0], -correction[1], np.nan)
            moving[r0:r1, c0:c1] = shifted[r0:r1, c0:c1]

    result = RegistrationService().assess_and_correct(_pair(reference, moving))

    assert result.assessment.state == "inconclusive"
    assert result.assessment.correction_state == "rejected"
    assert not result.assessment.agreement.agrees
    assert result.corrected_moving_scene is None


def test_agreed_estimate_is_rejected_when_held_out_patches_do_not_improve() -> None:
    reference = _texture()
    shifted = _translate(reference, -2, -2, np.nan)
    moving = reference.copy()
    edges = np.linspace(0, SHAPE[0], 4, dtype=int)
    for row in range(3):
        for column in range(3):
            if (row + column) % 2 != 0:
                continue
            r0, r1 = edges[row], edges[row + 1]
            c0, c1 = edges[column], edges[column + 1]
            moving[r0:r1, c0:c1] = shifted[r0:r1, c0:c1]

    result = RegistrationService().assess_and_correct(_pair(reference, moving))

    assert result.assessment.agreement.agrees
    assert result.assessment.state == "inconclusive"
    assert result.assessment.correction_state == "rejected"
    assert not result.assessment.residual.improved
    assert result.corrected_moving_scene is None
