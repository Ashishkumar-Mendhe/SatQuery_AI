from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isclose
from typing import Literal

import numpy as np

from satquery.api.schemas.processing import OutputGrid, PreparationRequest
from satquery.api.schemas.viewer import ViewerSceneIdentity
from satquery.processing.area import projected_pixel_area_square_metres
from satquery.processing.grid import CommonGridResult, HarmonizedScene
from satquery.processing.registration import RegistrationResult
from satquery.processing.validity import SceneAcquisitionEvidence

PAIR_PREPARATION_VERSION: Literal["8b-pair-preparation-v1"] = "8b-pair-preparation-v1"


@dataclass(frozen=True, slots=True)
class PairPreparationParameters:
    version: Literal["8b-pair-preparation-v1"] = PAIR_PREPARATION_VERSION
    required_registration_state: Literal["reliable"] = "reliable"
    required_correction_states: tuple[str, ...] = ("applied", "not_needed")
    joint_valid_policy: str = "inside_aoi_and_all_required_bands_valid_on_both_dates"
    joint_usable_policy: str = (
        "joint_valid_and_qa_usable_on_both_dates_excluding_cloud_cirrus_cloud_shadow_"
        "cast_shadow_snow_missing_unknown_and_outside_aoi"
    )
    area_method: Literal["projected_grid_cell_count"] = "projected_grid_cell_count"


@dataclass(frozen=True, slots=True)
class PairPreparationReason:
    code: str
    explanation: str
    corrective_action: str


@dataclass(frozen=True, slots=True)
class PairObservedCoverage:
    denominator_name: Literal["inside_aoi"]
    aoi_pixels: int
    joint_valid_pixels: int
    joint_valid_percent: float
    joint_usable_pixels: int
    joint_usable_percent: float
    pixel_area_square_metres: float
    joint_valid_area_square_metres: float
    joint_usable_area_square_metres: float


@dataclass(frozen=True, slots=True)
class PairPreparationOutcome:
    state: Literal["comparable", "rejected"]
    comparison_allowed: bool
    processing_version: Literal["8b-pair-preparation-v1"]
    parameters: PairPreparationParameters
    sources: tuple[ViewerSceneIdentity, ViewerSceneIdentity]
    acquired_at: tuple[datetime | None, datetime | None]
    band_order: tuple[str, ...]
    grid: OutputGrid
    registration_state: str
    correction_state: str
    joint_valid: np.ndarray
    joint_usable: np.ndarray
    coverage: PairObservedCoverage
    reasons: tuple[PairPreparationReason, ...]


class PairPreparationService:
    """Assess whether a Phase 6 optical pair is safe input for later change analysis."""

    def __init__(self, parameters: PairPreparationParameters | None = None) -> None:
        self._parameters = parameters or PairPreparationParameters()

    def prepare(
        self,
        request: PreparationRequest,
        grid: CommonGridResult,
        registration: RegistrationResult,
        acquisition_evidence: tuple[SceneAcquisitionEvidence, ...],
    ) -> PairPreparationOutcome:
        reasons: list[PairPreparationReason] = []
        if request.intended_task != "optical_pair" or len(request.scenes) != 2:
            raise ValueError("8B pair preparation requires an optical_pair request with two scenes")
        if len(grid.scenes) != 2:
            raise ValueError("8B pair preparation requires exactly two common-grid scenes")
        if registration.original is not grid:
            raise ValueError("registration evidence must refer to the supplied common grid")

        acquired_at = _validate_acquisitions(request, acquisition_evidence, reasons)
        scenes = _effective_scenes(grid, registration)
        band_order, grid_consistent = _validate_bands_and_grid(request, grid, scenes, reasons)
        _validate_quality(scenes, reasons)

        if grid_consistent:
            joint_valid, joint_usable = _joint_masks(grid, scenes)
        else:
            shape = (grid.grid.height, grid.grid.width)
            joint_valid = np.zeros(shape, dtype=bool)
            joint_usable = np.zeros(shape, dtype=bool)
        aoi_pixels = int(grid.aoi_mask.sum())
        joint_valid_pixels = int(joint_valid.sum())
        joint_usable_pixels = int(joint_usable.sum())
        if grid_consistent and joint_valid_pixels == 0:
            reasons.append(
                PairPreparationReason(
                    code="no_spatial_overlap",
                    explanation=(
                        "The two dates have no pixel that is inside the AOI and valid in all "
                        "required bands on both dates."
                    ),
                    corrective_action="Choose scenes with actual valid-data overlap over the AOI.",
                )
            )
        elif grid_consistent and joint_usable_pixels == 0:
            reasons.append(
                PairPreparationReason(
                    code="no_joint_usable_area",
                    explanation=(
                        "All overlapping valid pixels are excluded by quality information on at "
                        "least one date."
                    ),
                    corrective_action=(
                        "Choose dates with clear, valid observations on both sides of the pair."
                    ),
                )
            )

        assessment = registration.assessment
        if assessment.state != self._parameters.required_registration_state:
            reasons.append(
                PairPreparationReason(
                    code="registration_unreliable",
                    explanation=(
                        f"Registration is {assessment.state}; matching CRS and pixels do not "
                        "establish feature alignment."
                    ),
                    corrective_action=(
                        "Use a pair with distributed texture and agreeing held-out registration "
                        "evidence."
                    ),
                )
            )
        elif assessment.correction_state not in self._parameters.required_correction_states:
            reasons.append(
                PairPreparationReason(
                    code="registration_correction_unaccepted",
                    explanation=(
                        f"Registration correction state '{assessment.correction_state}' is not "
                        "accepted for comparison."
                    ),
                    corrective_action="Use a pair whose correction is validated or not needed.",
                )
            )

        pixel_area = projected_pixel_area_square_metres(grid.grid)
        coverage = PairObservedCoverage(
            denominator_name="inside_aoi",
            aoi_pixels=aoi_pixels,
            joint_valid_pixels=joint_valid_pixels,
            joint_valid_percent=100.0 * joint_valid_pixels / aoi_pixels,
            joint_usable_pixels=joint_usable_pixels,
            joint_usable_percent=100.0 * joint_usable_pixels / aoi_pixels,
            pixel_area_square_metres=pixel_area,
            joint_valid_area_square_metres=joint_valid_pixels * pixel_area,
            joint_usable_area_square_metres=joint_usable_pixels * pixel_area,
        )
        comparable = not reasons
        return PairPreparationOutcome(
            state="comparable" if comparable else "rejected",
            comparison_allowed=comparable,
            processing_version=self._parameters.version,
            parameters=self._parameters,
            sources=(request.scenes[0], request.scenes[1]),
            acquired_at=acquired_at,
            band_order=band_order,
            grid=grid.grid,
            registration_state=assessment.state,
            correction_state=assessment.correction_state,
            joint_valid=joint_valid,
            joint_usable=joint_usable,
            coverage=coverage,
            reasons=tuple(reasons),
        )


