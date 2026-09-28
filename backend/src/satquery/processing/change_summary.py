from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import numpy as np

from satquery.api.schemas.catalog import CatalogGeometry
from satquery.api.schemas.processing import PreparationRequest
from satquery.api.schemas.viewer import ViewerSceneIdentity
from satquery.processing.area import projected_pixel_area_square_metres
from satquery.processing.change import PairPreparationOutcome
from satquery.processing.change_detection import OpticalChangeDetectionOutcome
from satquery.processing.grid import CommonGridResult, HarmonizedScene
from satquery.processing.registration import RegistrationResult

CHANGE_SUMMARY_VERSION: Literal["8d-computed-summary-v1"] = "8d-computed-summary-v1"


class ChangeSummaryError(ValueError):
    """A safe failure when computed evidence cannot support a change summary."""


@dataclass(frozen=True, slots=True)
class ChangeSummaryParameters:
    version: Literal["8d-computed-summary-v1"] = CHANGE_SUMMARY_VERSION
    change_percentage_denominator: Literal["joint_valid_observed_area"] = (
        "joint_valid_observed_area"
    )
    coverage_denominator: Literal["inside_aoi"] = "inside_aoi"
    unknown_policy: Literal["inside_aoi_outside_joint_usable"] = "inside_aoi_outside_joint_usable"
    pixel_area_method: Literal["projected_affine_determinant_with_crs_unit_conversion"] = (
        "projected_affine_determinant_with_crs_unit_conversion"
    )
    seasonal_context_warning_days: int = 45

    def __post_init__(self) -> None:
        if self.seasonal_context_warning_days < 1:
            raise ValueError("seasonal warning interval must be positive")


@dataclass(frozen=True, slots=True)
class ChangeAreaSummary:
    pixel_area_square_metres: float
    aoi_pixel_count: int
    aoi_area_square_metres: float
    joint_valid_pixel_count: int
    joint_valid_observed_area_square_metres: float
    observed_coverage_percent_of_aoi: float
    joint_usable_pixel_count: int
    joint_usable_area_square_metres: float
    usable_coverage_percent_of_aoi: float
    changed_pixel_count: int
    changed_area_square_metres: float
    changed_percent_of_joint_valid_observed_area: float
    unchanged_pixel_count: int
    unchanged_area_square_metres: float
    unknown_pixel_count: int
    unknown_area_square_metres: float
    unknown_percent_of_aoi: float


@dataclass(frozen=True, slots=True)
class ChangeSummaryWarning:
    code: str
    statement: str


@dataclass(frozen=True, slots=True)
class ComputedChangeSummary:
    version: Literal["8d-computed-summary-v1"]
    parameters: ChangeSummaryParameters
    sources: tuple[ViewerSceneIdentity, ViewerSceneIdentity]
    acquired_at: tuple[datetime, datetime]
    aoi: CatalogGeometry
    method: str
    method_version: str
    threshold: float
    threshold_units: str
    area: ChangeAreaSummary
    alignment_statement: str
    warnings: tuple[ChangeSummaryWarning, ...]
    statements: tuple[str, ...]
    directional_measurements: tuple[()] = ()
    cause_or_land_cover_category: Literal["not_determined"] = "not_determined"


