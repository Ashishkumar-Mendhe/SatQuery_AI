from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal, cast

import numpy as np

from satquery.processing.grid import (
    AreaCoverageStatistic,
    CommonGridResult,
    HarmonizedQualityMasks,
    HarmonizedScene,
)
from satquery.processing.quality import SCL_UNKNOWN

RegistrationState = Literal["reliable", "inconclusive", "unsupported"]
PatchPurpose = Literal["estimate", "validate"]
CorrectionState = Literal["applied", "not_needed", "rejected", "not_supported"]


class RegistrationAssessmentError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class RegistrationParameters:
    band_role: str = "red"
    patch_grid_rows: int = 3
    patch_grid_columns: int = 3
    max_translation_pixels: int = 6
    min_patch_size_pixels: int = 24
    min_valid_pixels: int = 128
    min_valid_fraction: float = 0.50
    min_texture_standard_deviation: float = 0.002
    min_patch_correlation: float = 0.55
    min_peak_margin: float = 0.01
    agreement_tolerance_pixels: float = 0.75
    min_agreement_fraction: float = 0.60
    min_estimation_patches: int = 3
    min_validation_patches: int = 2
    min_residual_correlation: float = 0.55
    min_validation_improvement: float = 0.03

    def __post_init__(self) -> None:
        if self.patch_grid_rows < 2 or self.patch_grid_columns < 2:
            raise ValueError("registration requires at least a 2 by 2 patch grid")
        if self.max_translation_pixels < 1 or self.max_translation_pixels > 16:
            raise ValueError("max_translation_pixels must be between 1 and 16")
        if self.min_patch_size_pixels < 8:
            raise ValueError("min_patch_size_pixels must be at least 8")
        if self.min_valid_pixels < 16:
            raise ValueError("min_valid_pixels must be at least 16")
        for name, value in (
            ("min_valid_fraction", self.min_valid_fraction),
            ("min_agreement_fraction", self.min_agreement_fraction),
        ):
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1]")


@dataclass(frozen=True, slots=True)
class PatchEstimate:
    patch_row: int
    patch_column: int
    purpose: PatchPurpose
    bounds_pixels: tuple[int, int, int, int]
    centre_fraction: tuple[float, float]
    usable: bool
    reason: str | None
    row_shift_pixels: int | None
    column_shift_pixels: int | None
    correlation: float | None
    second_best_correlation: float | None
    peak_margin: float | None
    valid_pixels: int
    valid_fraction: float
    reference_texture_standard_deviation: float | None
    moving_texture_standard_deviation: float | None
    search_boundary_hit: bool


@dataclass(frozen=True, slots=True)
class PatchDistribution:
    total_patches: int
    usable_patches: int
    usable_estimation_patches: int
    usable_validation_patches: int
    represented_rows: int
    represented_columns: int
    centre_extent_fraction: tuple[float, float]


@dataclass(frozen=True, slots=True)
class EstimateAgreement:
    estimate_count: int
    inlier_count: int
    inlier_fraction: float | None
    tolerance_pixels: float
    median_row_shift_pixels: float | None
    median_column_shift_pixels: float | None
    maximum_inlier_deviation_pixels: float | None
    agrees: bool


@dataclass(frozen=True, slots=True)
class ResidualAlignmentEvidence:
    validation_patch_count: int
    median_correlation_before: float | None
    median_correlation_after: float | None
    median_improvement: float | None
    improved_patch_count: int
    required_improvement: float
    improved: bool


@dataclass(frozen=True, slots=True)
class AppliedTranslation:
    model: Literal["integer_translation"]
    row_shift_pixels: int
    column_shift_pixels: int
    x_shift_map_units: float
    y_shift_map_units: float
    map_units: Literal["metres"]
    affine_matrix: tuple[float, float, float, float, float, float, float, float, float]
    interpolation: Literal["integer_copy"]
    explanation: str


