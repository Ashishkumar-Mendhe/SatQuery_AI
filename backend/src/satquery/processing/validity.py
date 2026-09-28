from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import numpy as np

from satquery.api.schemas.processing import PreparationRequest
from satquery.api.schemas.viewer import ViewerSceneIdentity
from satquery.processing.grid import CommonGridResult, HarmonizedScene
from satquery.processing.registration import RegistrationResult

CheckOutcome = Literal["pass", "warning", "fail", "unknown", "not_applicable"]
ReadinessState = Literal["ready", "limited", "not_ready", "unknown", "unsupported"]
CheckCategory = Literal[
    "bands",
    "processing",
    "calibration",
    "coverage",
    "quality",
    "resolution",
    "registration",
    "compatibility",
    "temporal",
    "geofeasibility",
]


@dataclass(frozen=True, slots=True)
class ScientificValidityThresholds:
    version: str = "provisional-engineering-v1"
    min_valid_aoi_percent_pass: float = 80.0
    min_valid_aoi_percent_warning: float = 60.0
    min_usable_aoi_percent_pass: float = 60.0
    min_usable_aoi_percent_warning: float = 30.0
    max_cloud_aoi_percent_pass: float = 20.0
    max_cloud_aoi_percent_warning: float = 40.0
    max_shadow_aoi_percent_pass: float = 15.0
    max_shadow_aoi_percent_warning: float = 30.0
    max_missing_aoi_percent_pass: float = 5.0
    max_missing_aoi_percent_warning: float = 20.0
    min_pair_valid_overlap_percent_pass: float = 80.0
    min_pair_valid_overlap_percent_warning: float = 60.0
    min_pair_usable_aoi_percent_pass: float = 50.0
    min_pair_usable_aoi_percent_warning: float = 25.0
    native_resolution_metres_pass: float = 10.0
    native_resolution_metres_warning: float = 20.0
    supported_scale_native_pixel_multiplier: float = 3.0
    temporal_interval_warning_days: float = 365.0
    seasonal_day_of_year_warning_days: float = 45.0

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("threshold version must not be empty")
        minimum_pairs = (
            (self.min_valid_aoi_percent_pass, self.min_valid_aoi_percent_warning),
            (self.min_usable_aoi_percent_pass, self.min_usable_aoi_percent_warning),
            (
                self.min_pair_valid_overlap_percent_pass,
                self.min_pair_valid_overlap_percent_warning,
            ),
            (
                self.min_pair_usable_aoi_percent_pass,
                self.min_pair_usable_aoi_percent_warning,
            ),
        )
        maximum_pairs = (
            (self.max_cloud_aoi_percent_pass, self.max_cloud_aoi_percent_warning),
            (self.max_shadow_aoi_percent_pass, self.max_shadow_aoi_percent_warning),
            (self.max_missing_aoi_percent_pass, self.max_missing_aoi_percent_warning),
            (self.native_resolution_metres_pass, self.native_resolution_metres_warning),
        )
        if any(not 0 <= warning <= passed <= 100 for passed, warning in minimum_pairs):
            raise ValueError("minimum percentage thresholds require 0 <= warning <= pass <= 100")
        if any(not 0 <= passed <= warning for passed, warning in maximum_pairs):
            raise ValueError("maximum thresholds require 0 <= pass <= warning")
        if self.supported_scale_native_pixel_multiplier < 1:
            raise ValueError("supported scale multiplier must be at least one native pixel")


@dataclass(frozen=True, slots=True)
class ValidityTaskProfile:
    profile_id: str
    version: Literal["1.0"]
    intended_task: Literal["optical_single_scene", "optical_pair"]
    processing_profile: Literal["sentinel-2-l2a-surface-reflectance-v1"]
    required_bands: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    requires_registration: bool


@dataclass(frozen=True, slots=True)
class SceneAcquisitionEvidence:
    scene: ViewerSceneIdentity
    acquired_at: datetime | None
    sensor: str | None
    platform: str | None
    processing_level: str | None

    def __post_init__(self) -> None:
        if self.acquired_at is not None:
            if self.acquired_at.tzinfo is None or self.acquired_at.utcoffset() is None:
                raise ValueError("acquired_at must include a UTC offset")
            object.__setattr__(self, "acquired_at", self.acquired_at.astimezone(UTC))


@dataclass(frozen=True, slots=True)
class ScientificCheck:
    check_id: str
    category: CheckCategory
    outcome: CheckOutcome
    required: bool
    measured_value: float | None
    measured_text: str | None
    units: str | None
    denominator_name: str | None
    denominator_value: float | None
    threshold_description: str
    reason: str
    corrective_action: str | None
    evidence_source: str
    provisional_threshold: bool


@dataclass(frozen=True, slots=True)
class ScientificValidityContext:
    request: PreparationRequest
    common_grid: CommonGridResult | None
    registration: RegistrationResult | None
    acquisition_evidence: tuple[SceneAcquisitionEvidence, ...]
    requested_spatial_scale_metres: float | None

    def __post_init__(self) -> None:
        if self.requested_spatial_scale_metres is not None and (
            not math.isfinite(self.requested_spatial_scale_metres)
            or self.requested_spatial_scale_metres <= 0
        ):
            raise ValueError("requested_spatial_scale_metres must be positive and finite")


