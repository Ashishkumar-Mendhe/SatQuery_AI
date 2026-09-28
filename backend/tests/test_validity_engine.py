from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

from satquery.api.schemas.processing import OutputGrid, PreparationRequest
from satquery.api.schemas.viewer import ResolvedImageryAssetIdentity, ViewerSceneIdentity
from satquery.processing import (
    BandCalibration,
    CommonGridResult,
    EstimateAgreement,
    HarmonizedQualityMasks,
    HarmonizedScene,
    PatchDistribution,
    RegistrationAssessment,
    RegistrationResult,
    ResidualAlignmentEvidence,
    SceneAcquisitionEvidence,
    ScientificCheck,
    ScientificValidityContext,
    ScientificValidityEngine,
    ScientificValidityReport,
)
from satquery.processing.quality import SCL_CLASS_LABELS

SHAPE = (100, 100)
SCENES = (
    ViewerSceneIdentity(
        provider="earth-search",
        collection="sentinel-2-c1-l2a",
        item="synthetic-validity-a",
    ),
    ViewerSceneIdentity(
        provider="earth-search",
        collection="sentinel-2-c1-l2a",
        item="synthetic-validity-b",
    ),
)


def _request(
    *, pair: bool, bands: tuple[str, ...] = ("red", "green", "blue")
) -> PreparationRequest:
    return PreparationRequest.model_validate(
        {
            "scenes": [scene.model_dump(mode="json") for scene in SCENES[: 2 if pair else 1]],
            "aoi": {
                "type": "Polygon",
                "coordinates": [[[3, 1], [3.01, 1], [3.01, 1.01], [3, 1.01], [3, 1]]],
            },
            "required_bands": [{"role": role, "common_name": role} for role in bands],
            "intended_task": "optical_pair" if pair else "optical_single_scene",
            "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
            "options": {
                "grid_policy": "common_utm",
                "target_resolution_metres": 10.0,
                "continuous_resampling": "bilinear",
                "max_output_pixels": 100_000,
            },
        }
    )


def _mask(count: int, *, offset: int = 0) -> np.ndarray:
    flat = np.zeros(SHAPE[0] * SHAPE[1], dtype=bool)
    flat[offset : offset + count] = True
    return flat.reshape(SHAPE)


def _scene(
    index: int,
    *,
    valid_percent: float = 100,
    usable_percent: float = 80,
    cloud_percent: float = 0,
    shadow_percent: float = 0,
    native_resolution: float = 10,
    upsampled: bool = False,
    calibration: bool = True,
    quality_available: bool = True,
) -> HarmonizedScene:
    pixels = SHAPE[0] * SHAPE[1]
    valid = _mask(round(pixels * valid_percent / 100))
    usable_count = round(pixels * usable_percent / 100)
    cloud_count = round(pixels * cloud_percent / 100)
    shadow_count = round(pixels * shadow_percent / 100)
    usable = _mask(usable_count) & valid
    clouds = _mask(cloud_count, offset=usable_count)
    shadows = _mask(shadow_count, offset=usable_count + cloud_count)
    missing = ~valid
    empty = np.zeros(SHAPE, dtype=bool)
    classes = np.full(SHAPE, 4, dtype=np.uint8)
    classes[clouds] = 9
    classes[shadows] = 3
    classes[missing] = 0
    quality = HarmonizedQualityMasks(
        quality_information="available" if quality_available else "unavailable",
        unavailable_reason=None if quality_available else "Synthetic QA missing.",
        source_asset="scl" if quality_available else None,
        processing_baseline="05.11",
        catalogue_scene_cloud_percent=None,
        scl_classes=classes,
        class_labels=dict(SCL_CLASS_LABELS),
        outside_aoi=empty.copy(),
        missing_or_invalid=missing,
        clouds_or_cirrus=clouds,
        cloud_shadows=shadows,
        cast_shadows=empty.copy(),
        snow_or_ice=empty.copy(),
        unknown_quality=empty.copy() if quality_available else np.ones(SHAPE, dtype=bool),
        usable=usable if quality_available else empty.copy(),
        excluded_any=~usable,
    )
    identity = ResolvedImageryAssetIdentity(
        scene=SCENES[index], asset="synthetic", asset_version="v1"
    )
    bands = (
        tuple(
            BandCalibration(
                source=identity,
                role=role,
                band_name=role,
                band_index=band_index,
                units="1",
                native_resolution_metres=native_resolution,
                source_nodata=None,
                provider_scale=1.0,
                provider_offset=0.0,
                applied_scale=1.0,
                applied_offset=0.0,
                method="identity",
            )
            for band_index, role in enumerate(("red", "green", "blue"), start=1)
        )
        if calibration
        else ()
    )
    data = np.full((3, *SHAPE), 0.2, dtype=np.float32)
    data[:, ~valid] = np.nan
    return HarmonizedScene(
        scene=SCENES[index],
        data=data,
        band_validity=np.stack([valid, valid, valid]),
        valid_data=valid,
        quality=quality,
        band_order=("red", "green", "blue"),
        bands=bands,
        native_resolutions_metres=(native_resolution,) * 3,
        output_resolution_metres=10.0,
        continuous_resampling="bilinear",
        upsampled=upsampled,
        upsampling_explanation=(
            "Synthetic upsampling does not create detail." if upsampled else None
        ),
        coverage=(),
    )