class ChangeSummaryService:
    """Build deterministic measurements and prose only from a completed 8C result."""

    def __init__(self, parameters: ChangeSummaryParameters | None = None) -> None:
        self._parameters = parameters or ChangeSummaryParameters()

    def summarize(
        self,
        request: PreparationRequest,
        pair: PairPreparationOutcome,
        detection: OpticalChangeDetectionOutcome,
        grid: CommonGridResult,
        registration: RegistrationResult,
    ) -> ComputedChangeSummary:
        _validate_inputs(request, pair, detection, grid, registration)
        classification = detection.classification
        if classification is None:
            raise ChangeSummaryError("A completed classification is required for a summary.")
        _validate_classification(classification, pair, detection, grid)
        before_date, after_date = pair.acquired_at
        if before_date is None or after_date is None:
            raise ChangeSummaryError("Both authoritative acquisition dates are required.")

        pixel_area = projected_pixel_area_square_metres(grid.grid)
        aoi_pixels = int(grid.aoi_mask.sum())
        joint_valid_pixels = int(pair.joint_valid.sum())
        joint_usable_pixels = int(pair.joint_usable.sum())
        changed_pixels = int(
            np.count_nonzero((classification == detection.parameters.changed_value) & grid.aoi_mask)
        )
        unchanged_pixels = int(
            np.count_nonzero(
                (classification == detection.parameters.unchanged_value) & grid.aoi_mask
            )
        )
        unknown_pixels = aoi_pixels - joint_usable_pixels
        if changed_pixels + unchanged_pixels != joint_usable_pixels:
            raise ChangeSummaryError(
                "Changed plus unchanged pixels must equal the exact joint-usable support."
            )
        if joint_valid_pixels <= 0:
            raise ChangeSummaryError(
                "Changed percentage is unavailable without joint-valid observed area."
            )

        area = ChangeAreaSummary(
            pixel_area_square_metres=pixel_area,
            aoi_pixel_count=aoi_pixels,
            aoi_area_square_metres=aoi_pixels * pixel_area,
            joint_valid_pixel_count=joint_valid_pixels,
            joint_valid_observed_area_square_metres=joint_valid_pixels * pixel_area,
            observed_coverage_percent_of_aoi=100.0 * joint_valid_pixels / aoi_pixels,
            joint_usable_pixel_count=joint_usable_pixels,
            joint_usable_area_square_metres=joint_usable_pixels * pixel_area,
            usable_coverage_percent_of_aoi=100.0 * joint_usable_pixels / aoi_pixels,
            changed_pixel_count=changed_pixels,
            changed_area_square_metres=changed_pixels * pixel_area,
            changed_percent_of_joint_valid_observed_area=(
                100.0 * changed_pixels / joint_valid_pixels
            ),
            unchanged_pixel_count=unchanged_pixels,
            unchanged_area_square_metres=unchanged_pixels * pixel_area,
            unknown_pixel_count=unknown_pixels,
            unknown_area_square_metres=unknown_pixels * pixel_area,
            unknown_percent_of_aoi=100.0 * unknown_pixels / aoi_pixels,
        )
        scenes = _effective_scenes(grid, registration)
        warnings = _warnings(
            scenes, grid.aoi_mask, before_date, after_date, registration, area, self._parameters
        )
        alignment_statement = _alignment_statement(registration)
        statements = _statements(request, detection, before_date, after_date, area)
        return ComputedChangeSummary(
            version=self._parameters.version,
            parameters=self._parameters,
            sources=pair.sources,
            acquired_at=(before_date, after_date),
            aoi=request.aoi,
            method=detection.parameters.method,
            method_version=detection.parameters.version,
            threshold=detection.parameters.threshold,
            threshold_units=detection.parameters.threshold_units,
            area=area,
            alignment_statement=alignment_statement,
            warnings=warnings,
            statements=statements,
        )


def _validate_inputs(
    request: PreparationRequest,
    pair: PairPreparationOutcome,
    detection: OpticalChangeDetectionOutcome,
    grid: CommonGridResult,
    registration: RegistrationResult,
) -> None:
    if request.intended_task != "optical_pair" or tuple(request.scenes) != pair.sources:
        raise ChangeSummaryError("The request does not match the computed source pair.")
    if registration.original is not grid or pair.grid != grid.grid:
        raise ChangeSummaryError("The summary inputs do not share the computed common grid.")
    if detection.state != "completed" or detection.sources != pair.sources:
        raise ChangeSummaryError("Only a completed source-matched change result can be summarized.")
    if detection.pair_processing_version != pair.processing_version:
        raise ChangeSummaryError("The change result is not bound to this pair preparation version.")


def _effective_scenes(
    grid: CommonGridResult, registration: RegistrationResult
) -> tuple[HarmonizedScene, HarmonizedScene]:
    return grid.scenes[0], registration.corrected_moving_scene or grid.scenes[1]


def _validate_classification(
    classification: np.ndarray,
    pair: PairPreparationOutcome,
    detection: OpticalChangeDetectionOutcome,
    grid: CommonGridResult,
) -> None:
    expected_shape = (grid.grid.height, grid.grid.width)
    if classification.shape != expected_shape:
        raise ChangeSummaryError("The classification does not match the common grid shape.")
    usable = pair.joint_usable
    changed_value = detection.parameters.changed_value
    unchanged_value = detection.parameters.unchanged_value
    unknown_value = detection.parameters.unknown_value
    if np.any(classification[~usable] != unknown_value) or np.any(
        ~np.isin(classification[usable], (changed_value, unchanged_value))
    ):
        raise ChangeSummaryError(
            "The classification violates the exact joint-usable unknown-pixel policy."
        )
    recorded = {item.classification: item.pixel_count for item in detection.classes}
    measured = {
        "changed": int(np.count_nonzero((classification == changed_value) & grid.aoi_mask)),
        "unchanged": int(np.count_nonzero((classification == unchanged_value) & grid.aoi_mask)),
        "unknown": int(grid.aoi_mask.sum()) - int(usable.sum()),
    }
    if recorded != measured:
        raise ChangeSummaryError("The classification counts do not match the 8C evidence record.")