@dataclass(frozen=True, slots=True)
class ScientificValidityReport:
    profile: ValidityTaskProfile
    threshold_version: str
    thresholds_are_provisional_engineering_limits: Literal[True]
    checks: tuple[ScientificCheck, ...]
    readiness: ReadinessState
    readiness_reason: str
    blocking_check_ids: tuple[str, ...]
    warning_check_ids: tuple[str, ...]
    minimum_supported_spatial_scale_metres: float | None
    requested_spatial_scale_metres: float | None
    map_viewing_affected: Literal[False]
    catalogue_search_affected: Literal[False]


_PROFILES: dict[str, ValidityTaskProfile] = {
    "optical_single_scene": ValidityTaskProfile(
        profile_id="sentinel-2-l2a-single-scene-validity-v1",
        version="1.0",
        intended_task="optical_single_scene",
        processing_profile="sentinel-2-l2a-surface-reflectance-v1",
        required_bands=("red", "green", "blue"),
        required_capabilities=(
            "calibrated_surface_reflectance",
            "aoi_validity",
            "sentinel_2_scene_classification",
            "spatial_scale_support",
        ),
        requires_registration=False,
    ),
    "optical_pair": ValidityTaskProfile(
        profile_id="sentinel-2-l2a-pair-comparison-validity-v1",
        version="1.0",
        intended_task="optical_pair",
        processing_profile="sentinel-2-l2a-surface-reflectance-v1",
        required_bands=("red", "green", "blue"),
        required_capabilities=(
            "calibrated_surface_reflectance",
            "aoi_validity",
            "sentinel_2_scene_classification",
            "joint_usable_overlap",
            "registration_evidence",
            "temporal_context",
            "spatial_scale_support",
        ),
        requires_registration=True,
    ),
}


class ScientificValidityEngine:
    """Deterministic, task-scoped quality and geofeasibility evaluation."""

    def __init__(self, thresholds: ScientificValidityThresholds | None = None) -> None:
        self._thresholds = thresholds or ScientificValidityThresholds()

    def evaluate(self, context: ScientificValidityContext) -> ScientificValidityReport:
        profile = _PROFILES.get(context.request.intended_task)
        if profile is None or context.request.processing_profile != profile.processing_profile:
            return _unsupported_report(context, self._thresholds)
        checks: list[ScientificCheck] = []
        grid = context.common_grid
        checks.append(_required_bands_check(context, profile))
        checks.append(_processing_level_check(context, profile))
        checks.append(_calibration_check(context, profile))
        checks.append(_sensor_product_check(context, profile))
        checks.extend(_acquisition_checks(context, profile, self._thresholds))
        if grid is None:
            checks.extend(_missing_grid_checks(profile))
            minimum_scale = None
        else:
            scenes, joint_valid, joint_usable = _effective_outputs(context)
            checks.extend(_scene_checks(scenes, grid, self._thresholds))
            checks.append(_native_resolution_check(scenes, profile, self._thresholds))
            checks.append(_upsampling_check(scenes))
            minimum_scale = _minimum_supported_scale(scenes, profile, self._thresholds)
            checks.append(_spatial_scale_check(context, minimum_scale, self._thresholds))
            if profile.intended_task == "optical_pair":
                checks.extend(
                    _pair_checks(
                        context,
                        grid,
                        joint_valid,
                        joint_usable,
                        self._thresholds,
                    )
                )
            else:
                checks.append(_not_applicable_registration())
        return _report(context, profile, tuple(checks), minimum_scale, self._thresholds)


def _required_bands_check(
    context: ScientificValidityContext, profile: ValidityTaskProfile
) -> ScientificCheck:
    requested = {band.role for band in context.request.required_bands}
    missing = sorted(set(profile.required_bands) - requested)
    return _categorical_check(
        "required_bands",
        "bands",
        "fail" if missing else "pass",
        required=True,
        measured_text=("missing: " + ", ".join(missing))
        if missing
        else ", ".join(sorted(requested)),
        threshold=f"must include roles: {', '.join(profile.required_bands)}",
        reason=(
            "Required task-profile bands are missing."
            if missing
            else "All task-profile bands are requested."
        ),
        corrective=(
            "Prepare the missing required bands through the trusted adapter." if missing else None
        ),
        source="preparation_request.required_bands",
    )


def _processing_level_check(
    context: ScientificValidityContext, profile: ValidityTaskProfile
) -> ScientificCheck:
    evidence = _ordered_evidence(context)
    levels = [item.processing_level for item in evidence]
    if len(evidence) != len(context.request.scenes) or any(level is None for level in levels):
        return _unknown_check(
            "processing_level",
            "processing",
            required=True,
            threshold="every scene must be Sentinel-2 Level-2A surface reflectance",
            reason="Processing-level evidence is missing for one or more scenes.",
            corrective="Resolve authoritative processing-level metadata for every scene.",
            source="scene_acquisition_evidence.processing_level",
        )
    valid = all(level == "L2A" for level in levels)
    return _categorical_check(
        "processing_level",
        "processing",
        "pass" if valid else "fail",
        required=True,
        measured_text=", ".join(str(level) for level in levels),
        threshold="every scene must equal L2A",
        reason=(
            "All scenes provide the required surface-reflectance processing level."
            if valid
            else "At least one scene has an unsupported processing level."
        ),
        corrective=None if valid else "Use supported Sentinel-2 L2A products.",
        source="scene_acquisition_evidence.processing_level",
    )