def _grid(*scenes: HarmonizedScene) -> CommonGridResult:
    aoi = np.ones(SHAPE, dtype=bool)
    joint_valid = None
    joint_usable = None
    if len(scenes) == 2:
        joint_valid = scenes[0].valid_data & scenes[1].valid_data
        joint_usable = scenes[0].quality.usable & scenes[1].quality.usable
    return CommonGridResult(
        grid=OutputGrid(
            crs="EPSG:32631",
            transform=(10.0, 0.0, 500_000.0, 0.0, -10.0, 1_001_000.0),
            width=100,
            height=100,
            resolution_metres=(10.0, 10.0),
            bounds=(500_000.0, 1_000_000.0, 501_000.0, 1_001_000.0),
        ),
        aoi_mask=aoi,
        scenes=tuple(scenes),
        joint_valid_data=joint_valid,
        joint_usable=joint_usable,
        pair_coverage=(),
        area_method="projected_pixel_count",
        registration_status="not_assessed",
        registration_explanation="Synthetic common grid.",
        radiometric_harmonization="none",
    )


def _evidence(
    *, pair: bool, different_platform: bool = False
) -> tuple[SceneAcquisitionEvidence, ...]:
    start = datetime(2026, 1, 10, tzinfo=UTC)
    return tuple(
        SceneAcquisitionEvidence(
            scene=scene,
            acquired_at=start + timedelta(days=10 * index),
            sensor="sentinel-2-msi",
            platform=("sentinel-2b" if different_platform and index else "sentinel-2a"),
            processing_level="L2A",
        )
        for index, scene in enumerate(SCENES[: 2 if pair else 1])
    )


def _registration(pair: CommonGridResult) -> RegistrationResult:
    assessment = RegistrationAssessment(
        state="reliable",
        explanation="Synthetic distributed evidence supports zero translation.",
        method="distributed_masked_zncc_integer_translation",
        coordinate_convention="Synthetic moving-to-reference convention.",
        band_role="red",
        estimated_row_shift_pixels=0,
        estimated_column_shift_pixels=0,
        estimated_x_shift_map_units=0.0,
        estimated_y_shift_map_units=0.0,
        map_displacement_units="metres",
        patches=(),
        distribution=PatchDistribution(9, 9, 5, 4, 3, 3, (2 / 3, 2 / 3)),
        agreement=EstimateAgreement(5, 5, 1.0, 0.75, 0.0, 0.0, 0.0, True),
        residual=ResidualAlignmentEvidence(4, 1.0, 1.0, 0.0, 0, 0.03, False),
        correction_state="not_needed",
        correction=None,
    )
    return RegistrationResult(pair, assessment, None, None, None, ())


def _context(
    *,
    pair: bool,
    grid: CommonGridResult | None,
    registration: RegistrationResult | None = None,
    evidence: tuple[SceneAcquisitionEvidence, ...] | None = None,
    scale: float | None = 30.0,
    bands: tuple[str, ...] = ("red", "green", "blue"),
) -> ScientificValidityContext:
    return ScientificValidityContext(
        request=_request(pair=pair, bands=bands),
        common_grid=grid,
        registration=registration,
        acquisition_evidence=_evidence(pair=pair) if evidence is None else evidence,
        requested_spatial_scale_metres=scale,
    )