@dataclass(frozen=True, slots=True)
class RegistrationAssessment:
    state: RegistrationState
    explanation: str
    method: Literal["distributed_masked_zncc_integer_translation"]
    coordinate_convention: str
    band_role: str
    estimated_row_shift_pixels: int | None
    estimated_column_shift_pixels: int | None
    estimated_x_shift_map_units: float | None
    estimated_y_shift_map_units: float | None
    map_displacement_units: Literal["metres"]
    patches: tuple[PatchEstimate, ...]
    distribution: PatchDistribution
    agreement: EstimateAgreement
    residual: ResidualAlignmentEvidence
    correction_state: CorrectionState
    correction: AppliedTranslation | None


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    original: CommonGridResult
    assessment: RegistrationAssessment
    corrected_moving_scene: HarmonizedScene | None
    corrected_joint_valid_data: np.ndarray | None
    corrected_joint_usable: np.ndarray | None
    corrected_pair_coverage: tuple[AreaCoverageStatistic, ...]


class RegistrationService:
    """Assess a same-sensor pair and optionally apply one validated integer translation."""

    def __init__(self, parameters: RegistrationParameters | None = None) -> None:
        self._parameters = parameters or RegistrationParameters()

    def assess_and_correct(self, pair: CommonGridResult) -> RegistrationResult:
        unsupported = _unsupported_reason(pair, self._parameters)
        if unsupported is not None:
            return _result_without_correction(
                pair,
                _empty_assessment(
                    self._parameters,
                    state="unsupported",
                    explanation=unsupported,
                    correction_state="not_supported",
                ),
            )
        reference, moving = pair.scenes
        band_index = reference.band_order.index(self._parameters.band_role)
        reference_band = reference.data[band_index]
        moving_band = moving.data[band_index]
        reference_mask = reference.band_validity[band_index] & reference.quality.usable
        moving_mask = moving.band_validity[band_index] & moving.quality.usable
        patches = _assess_patches(
            reference_band,
            moving_band,
            reference_mask,
            moving_mask,
            self._parameters,
        )
        distribution = _distribution(patches, self._parameters)
        estimates = tuple(
            patch for patch in patches if patch.purpose == "estimate" and patch.usable
        )
        agreement = _agreement(estimates, self._parameters)
        if not agreement.agrees:
            assessment = RegistrationAssessment(
                state="inconclusive",
                explanation=(
                    "Usable distributed patch estimates were insufficient or did not agree; "
                    "matching grid metadata and isolated correlations are not registration proof."
                ),
                method="distributed_masked_zncc_integer_translation",
                coordinate_convention=_COORDINATE_CONVENTION,
                band_role=self._parameters.band_role,
                estimated_row_shift_pixels=None,
                estimated_column_shift_pixels=None,
                estimated_x_shift_map_units=None,
                estimated_y_shift_map_units=None,
                map_displacement_units="metres",
                patches=patches,
                distribution=distribution,
                agreement=agreement,
                residual=_empty_residual(self._parameters),
                correction_state="rejected",
                correction=None,
            )
            return _result_without_correction(pair, assessment)

        row_shift = round(cast(float, agreement.median_row_shift_pixels))
        column_shift = round(cast(float, agreement.median_column_shift_pixels))
        residual = _residual_evidence(
            patches,
            reference_band,
            moving_band,
            reference_mask,
            moving_mask,
            row_shift,
            column_shift,
            self._parameters,
        )
        x_shift = column_shift * pair.grid.transform[0]
        y_shift = row_shift * pair.grid.transform[4]
        if row_shift == 0 and column_shift == 0:
            reliable = (
                residual.validation_patch_count >= self._parameters.min_validation_patches
                and residual.median_correlation_after is not None
                and residual.median_correlation_after >= self._parameters.min_residual_correlation
            )
            assessment = RegistrationAssessment(
                state="reliable" if reliable else "inconclusive",
                explanation=(
                    "Distributed estimates and held-out patches support zero integer-pixel "
                    "translation; no correction is needed."
                    if reliable
                    else "The estimated translation is zero, but held-out residual evidence is "
                    "insufficient to call registration reliable."
                ),
                method="distributed_masked_zncc_integer_translation",
                coordinate_convention=_COORDINATE_CONVENTION,
                band_role=self._parameters.band_role,
                estimated_row_shift_pixels=row_shift,
                estimated_column_shift_pixels=column_shift,
                estimated_x_shift_map_units=x_shift,
                estimated_y_shift_map_units=y_shift,
                map_displacement_units="metres",
                patches=patches,
                distribution=distribution,
                agreement=agreement,
                residual=residual,
                correction_state="not_needed" if reliable else "rejected",
                correction=None,
            )
            return _result_without_correction(pair, assessment)

        if not residual.improved:
            assessment = RegistrationAssessment(
                state="inconclusive",
                explanation=(
                    "Patch estimates agreed, but the proposed translation did not produce the "
                    "required improvement on independent held-out patches."
                ),
                method="distributed_masked_zncc_integer_translation",
                coordinate_convention=_COORDINATE_CONVENTION,
                band_role=self._parameters.band_role,
                estimated_row_shift_pixels=row_shift,
                estimated_column_shift_pixels=column_shift,
                estimated_x_shift_map_units=x_shift,
                estimated_y_shift_map_units=y_shift,
                map_displacement_units="metres",
                patches=patches,
                distribution=distribution,
                agreement=agreement,
                residual=residual,
                correction_state="rejected",
                correction=None,
            )
            return _result_without_correction(pair, assessment)

        correction = AppliedTranslation(
            model="integer_translation",
            row_shift_pixels=row_shift,
            column_shift_pixels=column_shift,
            x_shift_map_units=x_shift,
            y_shift_map_units=y_shift,
            map_units="metres",
            affine_matrix=(
                1.0,
                0.0,
                float(column_shift),
                0.0,
                1.0,
                float(row_shift),
                0.0,
                0.0,
                1.0,
            ),
            interpolation="integer_copy",
            explanation=(
                "The moving scene is copied by the accepted integer translation; originals are "
                "retained and no flexible warp or radiometric adjustment is applied."
            ),
        )
        corrected = _translate_scene(moving, pair, row_shift, column_shift)
        joint_valid = reference.valid_data & corrected.valid_data
        joint_usable = reference.quality.usable & corrected.quality.usable
        coverage = _pair_coverage(pair, joint_valid, joint_usable)
        assessment = RegistrationAssessment(
            state="reliable",
            explanation=(
                "Distributed estimates agreed and the bounded translation improved independent "
                "held-out residual evidence."
            ),
            method="distributed_masked_zncc_integer_translation",
            coordinate_convention=_COORDINATE_CONVENTION,
            band_role=self._parameters.band_role,
            estimated_row_shift_pixels=row_shift,
            estimated_column_shift_pixels=column_shift,
            estimated_x_shift_map_units=x_shift,
            estimated_y_shift_map_units=y_shift,
            map_displacement_units="metres",
            patches=patches,
            distribution=distribution,
            agreement=agreement,
            residual=residual,
            correction_state="applied",
            correction=correction,
        )
        return RegistrationResult(
            original=pair,
            assessment=assessment,
            corrected_moving_scene=corrected,
            corrected_joint_valid_data=joint_valid,
            corrected_joint_usable=joint_usable,
            corrected_pair_coverage=coverage,
        )