def _calibration_check(
    context: ScientificValidityContext, profile: ValidityTaskProfile
) -> ScientificCheck:
    if context.common_grid is None:
        return _unknown_check(
            "calibration_availability",
            "calibration",
            required=True,
            threshold="every required band must retain finite applied calibration metadata",
            reason="Common-grid scene outputs are unavailable.",
            corrective="Complete trusted calibrated extraction and common-grid preparation.",
            source="6B band calibration metadata",
        )
    missing: list[str] = []
    for scene_index, scene in enumerate(context.common_grid.scenes, start=1):
        metadata = {band.role: band for band in scene.bands}
        for role in profile.required_bands:
            band = metadata.get(role)
            if band is None or not (
                math.isfinite(band.applied_scale) and math.isfinite(band.applied_offset)
            ):
                missing.append(f"scene_{scene_index}:{role}")
    return _categorical_check(
        "calibration_availability",
        "calibration",
        "fail" if missing else "pass",
        required=True,
        measured_text=("missing: " + ", ".join(missing)) if missing else "available",
        threshold="finite applied scale/offset metadata for every required band",
        reason=(
            "Required calibration evidence is missing."
            if missing
            else "Every required band retains applied or identity calibration evidence."
        ),
        corrective=(
            "Re-extract bands with trusted provider calibration metadata." if missing else None
        ),
        source="6B BandCalibration",
    )


def _sensor_product_check(
    context: ScientificValidityContext, profile: ValidityTaskProfile
) -> ScientificCheck:
    evidence = _ordered_evidence(context)
    sensors = [item.sensor for item in evidence]
    scene_compatible = all(
        scene.provider == "earth-search" and scene.collection == "sentinel-2-c1-l2a"
        for scene in context.request.scenes
    )
    if len(evidence) != len(context.request.scenes) or any(sensor is None for sensor in sensors):
        return _unknown_check(
            "sensor_product_compatibility",
            "compatibility",
            required=True,
            threshold="all scenes must be Earth Search Sentinel-2 L2A with Sentinel-2 MSI evidence",
            reason="Sensor evidence is missing for one or more scenes.",
            corrective="Resolve authoritative sensor metadata for every selected scene.",
            source="scene identity and scene_acquisition_evidence.sensor",
        )
    compatible = scene_compatible and all(sensor == "sentinel-2-msi" for sensor in sensors)
    return _categorical_check(
        "sensor_product_compatibility",
        "compatibility",
        "pass" if compatible else "fail",
        required=True,
        measured_text=", ".join(str(sensor) for sensor in sensors),
        threshold="same supported Sentinel-2 MSI / L2A collection",
        reason=(
            "Sensor and product evidence is compatible with the task profile."
            if compatible
            else "The selected scenes are not supported same-profile Sentinel-2 MSI products."
        ),
        corrective=None if compatible else "Use compatible Sentinel-2 MSI Level-2A scenes.",
        source="scene identity and scene_acquisition_evidence.sensor",
    )