def _check(report: ScientificValidityReport, check_id: str) -> ScientificCheck:
    return next(item for item in report.checks if item.check_id == check_id)


def test_valid_single_scene_is_ready_without_affecting_viewing_or_search() -> None:
    grid = _grid(_scene(0))
    report = ScientificValidityEngine().evaluate(_context(pair=False, grid=grid))

    assert report.profile.profile_id == "sentinel-2-l2a-single-scene-validity-v1"
    assert report.readiness == "ready"
    assert report.threshold_version == "provisional-engineering-v1"
    assert report.thresholds_are_provisional_engineering_limits
    assert report.minimum_supported_spatial_scale_metres == 30.0
    assert not report.map_viewing_affected
    assert not report.catalogue_search_affected
    assert _check(report, "registration_evidence").outcome == "not_applicable"


def test_valid_pair_is_ready_when_registration_and_temporal_evidence_pass() -> None:
    grid = _grid(_scene(0), _scene(1))
    report = ScientificValidityEngine().evaluate(
        _context(pair=True, grid=grid, registration=_registration(grid))
    )

    assert report.profile.profile_id == "sentinel-2-l2a-pair-comparison-validity-v1"
    assert report.readiness == "ready"
    assert _check(report, "pair_valid_overlap").outcome == "pass"
    assert _check(report, "pair_joint_usable_aoi").outcome == "pass"
    assert _check(report, "registration_evidence").outcome == "pass"
    assert _check(report, "acquisition_dates").outcome == "pass"


def test_missing_required_evidence_prohibits_positive_readiness() -> None:
    report = ScientificValidityEngine().evaluate(
        _context(pair=False, grid=None, evidence=(), scale=None)
    )

    assert report.readiness == "unknown"
    assert "processing_level" in report.blocking_check_ids
    assert "calibration_availability" in report.blocking_check_ids
    assert "requested_spatial_scale" in report.blocking_check_ids
    assert all(
        check.measured_value is None for check in report.checks if check.outcome == "unknown"
    )


def test_inclusive_boundary_values_pass_and_below_scale_fails() -> None:
    scene = _scene(
        0,
        valid_percent=95,
        usable_percent=60,
        cloud_percent=20,
        shadow_percent=15,
    )
    grid = _grid(scene)
    engine = ScientificValidityEngine()
    boundary = engine.evaluate(_context(pair=False, grid=grid, scale=30.0))

    assert boundary.readiness == "ready"
    assert _check(boundary, "scene_1_usable_aoi_coverage").outcome == "pass"
    assert _check(boundary, "scene_1_cloud_coverage").outcome == "pass"
    assert _check(boundary, "scene_1_shadow_coverage").outcome == "pass"
    assert _check(boundary, "scene_1_missing_data_coverage").outcome == "pass"
    assert _check(boundary, "requested_spatial_scale").outcome == "pass"

    below = engine.evaluate(_context(pair=False, grid=grid, scale=29.9))
    assert below.readiness == "not_ready"
    assert _check(below, "requested_spatial_scale").outcome == "fail"
    assert "detection guarantee" not in below.readiness_reason


def test_failed_required_check_wins_over_other_passing_checks() -> None:
    grid = _grid(_scene(0))
    report = ScientificValidityEngine().evaluate(
        _context(pair=False, grid=grid, bands=("red", "green"))
    )

    assert _check(report, "required_bands").outcome == "fail"
    assert _check(report, "scene_1_valid_aoi_coverage").outcome == "pass"
    assert report.readiness == "not_ready"
    assert "required_bands" in report.blocking_check_ids


def test_pair_profile_requires_registration_and_keeps_contextual_differences_limited() -> None:
    grid = _grid(_scene(0), _scene(1))
    missing_registration = ScientificValidityEngine().evaluate(
        _context(pair=True, grid=grid, registration=None)
    )

    assert missing_registration.readiness == "unknown"
    assert _check(missing_registration, "registration_evidence").outcome == "unknown"

    contextual = ScientificValidityEngine().evaluate(
        _context(
            pair=True,
            grid=grid,
            registration=_registration(grid),
            evidence=_evidence(pair=True, different_platform=True),
        )
    )
    assert contextual.readiness == "limited"
    assert _check(contextual, "platform_context").outcome == "warning"
    assert not contextual.blocking_check_ids
