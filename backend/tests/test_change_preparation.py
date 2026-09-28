from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Literal

import numpy as np
import pytest

from satquery.api.schemas.processing import OutputGrid, PreparationRequest
from satquery.api.schemas.viewer import ResolvedImageryAssetIdentity, ViewerSceneIdentity
from satquery.processing import (
    AreaMeasurementError,
    BandCalibration,
    ChangeSummaryService,
    CommonGridResult,
    EstimateAgreement,
    HarmonizedQualityMasks,
    HarmonizedScene,
    OpticalChangeDetectionOutcome,
    OpticalChangeDetector,
    PairPreparationService,
    PatchDistribution,
    RegistrationAssessment,
    RegistrationResult,
    ResidualAlignmentEvidence,
    SceneAcquisitionEvidence,
    projected_pixel_area_square_metres,
)
from satquery.processing.quality import SCL_CLASS_LABELS

SHAPE = (6, 6)
SCENES = (
    ViewerSceneIdentity(
        provider="earth-search",
        collection="sentinel-2-c1-l2a",
        item="synthetic-before",
    ),
    ViewerSceneIdentity(
        provider="earth-search",
        collection="sentinel-2-c1-l2a",
        item="synthetic-after",
    ),
)


def _request() -> PreparationRequest:
    return PreparationRequest.model_validate(
        {
            "scenes": [scene.model_dump(mode="json") for scene in SCENES],
            "aoi": {
                "type": "Polygon",
                "coordinates": [[[3.0, 1.0], [3.01, 1.0], [3.01, 1.01], [3.0, 1.01], [3.0, 1.0]]],
            },
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
                "max_output_pixels": 1000,
            },
        }
    )


def _quality(
    aoi: np.ndarray,
    valid: np.ndarray,
    *,
    cloud: tuple[int, int] | None = None,
    shadow: tuple[int, int] | None = None,
) -> HarmonizedQualityMasks:
    empty = np.zeros(SHAPE, dtype=bool)
    clouds = empty.copy()
    shadows = empty.copy()
    if cloud is not None:
        clouds[cloud] = True
    if shadow is not None:
        shadows[shadow] = True
    missing = aoi & ~valid
    outside = ~aoi
    excluded = outside | missing | clouds | shadows
    usable = aoi & valid & ~excluded
    scl = np.full(SHAPE, 4, dtype=np.uint8)
    scl[outside | missing] = 0
    scl[clouds] = 9
    scl[shadows] = 3
    return HarmonizedQualityMasks(
        quality_information="available",
        unavailable_reason=None,
        source_asset="scl",
        processing_baseline="05.11",
        catalogue_scene_cloud_percent=10.0,
        scl_classes=scl,
        class_labels=dict(SCL_CLASS_LABELS),
        outside_aoi=outside,
        missing_or_invalid=missing,
        clouds_or_cirrus=clouds,
        cloud_shadows=shadows,
        cast_shadows=empty.copy(),
        snow_or_ice=empty.copy(),
        unknown_quality=empty.copy(),
        usable=usable,
        excluded_any=excluded,
    )


def _scene(
    index: int,
    aoi: np.ndarray,
    valid: np.ndarray,
    *,
    cloud: tuple[int, int] | None = None,
    shadow: tuple[int, int] | None = None,
) -> HarmonizedScene:
    data = np.full((3, *SHAPE), 0.2 + index * 0.01, dtype=np.float32)
    band_validity = np.repeat(valid[np.newaxis, :, :], 3, axis=0)
    data[~band_validity] = np.nan
    identity = ResolvedImageryAssetIdentity(
        scene=SCENES[index], asset="synthetic", asset_version="v1"
    )
    bands = tuple(
        BandCalibration(
            source=identity,
            role=role,
            band_name=role,
            band_index=band_index,
            units="1",
            native_resolution_metres=10.0,
            source_nodata=None,
            provider_scale=0.0001,
            provider_offset=0.0,
            applied_scale=0.0001,
            applied_offset=0.0,
            method="metadata_scale_offset",
        )
        for band_index, role in enumerate(("red", "green", "blue"), start=1)
    )
    return HarmonizedScene(
        scene=SCENES[index],
        data=data,
        band_validity=band_validity,
        valid_data=valid,
        quality=_quality(aoi, valid, cloud=cloud, shadow=shadow),
        band_order=("red", "green", "blue"),
        bands=bands,
        native_resolutions_metres=(10.0, 10.0, 10.0),
        output_resolution_metres=10.0,
        continuous_resampling="bilinear",
        upsampled=False,
        upsampling_explanation=None,
        coverage=(),
    )


