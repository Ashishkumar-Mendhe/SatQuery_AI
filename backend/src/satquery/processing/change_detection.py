from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isclose, isfinite
from typing import Literal

import numpy as np

from satquery.api.schemas.viewer import ViewerSceneIdentity
from satquery.processing.area import projected_pixel_area_square_metres
from satquery.processing.change import PairPreparationOutcome
from satquery.processing.grid import CommonGridResult, HarmonizedScene
from satquery.processing.registration import RegistrationResult

CHANGE_DETECTION_VERSION: Literal["8c-calibrated-rgb-rms-v1"] = "8c-calibrated-rgb-rms-v1"
UNKNOWN_CLASS_VALUE = np.uint8(255)
UNCHANGED_CLASS_VALUE = np.uint8(0)
CHANGED_CLASS_VALUE = np.uint8(1)


@dataclass(frozen=True, slots=True)
class ChangeDetectionParameters:
    """Versioned engineering parameters for observed spectral change only."""

    method: Literal["calibrated_rgb_rms_reflectance_difference"] = (
        "calibrated_rgb_rms_reflectance_difference"
    )
    version: Literal["8c-calibrated-rgb-rms-v1"] = CHANGE_DETECTION_VERSION
    input_band_roles: tuple[str, ...] = ("red", "green", "blue")
    threshold: float = 0.05
    threshold_units: Literal["dimensionless_surface_reflectance_rms"] = (
        "dimensionless_surface_reflectance_rms"
    )
    comparison_operator: Literal["greater_than_or_equal"] = "greater_than_or_equal"
    radiometric_harmonization: Literal["none"] = "none"
    per_image_normalization: Literal[False] = False
    changed_value: Literal[1] = 1
    unchanged_value: Literal[0] = 0
    unknown_value: Literal[255] = 255
    threshold_status: Literal["provisional_engineering_threshold"] = (
        "provisional_engineering_threshold"
    )

    def __post_init__(self) -> None:
        if not isfinite(self.threshold) or not 0 < self.threshold <= 1:
            raise ValueError("change threshold must be finite and in (0, 1]")
        if self.input_band_roles != ("red", "green", "blue"):
            raise ValueError("the initial detector requires calibrated red, green, and blue bands")


@dataclass(frozen=True, slots=True)
class ChangeDetectionReason:
    code: str
    explanation: str
    corrective_action: str


@dataclass(frozen=True, slots=True)
class ChangeClassMeasurement:
    classification: Literal["unchanged", "changed", "unknown"]
    raster_value: int
    pixel_count: int
    area_square_metres: float
    fraction_of_aoi: float
    fraction_of_joint_usable: float | None


@dataclass(frozen=True, slots=True)
class OpticalChangeDetectionOutcome:
    state: Literal["completed", "insufficient_evidence", "failed"]
    processing_version: Literal["8c-calibrated-rgb-rms-v1"]
    parameters: ChangeDetectionParameters
    sources: tuple[ViewerSceneIdentity, ViewerSceneIdentity]
    acquired_at: tuple[datetime | None, datetime | None]
    pair_processing_version: str
    classification: np.ndarray | None
    spectral_difference: np.ndarray | None
    classes: tuple[ChangeClassMeasurement, ...]
    reasons: tuple[ChangeDetectionReason, ...]
    interpretation: str