_COORDINATE_CONVENTION = (
    "Shift applied to moving scene B to align it with reference scene A; positive row is "
    "toward increasing array row/south and positive column is east. Map displacement uses "
    "the declared affine pixel vectors, so north-up positive row has negative y."
)


def _unsupported_reason(pair: CommonGridResult, parameters: RegistrationParameters) -> str | None:
    if len(pair.scenes) != 2:
        return "Registration assessment requires exactly two harmonized scenes."
    reference, moving = pair.scenes
    if (
        reference.scene.provider != moving.scene.provider
        or reference.scene.collection != moving.scene.collection
        or reference.scene.collection != "sentinel-2-c1-l2a"
    ):
        return "Task 6E supports only same-provider Sentinel-2 L2A optical pairs."
    if parameters.band_role not in reference.band_order or (
        parameters.band_role not in moving.band_order
    ):
        return f"Comparable band role '{parameters.band_role}' is unavailable in both scenes."
    if (
        reference.quality.quality_information != "available"
        or moving.quality.quality_information != "available"
    ):
        return "Actual quality masks are required to exclude clouds, shadows, and unknown pixels."
    if reference.data.shape != moving.data.shape:
        return "Registration inputs must already share the declared common-grid shape."
    height, width = reference.data.shape[1:]
    if (
        height < parameters.patch_grid_rows * parameters.min_patch_size_pixels
        or width < parameters.patch_grid_columns * parameters.min_patch_size_pixels
    ):
        return "The common-grid AOI is too small for the required distributed patch assessment."
    return None