def _grid(
    first_valid: np.ndarray,
    second_valid: np.ndarray,
    *,
    first_cloud: tuple[int, int] | None = None,
    second_shadow: tuple[int, int] | None = None,
) -> CommonGridResult:
    aoi = np.ones(SHAPE, dtype=bool)
    aoi[-1, :] = False
    first = _scene(0, aoi, first_valid, cloud=first_cloud)
    second = _scene(1, aoi, second_valid, shadow=second_shadow)
    return CommonGridResult(
        grid=OutputGrid(
            crs="EPSG:32631",
            transform=(10.0, 0.0, 500000.0, 0.0, -10.0, 1000060.0),
            width=SHAPE[1],
            height=SHAPE[0],
            resolution_metres=(10.0, 10.0),
            bounds=(500000.0, 1000000.0, 500060.0, 1000060.0),
        ),
        aoi_mask=aoi,
        scenes=(first, second),
        joint_valid_data=np.ones(SHAPE, dtype=bool),
        joint_usable=np.ones(SHAPE, dtype=bool),
        pair_coverage=(),
        area_method="projected_pixel_count",
        registration_status="not_assessed",
        registration_explanation="Synthetic common grid.",
        radiometric_harmonization="none",
    )


def _registration(
    grid: CommonGridResult,
    *,
    state: Literal["reliable", "inconclusive", "unsupported"] = "reliable",
    correction_state: Literal["applied", "not_needed", "rejected", "not_supported"] = "not_needed",
) -> RegistrationResult:
    assessment = RegistrationAssessment(
        state=state,
        explanation="Synthetic registration evidence.",
        method="distributed_masked_zncc_integer_translation",
        coordinate_convention="Synthetic moving-to-reference convention.",
        band_role="red",
        estimated_row_shift_pixels=0 if state == "reliable" else None,
        estimated_column_shift_pixels=0 if state == "reliable" else None,
        estimated_x_shift_map_units=0.0 if state == "reliable" else None,
        estimated_y_shift_map_units=0.0 if state == "reliable" else None,
        map_displacement_units="metres",
        patches=(),
        distribution=PatchDistribution(9, 9, 5, 4, 3, 3, (2 / 3, 2 / 3)),
        agreement=EstimateAgreement(5, 5, 1.0, 0.75, 0.0, 0.0, 0.0, state == "reliable"),
        residual=ResidualAlignmentEvidence(4, 1.0, 1.0, 0.0, 0, 0.03, False),
        correction_state=correction_state,
        correction=None,
    )
    return RegistrationResult(grid, assessment, None, None, None, ())


def _evidence(
    *, reversed_dates: bool = False, gap_days: int = 10
) -> tuple[SceneAcquisitionEvidence, ...]:
    first = datetime(2026, 1, 1, tzinfo=UTC)
    second = first + timedelta(days=gap_days)
    if reversed_dates:
        first, second = second, first
    return (
        SceneAcquisitionEvidence(SCENES[0], first, "MSI", "S2A", "L2A"),
        SceneAcquisitionEvidence(SCENES[1], second, "MSI", "S2A", "L2A"),
    )


def test_joint_masks_are_recomputed_from_both_dates_and_actual_qa() -> None:
    first_valid = np.ones(SHAPE, dtype=bool)
    second_valid = np.ones(SHAPE, dtype=bool)
    first_valid[0, 0] = False
    second_valid[0, 1] = False
    grid = _grid(first_valid, second_valid, first_cloud=(1, 1), second_shadow=(1, 2))

    outcome = PairPreparationService().prepare(_request(), grid, _registration(grid), _evidence())

    assert outcome.state == "comparable"
    assert outcome.comparison_allowed
    assert outcome.coverage.aoi_pixels == 30
    assert outcome.coverage.joint_valid_pixels == 28
    assert outcome.coverage.joint_usable_pixels == 26
    assert outcome.coverage.joint_usable_area_square_metres == 2600.0
    assert not outcome.joint_valid[-1].any()
    assert not outcome.joint_usable[0, 0]
    assert not outcome.joint_usable[0, 1]
    assert not outcome.joint_usable[1, 1]
    assert not outcome.joint_usable[1, 2]
    assert grid.joint_valid_data is not None
    assert not np.array_equal(outcome.joint_valid, grid.joint_valid_data)