def _acquisition_checks(
    context: ScientificValidityContext,
    profile: ValidityTaskProfile,
    thresholds: ScientificValidityThresholds,
) -> tuple[ScientificCheck, ...]:
    evidence = _ordered_evidence(context)
    dates = [item.acquired_at for item in evidence]
    if len(evidence) != len(context.request.scenes) or any(date is None for date in dates):
        date_check = _unknown_check(
            "acquisition_dates",
            "temporal",
            required=True,
            threshold="authoritative UTC acquisition time for every scene",
            reason="Acquisition-time evidence is missing.",
            corrective="Resolve authoritative acquisition timestamps for every scene.",
            source="scene_acquisition_evidence.acquired_at",
        )
        if profile.intended_task == "optical_pair":
            return (date_check, _unknown_temporal_context())
        return (date_check, _not_applicable_temporal_context())
    known_dates = [date for date in dates if date is not None]
    if profile.intended_task == "optical_single_scene":
        return (
            _categorical_check(
                "acquisition_dates",
                "temporal",
                "pass",
                required=True,
                measured_text=known_dates[0].isoformat(),
                threshold="one authoritative UTC acquisition time",
                reason="The scene acquisition time is available.",
                corrective=None,
                source="scene_acquisition_evidence.acquired_at",
            ),
            _not_applicable_temporal_context(),
        )
    first, second = known_dates
    if second <= first:
        order = _categorical_check(
            "acquisition_dates",
            "temporal",
            "fail",
            required=True,
            measured_text=f"{first.isoformat()} -> {second.isoformat()}",
            threshold="scene A acquisition must precede scene B",
            reason="Pair acquisition order is not strictly chronological.",
            corrective="Order the distinct scenes from earlier A to later B.",
            source="scene_acquisition_evidence.acquired_at",
        )
        return (order, _unknown_temporal_context())
    interval_days = (second - first).total_seconds() / 86_400
    order = _categorical_check(
        "acquisition_dates",
        "temporal",
        "pass",
        required=True,
        measured_text=f"{first.isoformat()} -> {second.isoformat()}",
        threshold="scene A acquisition must precede scene B",
        reason="Pair acquisition order is strictly chronological.",
        corrective=None,
        source="scene_acquisition_evidence.acquired_at",
    )
    doy_delta = _circular_day_of_year_difference(first, second)
    temporal_warning = (
        interval_days > thresholds.temporal_interval_warning_days
        or doy_delta > thresholds.seasonal_day_of_year_warning_days
    )
    temporal = ScientificCheck(
        check_id="temporal_context",
        category="temporal",
        outcome="warning" if temporal_warning else "pass",
        required=False,
        measured_value=interval_days,
        measured_text=f"seasonal day-of-year separation: {doy_delta:.1f} days",
        units="days",
        denominator_name=None,
        denominator_value=None,
        threshold_description=(
            f"warning when interval > {thresholds.temporal_interval_warning_days:g} days or "
            f"seasonal separation > {thresholds.seasonal_day_of_year_warning_days:g} days"
        ),
        reason=(
            "Temporal/seasonal differences are contextual limitations and may affect appearance."
            if temporal_warning
            else "The interval is within provisional temporal-context warning thresholds."
        ),
        corrective_action=(
            "Prefer seasonally comparable acquisitions or explicitly control for seasonal effects."
            if temporal_warning
            else None
        ),
        evidence_source="authoritative acquisition timestamps",
        provisional_threshold=True,
    )
    return order, temporal


def _scene_checks(
    scenes: tuple[HarmonizedScene, ...],
    grid: CommonGridResult,
    thresholds: ScientificValidityThresholds,
) -> tuple[ScientificCheck, ...]:
    checks: list[ScientificCheck] = []
    aoi_pixels = int(grid.aoi_mask.sum())
    for index, scene in enumerate(scenes, start=1):
        valid_pixels = int((scene.valid_data & grid.aoi_mask).sum())
        missing_pixels = max(0, aoi_pixels - valid_pixels)
        checks.append(
            _minimum_percent_check(
                f"scene_{index}_valid_aoi_coverage",
                "coverage",
                valid_pixels,
                aoi_pixels,
                thresholds.min_valid_aoi_percent_pass,
                thresholds.min_valid_aoi_percent_warning,
                required=True,
                source="6D scene valid_data mask",
                corrective="Reduce the AOI or select a scene with fuller valid-data coverage.",
            )
        )
        checks.append(
            _maximum_percent_check(
                f"scene_{index}_missing_data_coverage",
                "quality",
                missing_pixels,
                aoi_pixels,
                thresholds.max_missing_aoi_percent_pass,
                thresholds.max_missing_aoi_percent_warning,
                required=True,
                source="6D AOI and valid_data masks",
                corrective="Select a scene with less nodata or reduce the AOI.",
            )
        )
        if scene.quality.quality_information != "available":
            for suffix, reason in (
                ("usable_aoi_coverage", "Usable-pixel quality evidence is unavailable."),
                ("cloud_coverage", "Cloud/cirrus quality evidence is unavailable."),
                ("shadow_coverage", "Shadow quality evidence is unavailable."),
            ):
                checks.append(
                    _unknown_check(
                        f"scene_{index}_{suffix}",
                        "quality",
                        required=True,
                        threshold="actual decoded quality information is required",
                        reason=reason,
                        corrective="Resolve and decode the authoritative Sentinel-2 SCL asset.",
                        source="6C quality_information",
                    )
                )
            continue
        usable_pixels = int((scene.quality.usable & grid.aoi_mask).sum())
        cloud_pixels = int((scene.quality.clouds_or_cirrus & grid.aoi_mask).sum())
        shadow_mask = scene.quality.cloud_shadows | scene.quality.cast_shadows
        shadow_pixels = int((shadow_mask & grid.aoi_mask).sum())
        checks.extend(
            (
                _minimum_percent_check(
                    f"scene_{index}_usable_aoi_coverage",
                    "quality",
                    usable_pixels,
                    aoi_pixels,
                    thresholds.min_usable_aoi_percent_pass,
                    thresholds.min_usable_aoi_percent_warning,
                    required=True,
                    source="6C/6D usable mask",
                    corrective="Select a clearer scene or reduce the AOI.",
                ),
                _maximum_percent_check(
                    f"scene_{index}_cloud_coverage",
                    "quality",
                    cloud_pixels,
                    aoi_pixels,
                    thresholds.max_cloud_aoi_percent_pass,
                    thresholds.max_cloud_aoi_percent_warning,
                    required=True,
                    source="6C cloud/cirrus mask over AOI pixels",
                    corrective="Select a scene with lower measured AOI cloud coverage.",
                ),
                _maximum_percent_check(
                    f"scene_{index}_shadow_coverage",
                    "quality",
                    shadow_pixels,
                    aoi_pixels,
                    thresholds.max_shadow_aoi_percent_pass,
                    thresholds.max_shadow_aoi_percent_warning,
                    required=True,
                    source="6C cloud-shadow and cast-shadow union over AOI pixels",
                    corrective="Select a scene with lower measured AOI shadow coverage.",
                ),
            )
        )
    return tuple(checks)