def _assess_patches(
    reference: np.ndarray,
    moving: np.ndarray,
    reference_mask: np.ndarray,
    moving_mask: np.ndarray,
    parameters: RegistrationParameters,
) -> tuple[PatchEstimate, ...]:
    height, width = reference.shape
    row_edges = np.linspace(0, height, parameters.patch_grid_rows + 1, dtype=int)
    column_edges = np.linspace(0, width, parameters.patch_grid_columns + 1, dtype=int)
    results: list[PatchEstimate] = []
    for patch_row in range(parameters.patch_grid_rows):
        for patch_column in range(parameters.patch_grid_columns):
            bounds = (
                int(row_edges[patch_row]),
                int(row_edges[patch_row + 1]),
                int(column_edges[patch_column]),
                int(column_edges[patch_column + 1]),
            )
            purpose: PatchPurpose = (
                "estimate" if (patch_row + patch_column) % 2 == 0 else "validate"
            )
            results.append(
                _estimate_patch(
                    reference,
                    moving,
                    reference_mask,
                    moving_mask,
                    bounds,
                    patch_row,
                    patch_column,
                    purpose,
                    parameters,
                )
            )
    return tuple(results)


def _estimate_patch(
    reference: np.ndarray,
    moving: np.ndarray,
    reference_mask: np.ndarray,
    moving_mask: np.ndarray,
    bounds: tuple[int, int, int, int],
    patch_row: int,
    patch_column: int,
    purpose: PatchPurpose,
    parameters: RegistrationParameters,
) -> PatchEstimate:
    r0, r1, c0, c1 = bounds
    area = (r1 - r0) * (c1 - c0)
    centre = ((r0 + r1) / (2 * reference.shape[0]), (c0 + c1) / (2 * reference.shape[1]))
    candidates: list[tuple[float, int, int, int, float, float]] = []
    for row_shift in range(
        -parameters.max_translation_pixels, parameters.max_translation_pixels + 1
    ):
        for column_shift in range(
            -parameters.max_translation_pixels, parameters.max_translation_pixels + 1
        ):
            scored = _score_patch(
                reference,
                moving,
                reference_mask,
                moving_mask,
                bounds,
                row_shift,
                column_shift,
                parameters,
            )
            if scored is not None:
                score, valid_pixels, reference_texture, moving_texture = scored
                candidates.append(
                    (
                        score,
                        row_shift,
                        column_shift,
                        valid_pixels,
                        reference_texture,
                        moving_texture,
                    )
                )
    if not candidates:
        return _unusable_patch(
            patch_row, patch_column, purpose, bounds, centre, "insufficient_valid_texture"
        )
    candidates.sort(key=lambda item: item[0], reverse=True)
    best = candidates[0]
    second = candidates[1][0] if len(candidates) > 1 else None
    margin = None if second is None else best[0] - second
    boundary_hit = (
        abs(best[1]) == parameters.max_translation_pixels
        or abs(best[2]) == parameters.max_translation_pixels
    )
    reason: str | None = None
    if best[0] < parameters.min_patch_correlation:
        reason = "correlation_below_threshold"
    elif margin is None or margin < parameters.min_peak_margin:
        reason = "ambiguous_correlation_peak"
    elif boundary_hit:
        reason = "estimate_reached_search_boundary"
    return PatchEstimate(
        patch_row=patch_row,
        patch_column=patch_column,
        purpose=purpose,
        bounds_pixels=bounds,
        centre_fraction=centre,
        usable=reason is None,
        reason=reason,
        row_shift_pixels=best[1],
        column_shift_pixels=best[2],
        correlation=best[0],
        second_best_correlation=second,
        peak_margin=margin,
        valid_pixels=best[3],
        valid_fraction=best[3] / area,
        reference_texture_standard_deviation=best[4],
        moving_texture_standard_deviation=best[5],
        search_boundary_hit=boundary_hit,
    )