def test_pair_with_no_actual_valid_overlap_is_explicitly_rejected() -> None:
    first_valid = np.zeros(SHAPE, dtype=bool)
    second_valid = np.zeros(SHAPE, dtype=bool)
    first_valid[:, :3] = True
    second_valid[:, 3:] = True
    grid = _grid(first_valid, second_valid)

    outcome = PairPreparationService().prepare(_request(), grid, _registration(grid), _evidence())

    assert outcome.state == "rejected"
    assert not outcome.comparison_allowed
    assert outcome.coverage.joint_valid_pixels == 0
    assert outcome.coverage.joint_usable_area_square_metres == 0
    assert {reason.code for reason in outcome.reasons} >= {"no_spatial_overlap"}


def test_unreliable_registration_rejects_pair_without_change_output() -> None:
    valid = np.ones(SHAPE, dtype=bool)
    grid = _grid(valid, valid)

    outcome = PairPreparationService().prepare(
        _request(),
        grid,
        _registration(grid, state="inconclusive", correction_state="rejected"),
        _evidence(),
    )

    assert outcome.state == "rejected"
    assert not outcome.comparison_allowed
    assert outcome.coverage.joint_usable_pixels == 30
    assert {reason.code for reason in outcome.reasons} == {"registration_unreliable"}


def test_non_chronological_pair_is_rejected_even_when_pixels_are_usable() -> None:
    valid = np.ones(SHAPE, dtype=bool)
    grid = _grid(valid, valid)

    outcome = PairPreparationService().prepare(
        _request(), grid, _registration(grid), _evidence(reversed_dates=True)
    )

    assert outcome.state == "rejected"
    assert {reason.code for reason in outcome.reasons} == {"dates_not_chronological"}


def test_incompatible_band_order_is_rejected() -> None:
    valid = np.ones(SHAPE, dtype=bool)
    grid = _grid(valid, valid)
    incompatible = replace(grid.scenes[1], band_order=("blue", "green", "red"))
    grid = replace(grid, scenes=(grid.scenes[0], incompatible))

    outcome = PairPreparationService().prepare(_request(), grid, _registration(grid), _evidence())

    assert outcome.state == "rejected"
    assert {reason.code for reason in outcome.reasons} == {"incompatible_bands"}


def test_grid_mismatch_is_rejected_without_attempting_a_plausible_overlap() -> None:
    valid = np.ones(SHAPE, dtype=bool)
    grid = _grid(valid, valid)
    mismatched = replace(grid.scenes[1], output_resolution_metres=20.0)
    grid = replace(grid, scenes=(grid.scenes[0], mismatched))

    outcome = PairPreparationService().prepare(_request(), grid, _registration(grid), _evidence())

    assert outcome.state == "rejected"
    assert outcome.coverage.joint_valid_pixels == 0
    assert {reason.code for reason in outcome.reasons} == {"grid_mismatch"}


def _detect(
    grid: CommonGridResult, registration: RegistrationResult | None = None
) -> OpticalChangeDetectionOutcome:
    registration = registration or _registration(grid)
    pair = PairPreparationService().prepare(_request(), grid, registration, _evidence())
    return OpticalChangeDetector().detect(pair, grid, registration)


def test_change_detector_classifies_unchanged_calibrated_imagery() -> None:
    valid = np.ones(SHAPE, dtype=bool)
    grid = _grid(valid, valid)

    result = _detect(grid)

    assert result.state == "completed"
    assert result.parameters.method == "calibrated_rgb_rms_reflectance_difference"
    assert result.parameters.threshold == 0.05
    assert result.parameters.per_image_normalization is False
    assert result.classification is not None
    assert result.spectral_difference is not None
    assert np.all(result.classification[grid.aoi_mask] == 0)
    assert np.all(result.classification[~grid.aoi_mask] == 255)
    assert [item.pixel_count for item in result.classes] == [30, 0, 0]
    assert [item.area_square_metres for item in result.classes] == [3000.0, 0.0, 0.0]