class OpticalChangeDetector:
    """Classify observed RGB spectral change over an exact comparable Phase 8B pair."""

    def __init__(self, parameters: ChangeDetectionParameters | None = None) -> None:
        self._parameters = parameters or ChangeDetectionParameters()

    def detect(
        self,
        pair: PairPreparationOutcome,
        grid: CommonGridResult,
        registration: RegistrationResult,
    ) -> OpticalChangeDetectionOutcome:
        if pair.state != "comparable" or not pair.comparison_allowed:
            reasons = tuple(
                ChangeDetectionReason(reason.code, reason.explanation, reason.corrective_action)
                for reason in pair.reasons
            ) or (
                ChangeDetectionReason(
                    "pair_not_comparable",
                    "The Phase 8B preparation outcome does not permit comparison.",
                    "Resolve the pair preparation findings before change detection.",
                ),
            )
            return self._without_classification(pair, "insufficient_evidence", reasons)

        integrity_reason = _validate_pair_integrity(pair, grid, registration)
        if integrity_reason is not None:
            return self._without_classification(pair, "failed", (integrity_reason,))

        before, after = _effective_scenes(grid, registration)
        calibration_reason = _validate_calibrated_bands(
            before, after, self._parameters.input_band_roles
        )
        if calibration_reason is not None:
            return self._without_classification(pair, "failed", (calibration_reason,))

        usable = pair.joint_usable
        if not np.any(usable):
            return self._without_classification(
                pair,
                "insufficient_evidence",
                (
                    ChangeDetectionReason(
                        "no_joint_usable_area",
                        "No pixel is usable on both dates, so spectral change cannot be measured.",
                        "Choose a comparable pair with clear, valid overlap on both dates.",
                    ),
                ),
            )

        band_indices = tuple(
            before.band_order.index(role) for role in self._parameters.input_band_roles
        )
        before_values = before.data[np.asarray(band_indices)].astype(np.float64, copy=False)
        after_values = after.data[np.asarray(band_indices)].astype(np.float64, copy=False)
        finite = np.all(np.isfinite(before_values) & np.isfinite(after_values), axis=0)
        if not np.all(finite[usable]):
            return self._without_classification(
                pair,
                "failed",
                (
                    ChangeDetectionReason(
                        "nonfinite_usable_input",
                        "The declared joint-usable mask includes a non-finite calibrated value.",
                        "Re-run calibrated raster and pair preparation before change detection.",
                    ),
                ),
            )

        delta = after_values[:, usable] - before_values[:, usable]
        usable_difference = np.sqrt(np.mean(np.square(delta), axis=0))
        spectral_difference = np.full(usable.shape, np.nan, dtype=np.float32)
        spectral_difference[usable] = usable_difference.astype(np.float32)
        classification = np.full(usable.shape, UNKNOWN_CLASS_VALUE, dtype=np.uint8)
        changed = np.zeros(usable.shape, dtype=bool)
        changed[usable] = usable_difference >= self._parameters.threshold
        unchanged = usable & ~changed
        classification[unchanged] = UNCHANGED_CLASS_VALUE
        classification[changed] = CHANGED_CLASS_VALUE
        classes = _measure_classes(classification, grid.aoi_mask, usable, pair)
        return OpticalChangeDetectionOutcome(
            state="completed",
            processing_version=self._parameters.version,
            parameters=self._parameters,
            sources=pair.sources,
            acquired_at=pair.acquired_at,
            pair_processing_version=pair.processing_version,
            classification=classification,
            spectral_difference=spectral_difference,
            classes=classes,
            reasons=(),
            interpretation=(
                "This result identifies thresholded observed RGB surface-reflectance change. "
                "It does not determine a cause or identify buildings, mud, land-cover transitions, "
                "or seasonal effects."
            ),
        )

    def _without_classification(
        self,
        pair: PairPreparationOutcome,
        state: Literal["insufficient_evidence", "failed"],
        reasons: tuple[ChangeDetectionReason, ...],
    ) -> OpticalChangeDetectionOutcome:
        return OpticalChangeDetectionOutcome(
            state=state,
            processing_version=self._parameters.version,
            parameters=self._parameters,
            sources=pair.sources,
            acquired_at=pair.acquired_at,
            pair_processing_version=pair.processing_version,
            classification=None,
            spectral_difference=None,
            classes=(),
            reasons=reasons,
            interpretation=(
                "No spectral-change classification was produced because the required evidence "
                "was insufficient or inconsistent."
            ),
        )