def _score_patch(
    reference: np.ndarray,
    moving: np.ndarray,
    reference_mask: np.ndarray,
    moving_mask: np.ndarray,
    bounds: tuple[int, int, int, int],
    row_shift: int,
    column_shift: int,
    parameters: RegistrationParameters,
) -> tuple[float, int, float, float] | None:
    r0, r1, c0, c1 = bounds
    height, width = reference.shape
    out_r0 = max(r0, row_shift, 0)
    out_r1 = min(r1, height + row_shift, height)
    out_c0 = max(c0, column_shift, 0)
    out_c1 = min(c1, width + column_shift, width)
    if out_r1 <= out_r0 or out_c1 <= out_c0:
        return None
    reference_slice = np.s_[out_r0:out_r1, out_c0:out_c1]
    moving_slice = np.s_[
        out_r0 - row_shift : out_r1 - row_shift,
        out_c0 - column_shift : out_c1 - column_shift,
    ]
    valid = (
        reference_mask[reference_slice]
        & moving_mask[moving_slice]
        & np.isfinite(reference[reference_slice])
        & np.isfinite(moving[moving_slice])
    )
    valid_pixels = int(valid.sum())
    patch_area = (r1 - r0) * (c1 - c0)
    if (
        valid_pixels < parameters.min_valid_pixels
        or valid_pixels / patch_area < parameters.min_valid_fraction
    ):
        return None
    reference_values = reference[reference_slice][valid].astype(np.float64, copy=False)
    moving_values = moving[moving_slice][valid].astype(np.float64, copy=False)
    reference_texture = float(np.std(reference_values))
    moving_texture = float(np.std(moving_values))
    if (
        reference_texture < parameters.min_texture_standard_deviation
        or moving_texture < parameters.min_texture_standard_deviation
    ):
        return None
    normalized_reference = (reference_values - float(np.mean(reference_values))) / reference_texture
    normalized_moving = (moving_values - float(np.mean(moving_values))) / moving_texture
    correlation = float(np.mean(normalized_reference * normalized_moving))
    if not math.isfinite(correlation):
        return None
    return correlation, valid_pixels, reference_texture, moving_texture


def _unusable_patch(
    patch_row: int,
    patch_column: int,
    purpose: PatchPurpose,
    bounds: tuple[int, int, int, int],
    centre: tuple[float, float],
    reason: str,
) -> PatchEstimate:
    return PatchEstimate(
        patch_row=patch_row,
        patch_column=patch_column,
        purpose=purpose,
        bounds_pixels=bounds,
        centre_fraction=centre,
        usable=False,
        reason=reason,
        row_shift_pixels=None,
        column_shift_pixels=None,
        correlation=None,
        second_best_correlation=None,
        peak_margin=None,
        valid_pixels=0,
        valid_fraction=0.0,
        reference_texture_standard_deviation=None,
        moving_texture_standard_deviation=None,
        search_boundary_hit=False,
    )


def _distribution(
    patches: tuple[PatchEstimate, ...], parameters: RegistrationParameters
) -> PatchDistribution:
    usable = [patch for patch in patches if patch.usable]
    rows = {patch.patch_row for patch in usable}
    columns = {patch.patch_column for patch in usable}
    if usable:
        row_centres = [patch.centre_fraction[0] for patch in usable]
        column_centres = [patch.centre_fraction[1] for patch in usable]
        extent = (max(row_centres) - min(row_centres), max(column_centres) - min(column_centres))
    else:
        extent = (0.0, 0.0)
    return PatchDistribution(
        total_patches=parameters.patch_grid_rows * parameters.patch_grid_columns,
        usable_patches=len(usable),
        usable_estimation_patches=sum(patch.purpose == "estimate" for patch in usable),
        usable_validation_patches=sum(patch.purpose == "validate" for patch in usable),
        represented_rows=len(rows),
        represented_columns=len(columns),
        centre_extent_fraction=extent,
    )


def _agreement(
    estimates: tuple[PatchEstimate, ...], parameters: RegistrationParameters
) -> EstimateAgreement:
    if not estimates:
        return EstimateAgreement(
            0, 0, None, parameters.agreement_tolerance_pixels, None, None, None, False
        )
    rows = np.array([cast(int, patch.row_shift_pixels) for patch in estimates], dtype=float)
    columns = np.array([cast(int, patch.column_shift_pixels) for patch in estimates], dtype=float)
    median_row = float(np.median(rows))
    median_column = float(np.median(columns))
    deviations = np.hypot(rows - median_row, columns - median_column)
    inliers = deviations <= parameters.agreement_tolerance_pixels
    inlier_count = int(inliers.sum())
    fraction = inlier_count / len(estimates)
    inlier_patches = [patch for patch, selected in zip(estimates, inliers, strict=True) if selected]
    distributed = (
        len({patch.patch_row for patch in inlier_patches}) >= 2
        and len({patch.patch_column for patch in inlier_patches}) >= 2
    )
    integer_consensus = (
        abs(median_row - round(median_row)) <= 0.25
        and abs(median_column - round(median_column)) <= 0.25
    )
    agrees = (
        len(estimates) >= parameters.min_estimation_patches
        and inlier_count >= parameters.min_estimation_patches
        and fraction >= parameters.min_agreement_fraction
        and distributed
        and integer_consensus
    )
    return EstimateAgreement(
        estimate_count=len(estimates),
        inlier_count=inlier_count,
        inlier_fraction=fraction,
        tolerance_pixels=parameters.agreement_tolerance_pixels,
        median_row_shift_pixels=median_row,
        median_column_shift_pixels=median_column,
        maximum_inlier_deviation_pixels=(
            float(np.max(deviations[inliers])) if inlier_count else None
        ),
        agrees=agrees,
    )