def _native_resolution_check(
    scenes: tuple[HarmonizedScene, ...],
    profile: ValidityTaskProfile,
    thresholds: ScientificValidityThresholds,
) -> ScientificCheck:
    values: list[float] = []
    for scene in scenes:
        by_role = dict(zip(scene.band_order, scene.native_resolutions_metres, strict=True))
        for role in profile.required_bands:
            value = by_role.get(role)
            if value is not None:
                values.append(value)
    expected = len(scenes) * len(profile.required_bands)
    if len(values) != expected:
        return _unknown_check(
            "native_resolution",
            "resolution",
            required=True,
            threshold="native resolution for every required band",
            reason="Native-resolution evidence is incomplete.",
            corrective="Retain provider native-resolution metadata for every band.",
            source="6B/6D native resolution metadata",
        )
    worst = max(values)
    outcome: CheckOutcome = (
        "pass"
        if worst <= thresholds.native_resolution_metres_pass
        else "warning"
        if worst <= thresholds.native_resolution_metres_warning
        else "fail"
    )
    return ScientificCheck(
        check_id="native_resolution",
        category="resolution",
        outcome=outcome,
        required=True,
        measured_value=worst,
        measured_text=None,
        units="metres",
        denominator_name=None,
        denominator_value=None,
        threshold_description=(
            f"pass <= {thresholds.native_resolution_metres_pass:g} m; warning <= "
            f"{thresholds.native_resolution_metres_warning:g} m; otherwise fail"
        ),
        reason="Worst native resolution across required bands was evaluated.",
        corrective_action=(
            "Use data with native resolution appropriate to the requested task."
            if outcome != "pass"
            else None
        ),
        evidence_source="6B/6D native resolution metadata",
        provisional_threshold=True,
    )


def _upsampling_check(scenes: tuple[HarmonizedScene, ...]) -> ScientificCheck:
    upsampled = [str(index) for index, scene in enumerate(scenes, start=1) if scene.upsampled]
    return _categorical_check(
        "upsampling",
        "resolution",
        "warning" if upsampled else "pass",
        required=False,
        measured_text=("upsampled scenes: " + ", ".join(upsampled)) if upsampled else "none",
        threshold="warning when any scene is sampled onto pixels smaller than native resolution",
        reason=(
            "Upsampling interpolates samples and does not create additional spatial detail."
            if upsampled
            else "No scene is upsampled beyond its required-band native resolution."
        ),
        corrective="Use native-scale outputs or a genuinely finer-resolution source."
        if upsampled
        else None,
        source="6D upsampled flag and native/output resolutions",
    )


def _minimum_supported_scale(
    scenes: tuple[HarmonizedScene, ...],
    profile: ValidityTaskProfile,
    thresholds: ScientificValidityThresholds,
) -> float | None:
    native: list[float] = []
    for scene in scenes:
        by_role = dict(zip(scene.band_order, scene.native_resolutions_metres, strict=True))
        for role in profile.required_bands:
            value = by_role.get(role)
            if value is None:
                return None
            native.append(value)
    return max(native) * thresholds.supported_scale_native_pixel_multiplier if native else None


def _spatial_scale_check(
    context: ScientificValidityContext,
    minimum_scale: float | None,
    thresholds: ScientificValidityThresholds,
) -> ScientificCheck:
    requested = context.requested_spatial_scale_metres
    if requested is None or minimum_scale is None:
        return _unknown_check(
            "requested_spatial_scale",
            "geofeasibility",
            required=True,
            threshold=(
                "requested scale must be at least "
                f"{thresholds.supported_scale_native_pixel_multiplier:g} "
                "native pixels"
            ),
            reason="Requested scale or native-resolution evidence is missing.",
            corrective=(
                "Provide a positive requested spatial scale and complete native-resolution "
                "metadata."
            ),
            source="request scale and 6B/6D native resolution metadata",
        )
    supported = requested >= minimum_scale
    return ScientificCheck(
        check_id="requested_spatial_scale",
        category="geofeasibility",
        outcome="pass" if supported else "fail",
        required=True,
        measured_value=requested,
        measured_text=f"minimum supported scale: {minimum_scale:g} metres",
        units="metres",
        denominator_name=None,
        denominator_value=None,
        threshold_description=f"requested scale >= {minimum_scale:g} metres",
        reason=(
            "The requested scale has provisional sampling support; this is not a detection "
            "guarantee."
            if supported
            else "The requested scale is below the provisional native-resolution support limit."
        ),
        corrective_action=(
            None
            if supported
            else "Use finer native-resolution data or request a coarser spatial scale."
        ),
        evidence_source="requested scale and worst required-band native resolution",
        provisional_threshold=True,
    )