def _validate_pair_integrity(
    pair: PairPreparationOutcome,
    grid: CommonGridResult,
    registration: RegistrationResult,
) -> ChangeDetectionReason | None:
    if registration.original is not grid:
        return _integrity_reason("Registration evidence is not bound to the supplied common grid.")
    scenes = _effective_scenes(grid, registration)
    expected_shape = (grid.grid.height, grid.grid.width)
    if (
        pair.grid != grid.grid
        or pair.sources != (scenes[0].scene, scenes[1].scene)
        or pair.band_order != scenes[0].band_order
        or scenes[1].band_order != pair.band_order
        or pair.registration_state != registration.assessment.state
        or pair.correction_state != registration.assessment.correction_state
        or grid.radiometric_harmonization != "none"
        or pair.joint_valid.shape != expected_shape
        or pair.joint_usable.shape != expected_shape
        or grid.aoi_mask.shape != expected_shape
    ):
        return _integrity_reason("The prepared pair metadata does not match its source grid.")
    recomputed_valid, recomputed_usable = _recompute_masks(grid.aoi_mask, scenes)
    if not np.array_equal(pair.joint_valid, recomputed_valid) or not np.array_equal(
        pair.joint_usable, recomputed_usable
    ):
        return _integrity_reason("The prepared pair masks do not match both source dates and QA.")
    expected_pixel_area = projected_pixel_area_square_metres(grid.grid)
    coverage = pair.coverage
    if (
        coverage.aoi_pixels != int(grid.aoi_mask.sum())
        or coverage.joint_valid_pixels != int(recomputed_valid.sum())
        or coverage.joint_usable_pixels != int(recomputed_usable.sum())
        or not isclose(coverage.pixel_area_square_metres, expected_pixel_area)
        or not isclose(
            coverage.joint_valid_area_square_metres,
            coverage.joint_valid_pixels * expected_pixel_area,
        )
        or not isclose(
            coverage.joint_usable_area_square_metres,
            coverage.joint_usable_pixels * expected_pixel_area,
        )
    ):
        return _integrity_reason("The prepared pair coverage does not match its masks and grid.")
    if (
        registration.assessment.state != "reliable"
        or registration.assessment.correction_state not in {"applied", "not_needed"}
    ):
        return _integrity_reason(
            "The supplied registration evidence is not accepted for comparison."
        )
    return None


def _validate_calibrated_bands(
    before: HarmonizedScene,
    after: HarmonizedScene,
    roles: tuple[str, ...],
) -> ChangeDetectionReason | None:
    for scene in (before, after):
        if any(role not in scene.band_order for role in roles):
            return _integrity_reason("A required calibrated RGB band is absent from a source date.")
        metadata = {band.role: band for band in scene.bands}
        if any(role not in metadata or metadata[role].units != "1" for role in roles):
            return ChangeDetectionReason(
                "calibration_metadata_unavailable",
                "Both dates require dimensionless calibrated reflectance metadata for RGB.",
                "Re-run Phase 6 extraction from supported Sentinel-2 L2A scientific assets.",
            )
    return None


def _effective_scenes(
    grid: CommonGridResult, registration: RegistrationResult
) -> tuple[HarmonizedScene, HarmonizedScene]:
    return grid.scenes[0], registration.corrected_moving_scene or grid.scenes[1]


def _recompute_masks(
    aoi: np.ndarray, scenes: tuple[HarmonizedScene, HarmonizedScene]
) -> tuple[np.ndarray, np.ndarray]:
    valid = aoi.copy()
    usable = aoi.copy()
    for scene in scenes:
        valid &= scene.valid_data
        quality = scene.quality
        excluded = (
            quality.outside_aoi
            | quality.missing_or_invalid
            | quality.clouds_or_cirrus
            | quality.cloud_shadows
            | quality.cast_shadows
            | quality.snow_or_ice
            | quality.unknown_quality
        )
        usable &= scene.valid_data & quality.usable & ~excluded
    return valid, valid & usable


def _measure_classes(
    classification: np.ndarray,
    aoi: np.ndarray,
    usable: np.ndarray,
    pair: PairPreparationOutcome,
) -> tuple[ChangeClassMeasurement, ...]:
    aoi_pixels = int(aoi.sum())
    usable_pixels = int(usable.sum())
    pixel_area = pair.coverage.pixel_area_square_metres

    def measurement(
        name: Literal["unchanged", "changed", "unknown"], value: int, count: int
    ) -> ChangeClassMeasurement:
        return ChangeClassMeasurement(
            classification=name,
            raster_value=value,
            pixel_count=count,
            area_square_metres=count * pixel_area,
            fraction_of_aoi=count / aoi_pixels,
            fraction_of_joint_usable=(None if name == "unknown" else count / usable_pixels),
        )

    unchanged = int(np.count_nonzero((classification == UNCHANGED_CLASS_VALUE) & aoi))
    changed = int(np.count_nonzero((classification == CHANGED_CLASS_VALUE) & aoi))
    unknown = aoi_pixels - usable_pixels
    return (
        measurement("unchanged", int(UNCHANGED_CLASS_VALUE), unchanged),
        measurement("changed", int(CHANGED_CLASS_VALUE), changed),
        measurement("unknown", int(UNKNOWN_CLASS_VALUE), unknown),
    )


def _integrity_reason(explanation: str) -> ChangeDetectionReason:
    return ChangeDetectionReason(
        "pair_integrity_failed",
        explanation,
        "Re-run Phase 8B pair preparation and use its unmodified result and effective scenes.",
    )