def _validate_acquisitions(
    request: PreparationRequest,
    evidence: tuple[SceneAcquisitionEvidence, ...],
    reasons: list[PairPreparationReason],
) -> tuple[datetime | None, datetime | None]:
    by_scene = {item.scene.model_dump_json(): item for item in evidence}
    ordered = tuple(by_scene.get(scene.model_dump_json()) for scene in request.scenes)
    first = ordered[0].acquired_at if ordered[0] is not None else None
    second = ordered[1].acquired_at if ordered[1] is not None else None
    acquired = (first, second)
    if any(item is None for item in ordered) or any(value is None for value in acquired):
        reasons.append(
            PairPreparationReason(
                code="acquisition_time_unavailable",
                explanation="Both source acquisitions require authoritative UTC timestamps.",
                corrective_action="Refresh both scenes from the trusted catalogue provider.",
            )
        )
    elif first is not None and second is not None and first >= second:
        reasons.append(
            PairPreparationReason(
                code="dates_not_chronological",
                explanation="The first source must be acquired before the second source.",
                corrective_action="Submit the earlier acquisition first and the later one second.",
            )
        )
    return acquired


def _effective_scenes(
    grid: CommonGridResult, registration: RegistrationResult
) -> tuple[HarmonizedScene, HarmonizedScene]:
    moving = registration.corrected_moving_scene or grid.scenes[1]
    return grid.scenes[0], moving


def _validate_bands_and_grid(
    request: PreparationRequest,
    grid: CommonGridResult,
    scenes: tuple[HarmonizedScene, HarmonizedScene],
    reasons: list[PairPreparationReason],
) -> tuple[tuple[str, ...], bool]:
    expected = tuple(band.role for band in request.required_bands)
    if scenes[0].band_order != expected or scenes[1].band_order != expected:
        reasons.append(
            PairPreparationReason(
                code="incompatible_bands",
                explanation="Both dates must contain the same required bands in the same order.",
                corrective_action="Prepare both dates with one compatible required-band list.",
            )
        )
    shape = (grid.grid.height, grid.grid.width)
    grid_consistent = True
    for scene in scenes:
        quality_shapes = (
            scene.quality.outside_aoi,
            scene.quality.missing_or_invalid,
            scene.quality.clouds_or_cirrus,
            scene.quality.cloud_shadows,
            scene.quality.cast_shadows,
            scene.quality.snow_or_ice,
            scene.quality.unknown_quality,
            scene.quality.usable,
        )
        consistent = (
            scene.data.shape == (len(scene.band_order), *shape)
            and scene.band_validity.shape == scene.data.shape
            and scene.valid_data.shape == shape
            and all(mask.shape == shape for mask in quality_shapes)
            and isclose(scene.output_resolution_metres, grid.grid.resolution_metres[0])
        )
        if not consistent:
            grid_consistent = False
            reasons.append(
                PairPreparationReason(
                    code="grid_mismatch",
                    explanation=(
                        "A prepared scene does not match the declared common CRS, transform, "
                        "dimensions, band count, or pixel size."
                    ),
                    corrective_action="Re-run Phase 6 common-grid preparation for both dates.",
                )
            )
            break
    return expected, grid_consistent


def _validate_quality(
    scenes: tuple[HarmonizedScene, HarmonizedScene], reasons: list[PairPreparationReason]
) -> None:
    if any(scene.quality.quality_information != "available" for scene in scenes):
        reasons.append(
            PairPreparationReason(
                code="quality_information_unavailable",
                explanation=(
                    "Actual quality information is required on both dates; missing QA does not "
                    "mean clear conditions."
                ),
                corrective_action="Use scenes with readable supported Sentinel-2 SCL assets.",
            )
        )


def _joint_masks(
    grid: CommonGridResult, scenes: tuple[HarmonizedScene, HarmonizedScene]
) -> tuple[np.ndarray, np.ndarray]:
    joint_valid = grid.aoi_mask.copy()
    quality_usable: list[np.ndarray] = []
    for scene in scenes:
        joint_valid &= scene.valid_data
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
        quality_usable.append(grid.aoi_mask & scene.valid_data & quality.usable & ~excluded)
    joint_usable = joint_valid & quality_usable[0] & quality_usable[1]
    return joint_valid, joint_usable