def _warnings(
    scenes: tuple[HarmonizedScene, HarmonizedScene],
    aoi_mask: np.ndarray,
    before_date: datetime,
    after_date: datetime,
    registration: RegistrationResult,
    area: ChangeAreaSummary,
    parameters: ChangeSummaryParameters,
) -> tuple[ChangeSummaryWarning, ...]:
    warnings: list[ChangeSummaryWarning] = []
    for temporal_role, scene in zip(("before", "after"), scenes, strict=True):
        cloud_or_shadow = aoi_mask & (
            scene.quality.clouds_or_cirrus
            | scene.quality.cloud_shadows
            | scene.quality.cast_shadows
        )
        pixels = int(cloud_or_shadow.sum())
        if pixels:
            percent = 100.0 * pixels / area.aoi_pixel_count
            warnings.append(
                ChangeSummaryWarning(
                    code=f"{temporal_role}_cloud_or_shadow_exclusion",
                    statement=(
                        f"Actual QA excluded {pixels} {temporal_role} cloud/cirrus/shadow "
                        f"pixels ({percent:.2f}% of the rasterized AOI); they remain unknown."
                    ),
                )
            )
    if area.unknown_pixel_count:
        warnings.append(
            ChangeSummaryWarning(
                code="unknown_area_present",
                statement=(
                    f"{area.unknown_area_square_metres:.2f} m² "
                    f"({area.unknown_percent_of_aoi:.2f}% of the rasterized AOI) is unknown "
                    "because it is outside joint usability."
                ),
            )
        )
    interval_days = (after_date - before_date).total_seconds() / 86400.0
    if interval_days >= parameters.seasonal_context_warning_days:
        warnings.append(
            ChangeSummaryWarning(
                code="seasonal_context_not_isolated",
                statement=(
                    f"The acquisitions are {interval_days:.1f} days apart; this spectral method "
                    "does not isolate seasonal or illumination effects."
                ),
            )
        )
    if registration.assessment.correction_state == "applied":
        warnings.append(
            ChangeSummaryWarning(
                code="registration_translation_applied",
                statement=(
                    "A validated bounded translation was applied to the after image; matching "
                    "pixels do not establish ground-truth positional accuracy."
                ),
            )
        )
    return tuple(warnings)


def _alignment_statement(registration: RegistrationResult) -> str:
    assessment = registration.assessment
    if assessment.correction_state == "applied" and assessment.correction is not None:
        correction = assessment.correction
        return (
            "Registration was assessed as reliable after a validated translation of "
            f"{correction.row_shift_pixels} row and {correction.column_shift_pixels} column pixels."
        )
    return "Registration was assessed as reliable; no translation correction was needed."


def _statements(
    request: PreparationRequest,
    detection: OpticalChangeDetectionOutcome,
    before_date: datetime,
    after_date: datetime,
    area: ChangeAreaSummary,
) -> tuple[str, ...]:
    geometry_type = request.aoi.type
    return (
        (
            f"From {before_date.date().isoformat()} to {after_date.date().isoformat()}, "
            f"{area.changed_area_square_metres:.2f} m² met the spectral-change threshold, "
            f"equal to {area.changed_percent_of_joint_valid_observed_area:.2f}% of the "
            "joint-valid observed area."
        ),
        (
            f"The {geometry_type} AOI had {area.joint_valid_observed_area_square_metres:.2f} m² "
            f"joint-valid observed coverage ({area.observed_coverage_percent_of_aoi:.2f}% of "
            f"the rasterized AOI) and {area.joint_usable_area_square_metres:.2f} m² usable "
            "for classification."
        ),
        (
            f"Unknown area was {area.unknown_area_square_metres:.2f} m² "
            f"({area.unknown_percent_of_aoi:.2f}% of the rasterized AOI) and was not counted "
            "as unchanged."
        ),
        (
            f"Method {detection.parameters.method} {detection.parameters.version} used calibrated "
            f"RGB with threshold {detection.parameters.threshold:g} "
            f"{detection.parameters.threshold_units}; cause or land-cover category is not "
            "determined."
        ),
    )