def _pair_checks(
    context: ScientificValidityContext,
    grid: CommonGridResult,
    joint_valid: np.ndarray | None,
    joint_usable: np.ndarray | None,
    thresholds: ScientificValidityThresholds,
) -> tuple[ScientificCheck, ...]:
    aoi_pixels = int(grid.aoi_mask.sum())
    checks: list[ScientificCheck] = []
    if joint_valid is None:
        checks.append(
            _unknown_check(
                "pair_valid_overlap",
                "coverage",
                required=True,
                threshold="joint valid overlap is required",
                reason="Joint valid-data evidence is unavailable.",
                corrective="Complete common-grid pair preparation.",
                source="6D/6E joint valid-data mask",
            )
        )
    else:
        checks.append(
            _minimum_percent_check(
                "pair_valid_overlap",
                "coverage",
                int((joint_valid & grid.aoi_mask).sum()),
                aoi_pixels,
                thresholds.min_pair_valid_overlap_percent_pass,
                thresholds.min_pair_valid_overlap_percent_warning,
                required=True,
                source="6D/6E joint valid-data mask",
                corrective="Select scenes with greater valid AOI overlap or reduce the AOI.",
            )
        )
    quality_available = all(
        scene.quality.quality_information == "available" for scene in grid.scenes
    )
    if joint_usable is None or not quality_available:
        checks.append(
            _unknown_check(
                "pair_joint_usable_aoi",
                "quality",
                required=True,
                threshold="joint quality-usable AOI coverage is required",
                reason="Joint usable evidence or actual quality information is unavailable.",
                corrective="Resolve QA for both scenes and recompute joint usable overlap.",
                source="6C/6D/6E joint usable mask",
            )
        )
    else:
        checks.append(
            _minimum_percent_check(
                "pair_joint_usable_aoi",
                "quality",
                int((joint_usable & grid.aoi_mask).sum()),
                aoi_pixels,
                thresholds.min_pair_usable_aoi_percent_pass,
                thresholds.min_pair_usable_aoi_percent_warning,
                required=True,
                source="6C/6D/6E joint usable mask",
                corrective="Choose a clearer pair with more joint usable AOI coverage.",
            )
        )
    checks.append(_registration_check(context.registration))
    checks.append(_platform_context_check(context))
    return tuple(checks)


def _registration_check(registration: RegistrationResult | None) -> ScientificCheck:
    if registration is None:
        return _unknown_check(
            "registration_evidence",
            "registration",
            required=True,
            threshold="6E registration state must be reliable",
            reason="Registration evidence is missing.",
            corrective="Run bounded distributed registration assessment.",
            source="6E RegistrationAssessment",
        )
    assessment = registration.assessment
    if assessment.state == "reliable":
        return _categorical_check(
            "registration_evidence",
            "registration",
            "pass",
            required=True,
            measured_text=(
                f"row={assessment.estimated_row_shift_pixels}, "
                f"column={assessment.estimated_column_shift_pixels}, "
                f"correction={assessment.correction_state}"
            ),
            threshold="registration state must be reliable with validated correction if needed",
            reason="Distributed agreement and held-out residual evidence are reliable.",
            corrective=None,
            source="6E RegistrationAssessment",
        )
    if assessment.state == "unsupported":
        return _categorical_check(
            "registration_evidence",
            "registration",
            "fail",
            required=True,
            measured_text="unsupported",
            threshold="registration state must be reliable",
            reason=assessment.explanation,
            corrective="Use a supported same-sensor pair with comparable bands and QA.",
            source="6E RegistrationAssessment",
        )
    return _unknown_check(
        "registration_evidence",
        "registration",
        required=True,
        threshold="registration state must be reliable",
        reason=assessment.explanation,
        corrective=(
            "Use a pair with sufficient distributed texture/overlap or improve source alignment."
        ),
        source="6E RegistrationAssessment",
    )


def _platform_context_check(context: ScientificValidityContext) -> ScientificCheck:
    evidence = _ordered_evidence(context)
    platforms = [item.platform for item in evidence]
    if len(evidence) != len(context.request.scenes) or any(value is None for value in platforms):
        return _unknown_check(
            "platform_context",
            "compatibility",
            required=False,
            threshold="platform metadata should be available for contextual comparison",
            reason="Platform evidence is missing; no stronger compatibility conclusion is drawn.",
            corrective="Resolve platform metadata for both acquisitions.",
            source="scene_acquisition_evidence.platform",
        )
    different = len(set(platforms)) > 1
    return _categorical_check(
        "platform_context",
        "compatibility",
        "warning" if different else "pass",
        required=False,
        measured_text=", ".join(str(value) for value in platforms),
        threshold="different platforms are a contextual warning, not automatic incompatibility",
        reason=(
            "Different Sentinel-2 platforms may introduce contextual acquisition differences."
            if different
            else "Both acquisitions report the same platform."
        ),
        corrective=(
            "Account for platform/acquisition differences in downstream interpretation."
            if different
            else None
        ),
        source="scene_acquisition_evidence.platform",
    )