def test_change_detector_measures_known_synthetic_spectral_change() -> None:
    valid = np.ones(SHAPE, dtype=bool)
    grid = _grid(valid, valid)
    after_data = grid.scenes[1].data.copy()
    after_data[:, 1:3, 2:4] = np.asarray([0.31, 0.41, 0.51])[:, None, None]
    after = replace(grid.scenes[1], data=after_data)
    grid = replace(grid, scenes=(grid.scenes[0], after))

    result = _detect(grid)

    assert result.state == "completed"
    assert result.classification is not None
    assert np.all(result.classification[1:3, 2:4] == 1)
    assert [item.pixel_count for item in result.classes] == [26, 4, 0]
    assert [item.area_square_metres for item in result.classes] == [2600.0, 400.0, 0.0]
    assert "does not determine a cause" in result.interpretation


def test_change_detector_keeps_cloud_nodata_and_outside_aoi_unknown() -> None:
    first_valid = np.ones(SHAPE, dtype=bool)
    second_valid = np.ones(SHAPE, dtype=bool)
    first_valid[0, 0] = False
    second_valid[0, 1] = False
    grid = _grid(first_valid, second_valid, first_cloud=(1, 1), second_shadow=(1, 2))
    after = replace(grid.scenes[1], data=grid.scenes[1].data + np.float32(0.10))
    grid = replace(grid, scenes=(grid.scenes[0], after))

    result = _detect(grid)

    assert result.state == "completed"
    assert result.classification is not None
    assert result.spectral_difference is not None
    for row, column in ((0, 0), (0, 1), (1, 1), (1, 2), (5, 3)):
        assert result.classification[row, column] == 255
        assert np.isnan(result.spectral_difference[row, column])
    assert [item.pixel_count for item in result.classes] == [0, 26, 4]
    assert [item.area_square_metres for item in result.classes] == [0.0, 2600.0, 400.0]


def test_change_detector_rejects_poor_registration_without_plausible_output() -> None:
    valid = np.ones(SHAPE, dtype=bool)
    grid = _grid(valid, valid)
    registration = _registration(grid, state="inconclusive", correction_state="rejected")

    result = _detect(grid, registration)

    assert result.state == "insufficient_evidence"
    assert result.classification is None
    assert result.spectral_difference is None
    assert result.classes == ()
    assert {reason.code for reason in result.reasons} == {"registration_unreliable"}


def test_change_detector_reports_no_usable_overlap_as_insufficient_evidence() -> None:
    first_valid = np.zeros(SHAPE, dtype=bool)
    second_valid = np.zeros(SHAPE, dtype=bool)
    first_valid[:, :3] = True
    second_valid[:, 3:] = True
    grid = _grid(first_valid, second_valid)

    result = _detect(grid)

    assert result.state == "insufficient_evidence"
    assert result.classification is None
    assert {reason.code for reason in result.reasons} >= {"no_spatial_overlap"}


def test_change_detector_rejects_tampered_pair_mask() -> None:
    valid = np.ones(SHAPE, dtype=bool)
    grid = _grid(valid, valid)
    registration = _registration(grid)
    pair = PairPreparationService().prepare(_request(), grid, registration, _evidence())
    tampered_mask = pair.joint_usable.copy()
    tampered_mask[0, 0] = False
    pair = replace(pair, joint_usable=tampered_mask)

    result = OpticalChangeDetector().detect(pair, grid, registration)

    assert result.state == "failed"
    assert result.classification is None
    assert {reason.code for reason in result.reasons} == {"pair_integrity_failed"}


def test_change_summary_uses_joint_valid_denominator_and_reports_unknown_separately() -> None:
    first_valid = np.ones(SHAPE, dtype=bool)
    second_valid = np.ones(SHAPE, dtype=bool)
    first_valid[0, 0] = False
    second_valid[0, 1] = False
    grid = _grid(first_valid, second_valid, first_cloud=(1, 1), second_shadow=(1, 2))
    after = replace(grid.scenes[1], data=grid.scenes[1].data + np.float32(0.10))
    grid = replace(grid, scenes=(grid.scenes[0], after))
    registration = _registration(grid)
    pair = PairPreparationService().prepare(_request(), grid, registration, _evidence())
    detection = OpticalChangeDetector().detect(pair, grid, registration)

    summary = ChangeSummaryService().summarize(_request(), pair, detection, grid, registration)

    assert summary.area.pixel_area_square_metres == 100.0
    assert summary.area.joint_valid_observed_area_square_metres == 2800.0
    assert summary.area.changed_area_square_metres == 2600.0
    assert summary.area.changed_percent_of_joint_valid_observed_area == pytest.approx(100 * 26 / 28)
    assert summary.area.unknown_area_square_metres == 400.0
    assert summary.area.unknown_percent_of_aoi == pytest.approx(100 * 4 / 30)
    assert summary.cause_or_land_cover_category == "not_determined"
    assert summary.directional_measurements == ()