def _residual_evidence(
    patches: tuple[PatchEstimate, ...],
    reference: np.ndarray,
    moving: np.ndarray,
    reference_mask: np.ndarray,
    moving_mask: np.ndarray,
    row_shift: int,
    column_shift: int,
    parameters: RegistrationParameters,
) -> ResidualAlignmentEvidence:
    before: list[float] = []
    after: list[float] = []
    for patch in patches:
        if patch.purpose != "validate":
            continue
        before_score = _score_patch(
            reference,
            moving,
            reference_mask,
            moving_mask,
            patch.bounds_pixels,
            0,
            0,
            parameters,
        )
        after_score = _score_patch(
            reference,
            moving,
            reference_mask,
            moving_mask,
            patch.bounds_pixels,
            row_shift,
            column_shift,
            parameters,
        )
        if before_score is not None and after_score is not None:
            before.append(before_score[0])
            after.append(after_score[0])
    if not before:
        return _empty_residual(parameters)
    improvements = np.asarray(after) - np.asarray(before)
    median_before = float(np.median(before))
    median_after = float(np.median(after))
    median_improvement = float(np.median(improvements))
    improved_count = int(np.sum(improvements > 0.01))
    required_count = math.ceil(len(before) * parameters.min_agreement_fraction)
    improved = (
        len(before) >= parameters.min_validation_patches
        and median_after >= parameters.min_residual_correlation
        and median_improvement >= parameters.min_validation_improvement
        and improved_count >= required_count
    )
    return ResidualAlignmentEvidence(
        validation_patch_count=len(before),
        median_correlation_before=median_before,
        median_correlation_after=median_after,
        median_improvement=median_improvement,
        improved_patch_count=improved_count,
        required_improvement=parameters.min_validation_improvement,
        improved=improved,
    )


def _empty_residual(parameters: RegistrationParameters) -> ResidualAlignmentEvidence:
    return ResidualAlignmentEvidence(
        validation_patch_count=0,
        median_correlation_before=None,
        median_correlation_after=None,
        median_improvement=None,
        improved_patch_count=0,
        required_improvement=parameters.min_validation_improvement,
        improved=False,
    )


def _empty_assessment(
    parameters: RegistrationParameters,
    *,
    state: RegistrationState,
    explanation: str,
    correction_state: CorrectionState,
) -> RegistrationAssessment:
    return RegistrationAssessment(
        state=state,
        explanation=explanation,
        method="distributed_masked_zncc_integer_translation",
        coordinate_convention=_COORDINATE_CONVENTION,
        band_role=parameters.band_role,
        estimated_row_shift_pixels=None,
        estimated_column_shift_pixels=None,
        estimated_x_shift_map_units=None,
        estimated_y_shift_map_units=None,
        map_displacement_units="metres",
        patches=(),
        distribution=PatchDistribution(0, 0, 0, 0, 0, 0, (0.0, 0.0)),
        agreement=EstimateAgreement(
            0, 0, None, parameters.agreement_tolerance_pixels, None, None, None, False
        ),
        residual=_empty_residual(parameters),
        correction_state=correction_state,
        correction=None,
    )


def _result_without_correction(
    pair: CommonGridResult, assessment: RegistrationAssessment
) -> RegistrationResult:
    return RegistrationResult(
        original=pair,
        assessment=assessment,
        corrected_moving_scene=None,
        corrected_joint_valid_data=None,
        corrected_joint_usable=None,
        corrected_pair_coverage=(),
    )