def _effective_outputs(
    context: ScientificValidityContext,
) -> tuple[tuple[HarmonizedScene, ...], np.ndarray | None, np.ndarray | None]:
    grid = context.common_grid
    if grid is None:
        return (), None, None
    registration = context.registration
    if (
        registration is not None
        and registration.assessment.correction_state == "applied"
        and registration.corrected_moving_scene is not None
    ):
        return (
            (grid.scenes[0], registration.corrected_moving_scene),
            registration.corrected_joint_valid_data,
            registration.corrected_joint_usable,
        )
    return grid.scenes, grid.joint_valid_data, grid.joint_usable


def _ordered_evidence(context: ScientificValidityContext) -> tuple[SceneAcquisitionEvidence, ...]:
    by_scene = {item.scene.model_dump_json(): item for item in context.acquisition_evidence}
    return tuple(
        by_scene[key]
        for scene in context.request.scenes
        if (key := scene.model_dump_json()) in by_scene
    )


def _minimum_percent_check(
    check_id: str,
    category: CheckCategory,
    numerator: int,
    denominator: int,
    pass_threshold: float,
    warning_threshold: float,
    *,
    required: bool,
    source: str,
    corrective: str,
) -> ScientificCheck:
    if denominator <= 0:
        return _unknown_check(
            check_id,
            category,
            required=required,
            threshold=f"pass >= {pass_threshold:g}%; warning >= {warning_threshold:g}%",
            reason="The required denominator is empty.",
            corrective=corrective,
            source=source,
        )
    percent = numerator / denominator * 100.0
    outcome: CheckOutcome = (
        "pass"
        if percent >= pass_threshold
        else "warning"
        if percent >= warning_threshold
        else "fail"
    )
    return _percent_check(
        check_id,
        category,
        outcome,
        required,
        numerator,
        denominator,
        f"pass >= {pass_threshold:g}%; warning >= {warning_threshold:g}%; otherwise fail",
        corrective if outcome != "pass" else None,
        source,
    )


def _maximum_percent_check(
    check_id: str,
    category: CheckCategory,
    numerator: int,
    denominator: int,
    pass_threshold: float,
    warning_threshold: float,
    *,
    required: bool,
    source: str,
    corrective: str,
) -> ScientificCheck:
    if denominator <= 0:
        return _unknown_check(
            check_id,
            category,
            required=required,
            threshold=f"pass <= {pass_threshold:g}%; warning <= {warning_threshold:g}%",
            reason="The required denominator is empty.",
            corrective=corrective,
            source=source,
        )
    percent = numerator / denominator * 100.0
    outcome: CheckOutcome = (
        "pass"
        if percent <= pass_threshold
        else "warning"
        if percent <= warning_threshold
        else "fail"
    )
    return _percent_check(
        check_id,
        category,
        outcome,
        required,
        numerator,
        denominator,
        f"pass <= {pass_threshold:g}%; warning <= {warning_threshold:g}%; otherwise fail",
        corrective if outcome != "pass" else None,
        source,
    )


def _percent_check(
    check_id: str,
    category: CheckCategory,
    outcome: CheckOutcome,
    required: bool,
    numerator: int,
    denominator: int,
    threshold: str,
    corrective: str | None,
    source: str,
) -> ScientificCheck:
    percent = numerator / denominator * 100.0
    return ScientificCheck(
        check_id=check_id,
        category=category,
        outcome=outcome,
        required=required,
        measured_value=percent,
        measured_text=f"{numerator} of {denominator} pixels",
        units="percent",
        denominator_name="inside_aoi_pixels",
        denominator_value=float(denominator),
        threshold_description=threshold,
        reason=f"Measured {percent:.6f}% from the stated AOI denominator.",
        corrective_action=corrective,
        evidence_source=source,
        provisional_threshold=True,
    )


def _categorical_check(
    check_id: str,
    category: CheckCategory,
    outcome: CheckOutcome,
    *,
    required: bool,
    measured_text: str,
    threshold: str,
    reason: str,
    corrective: str | None,
    source: str,
) -> ScientificCheck:
    return ScientificCheck(
        check_id=check_id,
        category=category,
        outcome=outcome,
        required=required,
        measured_value=None,
        measured_text=measured_text,
        units=None,
        denominator_name=None,
        denominator_value=None,
        threshold_description=threshold,
        reason=reason,
        corrective_action=corrective,
        evidence_source=source,
        provisional_threshold=True,
    )


def _unknown_check(
    check_id: str,
    category: CheckCategory,
    *,
    required: bool,
    threshold: str,
    reason: str,
    corrective: str,
    source: str,
) -> ScientificCheck:
    return ScientificCheck(
        check_id=check_id,
        category=category,
        outcome="unknown",
        required=required,
        measured_value=None,
        measured_text=None,
        units=None,
        denominator_name=None,
        denominator_value=None,
        threshold_description=threshold,
        reason=reason,
        corrective_action=corrective,
        evidence_source=source,
        provisional_threshold=True,
    )