def test_change_summary_statements_are_computed_noncausal_and_warn_from_actual_masks() -> None:
    valid = np.ones(SHAPE, dtype=bool)
    grid = _grid(valid, valid, first_cloud=(1, 1))
    after_data = grid.scenes[1].data.copy()
    after_data[:, 2, 2] += np.float32(0.10)
    grid = replace(grid, scenes=(grid.scenes[0], replace(grid.scenes[1], data=after_data)))
    registration = _registration(grid)
    evidence = _evidence(gap_days=90)
    pair = PairPreparationService().prepare(_request(), grid, registration, evidence)
    detection = OpticalChangeDetector().detect(pair, grid, registration)

    summary = ChangeSummaryService().summarize(_request(), pair, detection, grid, registration)

    prose = " ".join(summary.statements)
    warning_codes = {warning.code for warning in summary.warnings}
    assert summary.aoi == _request().aoi
    assert summary.acquired_at == (evidence[0].acquired_at, evidence[1].acquired_at)
    assert "2026-01-01" in prose and "2026-04-01" in prose
    assert "100.00 m²" in prose
    assert "joint-valid observed area" in prose
    assert "cause or land-cover category is not determined" in prose
    assert "building" not in prose.lower() and "vegetation gain" not in prose.lower()
    assert warning_codes >= {
        "before_cloud_or_shadow_exclusion",
        "unknown_area_present",
        "seasonal_context_not_isolated",
    }


def test_muddy_flood_like_spectral_change_never_becomes_a_building_claim() -> None:
    """Brown RGB change is measurable appearance change, not evidence of its cause."""
    valid = np.ones(SHAPE, dtype=bool)
    grid = _grid(valid, valid)
    after_data = grid.scenes[1].data.copy()
    after_data[:, 1:4, 1:5] = np.asarray([0.34, 0.24, 0.14])[:, None, None]
    grid = replace(grid, scenes=(grid.scenes[0], replace(grid.scenes[1], data=after_data)))
    registration = _registration(grid)
    pair = PairPreparationService().prepare(_request(), grid, registration, _evidence())
    detection = OpticalChangeDetector().detect(pair, grid, registration)

    summary = ChangeSummaryService().summarize(_request(), pair, detection, grid, registration)

    assert summary.area.changed_pixel_count == 12
    assert summary.area.changed_area_square_metres == 1200.0
    assert summary.cause_or_land_cover_category == "not_determined"
    combined_text = " ".join((*summary.statements, *(item.statement for item in summary.warnings)))
    for unsupported_cause in ("new building", "construction", "flood", "mud"):
        assert unsupported_cause not in combined_text.lower()


def test_pixel_area_uses_projected_crs_units_and_rejects_degrees() -> None:
    metre_grid = _grid(np.ones(SHAPE, dtype=bool), np.ones(SHAPE, dtype=bool)).grid
    assert projected_pixel_area_square_metres(metre_grid) == 100.0

    feet_grid = OutputGrid.model_construct(
        crs="EPSG:2277",
        transform=(10.0, 0.0, 3000000.0, 0.0, -10.0, 10000000.0),
        width=1,
        height=1,
        resolution_metres=(10.0, 10.0),
        bounds=(3000000.0, 9999990.0, 3000010.0, 10000000.0),
        pixel_interpretation="area",
    )
    assert projected_pixel_area_square_metres(feet_grid) == pytest.approx(9.2903411613)

    geographic_grid = OutputGrid.model_construct(
        crs="EPSG:4326",
        transform=(0.001, 0.0, 77.5, 0.0, -0.001, 13.0),
        width=1,
        height=1,
        resolution_metres=(0.001, 0.001),
        bounds=(77.5, 12.999, 77.501, 13.0),
        pixel_interpretation="area",
    )
    with pytest.raises(AreaMeasurementError, match="degrees are not metres"):
        projected_pixel_area_square_metres(geographic_grid)