def _translate_scene(
    scene: HarmonizedScene,
    pair: CommonGridResult,
    row_shift: int,
    column_shift: int,
) -> HarmonizedScene:
    data = np.stack(
        [_translate_array(band, row_shift, column_shift, np.nan) for band in scene.data]
    ).astype(np.float32, copy=False)
    band_validity = np.stack(
        [_translate_array(mask, row_shift, column_shift, False) for mask in scene.band_validity]
    ).astype(bool, copy=False)
    band_validity &= pair.aoi_mask[np.newaxis, :, :] & np.isfinite(data)
    data[~band_validity] = np.nan
    valid_data = pair.aoi_mask & np.all(band_validity, axis=0)
    quality = _translate_quality(scene.quality, pair.aoi_mask, valid_data, row_shift, column_shift)
    pixel_area = pair.grid.resolution_metres[0] * pair.grid.resolution_metres[1]
    aoi_pixels = int(pair.aoi_mask.sum())
    return replace(
        scene,
        data=data,
        band_validity=band_validity,
        valid_data=valid_data,
        quality=quality,
        coverage=(
            _stat("valid_data", valid_data, "inside_aoi", aoi_pixels, pixel_area),
            _stat("usable", quality.usable, "inside_aoi", aoi_pixels, pixel_area),
        ),
    )


def _translate_quality(
    quality: HarmonizedQualityMasks,
    aoi_mask: np.ndarray,
    valid_data: np.ndarray,
    row_shift: int,
    column_shift: int,
) -> HarmonizedQualityMasks:
    translated_missing = _translate_array(
        quality.missing_or_invalid, row_shift, column_shift, False
    ).astype(bool, copy=False)

    def shifted(mask: np.ndarray) -> np.ndarray:
        return cast(
            np.ndarray,
            aoi_mask
            & _translate_array(mask, row_shift, column_shift, False).astype(bool, copy=False),
        )

    missing = aoi_mask & (~valid_data | translated_missing)
    clouds = shifted(quality.clouds_or_cirrus)
    cloud_shadows = shifted(quality.cloud_shadows)
    cast_shadows = shifted(quality.cast_shadows)
    snow = shifted(quality.snow_or_ice)
    unknown = shifted(quality.unknown_quality)
    usable = valid_data & shifted(quality.usable)
    excluded = aoi_mask & (missing | clouds | cloud_shadows | cast_shadows | snow | unknown)
    classes = _translate_array(quality.scl_classes, row_shift, column_shift, SCL_UNKNOWN).astype(
        np.uint8, copy=False
    )
    classes[~aoi_mask] = SCL_UNKNOWN
    return replace(
        quality,
        scl_classes=classes,
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


def _translate_array(
    source: np.ndarray, row_shift: int, column_shift: int, fill: object
) -> np.ndarray:
    destination = np.full(source.shape, fill, dtype=source.dtype)
    height, width = source.shape
    destination_r0 = max(0, row_shift)
    destination_r1 = min(height, height + row_shift)
    destination_c0 = max(0, column_shift)
    destination_c1 = min(width, width + column_shift)
    source_r0 = destination_r0 - row_shift
    source_r1 = destination_r1 - row_shift
    source_c0 = destination_c0 - column_shift
    source_c1 = destination_c1 - column_shift
    if destination_r1 > destination_r0 and destination_c1 > destination_c0:
        destination[destination_r0:destination_r1, destination_c0:destination_c1] = source[
            source_r0:source_r1, source_c0:source_c1
        ]
    return destination


def _pair_coverage(
    pair: CommonGridResult, joint_valid: np.ndarray, joint_usable: np.ndarray
) -> tuple[AreaCoverageStatistic, ...]:
    pixel_area = pair.grid.resolution_metres[0] * pair.grid.resolution_metres[1]
    aoi_pixels = int(pair.aoi_mask.sum())
    joint_valid_pixels = int(joint_valid.sum())
    return (
        _stat("joint_valid_overlap", joint_valid, "inside_aoi", aoi_pixels, pixel_area),
        _stat("joint_usable_inside_aoi", joint_usable, "inside_aoi", aoi_pixels, pixel_area),
        _stat(
            "joint_usable_within_valid_overlap",
            joint_usable,
            "joint_valid_overlap",
            joint_valid_pixels,
            pixel_area,
        ),
    )


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