def _missing_grid_checks(profile: ValidityTaskProfile) -> tuple[ScientificCheck, ...]:
    checks = [
        _unknown_check(
            "common_grid_evidence",
            "coverage",
            required=True,
            threshold="measured 6D common-grid outputs are required",
            reason="Common-grid evidence is missing.",
            corrective="Complete 6B-6D scientific preparation.",
            source="6D CommonGridResult",
        ),
        _unknown_check(
            "requested_spatial_scale",
            "geofeasibility",
            required=True,
            threshold="requested scale must be evaluated against native resolution",
            reason="Native resolution and common-grid evidence are missing.",
            corrective="Provide measured common-grid outputs and requested scale.",
            source="request scale and 6D outputs",
        ),
    ]
    if profile.requires_registration:
        checks.append(_registration_check(None))
    else:
        checks.append(_not_applicable_registration())
    return tuple(checks)


def _not_applicable_registration() -> ScientificCheck:
    return _categorical_check(
        "registration_evidence",
        "registration",
        "not_applicable",
        required=False,
        measured_text="single-scene profile",
        threshold="registration applies only to pair profiles",
        reason="Registration is not applicable to a single-scene task.",
        corrective=None,
        source="task profile",
    )


def _not_applicable_temporal_context() -> ScientificCheck:
    return _categorical_check(
        "temporal_context",
        "temporal",
        "not_applicable",
        required=False,
        measured_text="single-scene profile",
        threshold="pair interval/seasonal checks apply only to pair profiles",
        reason="Pair temporal context is not applicable to a single scene.",
        corrective=None,
        source="task profile",
    )


def _unknown_temporal_context() -> ScientificCheck:
    return _unknown_check(
        "temporal_context",
        "temporal",
        required=False,
        threshold="pair interval and seasonal separation should be measured",
        reason="Temporal context cannot be measured without two chronological dates.",
        corrective="Resolve both authoritative acquisition dates.",
        source="scene_acquisition_evidence.acquired_at",
    )


def _circular_day_of_year_difference(first: datetime, second: datetime) -> float:
    first_day = first.timetuple().tm_yday
    second_day = second.timetuple().tm_yday
    direct = abs(second_day - first_day)
    return float(min(direct, 365 - direct))


def _report(
    context: ScientificValidityContext,
    profile: ValidityTaskProfile,
    checks: tuple[ScientificCheck, ...],
    minimum_scale: float | None,
    thresholds: ScientificValidityThresholds,
) -> ScientificValidityReport:
    failed = tuple(check.check_id for check in checks if check.outcome == "fail")
    unknown_required = tuple(
        check.check_id for check in checks if check.required and check.outcome == "unknown"
    )
    warnings = tuple(check.check_id for check in checks if check.outcome == "warning")
    if failed:
        readiness: ReadinessState = "not_ready"
        reason = "One or more required scientific-validity checks failed."
        blocking = failed + unknown_required
    elif unknown_required:
        readiness = "unknown"
        reason = "Required evidence is missing or inconclusive; positive readiness is prohibited."
        blocking = unknown_required
    elif warnings:
        readiness = "limited"
        reason = "Required checks pass, but provisional contextual or quality warnings remain."
        blocking = ()
    else:
        readiness = "ready"
        reason = (
            "All required provisional engineering checks pass; this is task feasibility, not an "
            "accuracy or object-detection guarantee."
        )
        blocking = ()
    return ScientificValidityReport(
        profile=profile,
        threshold_version=thresholds.version,
        thresholds_are_provisional_engineering_limits=True,
        checks=checks,
        readiness=readiness,
        readiness_reason=reason,
        blocking_check_ids=blocking,
        warning_check_ids=warnings,
        minimum_supported_spatial_scale_metres=minimum_scale,
        requested_spatial_scale_metres=context.requested_spatial_scale_metres,
        map_viewing_affected=False,
        catalogue_search_affected=False,
    )


def _unsupported_report(
    context: ScientificValidityContext, thresholds: ScientificValidityThresholds
) -> ScientificValidityReport:
    profile = ValidityTaskProfile(
        profile_id="unsupported",
        version="1.0",
        intended_task=context.request.intended_task,
        processing_profile=context.request.processing_profile,
        required_bands=(),
        required_capabilities=(),
        requires_registration=False,
    )
    check = _categorical_check(
        "task_profile",
        "processing",
        "fail",
        required=True,
        measured_text=context.request.processing_profile,
        threshold="a configured validity task profile is required",
        reason="No deterministic validity profile supports this request.",
        corrective="Use a supported explicit processing/task profile.",
        source="PreparationRequest",
    )
    return ScientificValidityReport(
        profile=profile,
        threshold_version=thresholds.version,
        thresholds_are_provisional_engineering_limits=True,
        checks=(check,),
        readiness="unsupported",
        readiness_reason="The requested task/profile has no configured validity rules.",
        blocking_check_ids=(check.check_id,),
        warning_check_ids=(),
        minimum_supported_spatial_scale_metres=None,
        requested_spatial_scale_metres=context.requested_spatial_scale_metres,
        map_viewing_affected=False,
        catalogue_search_affected=False,
    )
