"""Deterministic mathematical engine for multimodal optical and SAR evidence fusion."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

import numpy as np
from rasterio.features import shapes
from rasterio.transform import Affine
from rio_tiler.utils import render

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    AOIGeometry,
    GeometryType,
    WarningSeverity,
)
from satquery.api.schemas.fusion import (
    FUSION_SCHEMA_VERSION,
    CoveragePartitionPixelCounts,
    CoveragePartitions,
    FusionQualityBreakdown,
    FusionRegion,
    FusionRuleDefinition,
    FusionRuleId,
    JointObservationState,
    JointStateMetrics,
    JointStatePixelCounts,
    MultimodalTimingMetrics,
    SARCalibrationStatus,
)

logger = logging.getLogger(__name__)

# Joint State RGBA Palette for discrete overlay rendering
FUSION_STATE_RGBA: dict[JointObservationState, tuple[int, int, int, int]] = {
    JointObservationState.BOTH_DETECT_CHANGE: (230, 97, 1, 255),  # Amber / Orange-Red
    JointObservationState.OPTICAL_RESPONSE_ONLY: (44, 162, 95, 230),  # Emerald Green
    JointObservationState.SAR_RESPONSE_ONLY: (43, 131, 186, 230),  # Cobalt Blue
    JointObservationState.NEITHER_ABOVE_THRESHOLD: (160, 160, 160, 80),  # Muted Slate Grey
    JointObservationState.UNCERTAIN: (175, 141, 195, 200),  # Lavender / Purple
}


class FusionCalculationError(RuntimeError):
    """Error raised when evidence fusion fails due to incompatibility or invalid input."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class FusionEngine:
    """Engine for assessing temporal/spatial compatibility, coverage partitioning, and deterministic fusion."""

    @classmethod
    def get_supported_rule_definitions(cls) -> list[FusionRuleDefinition]:
        """Return the list of authoritative, registered fusion rules."""
        return [
            FusionRuleDefinition(
                rule_id=FusionRuleId.CO_OBSERVED_RESPONSE_CHANGE,
                name="Co-Observed Multimodal Response Change",
                version=FUSION_SCHEMA_VERSION,
                description=(
                    "Evaluates the spatial co-occurrence of measured optical and SAR response changes "
                    "across compatible observation windows. Distinguishes both-sensor detections, "
                    "single-modality responses, and stable baseline areas."
                ),
                supported_modalities=["Optical", "SAR"],
                disclaimer=(
                    "Evidence-level fusion reports co-occurring sensor measurements. It does NOT "
                    "establish a confirmed physical cause (e.g. flood, demolition, or vegetation loss). "
                    "Physical interpretations remain unverified hypotheses."
                ),
            )
        ]

    @classmethod
    def assess_temporal_compatibility(
        cls,
        optical_before: datetime,
        optical_after: datetime,
        sar_before: datetime,
        sar_after: datetime,
        temporal_tolerance_days: float = 30.0,
        event_timestamp: datetime | None = None,
    ) -> tuple[MultimodalTimingMetrics, list[str], list[AnalysisWarning]]:
        """Assess temporal ordering, offsets, interval overlap, and event bracketing."""
        blocking_issues: list[str] = []
        warnings: list[AnalysisWarning] = []

        # 1. Ordering within each sensor
        if optical_before >= optical_after:
            blocking_issues.append(
                f"Optical before date ({optical_before.isoformat()}) must precede optical after date ({optical_after.isoformat()})."
            )
        if sar_before >= sar_after:
            blocking_issues.append(
                f"SAR before date ({sar_before.isoformat()}) must precede SAR after date ({sar_after.isoformat()})."
            )

        optical_duration_days = max(0.0, (optical_after - optical_before).total_seconds() / 86400.0)
        sar_duration_days = max(0.0, (sar_after - sar_before).total_seconds() / 86400.0)

        before_offset_days = abs((optical_before - sar_before).total_seconds()) / 86400.0
        after_offset_days = abs((optical_after - sar_after).total_seconds()) / 86400.0

        if before_offset_days > temporal_tolerance_days:
            warnings.append(
                AnalysisWarning(
                    code="TEMPORAL_BEFORE_OFFSET_EXCEEDED",
                    severity=WarningSeverity.MEDIUM,
                    title="Temporal Offset Exceeded",
                    message=(
                        f"Optical and SAR before dates differ by {before_offset_days:.1f} days, "
                        f"exceeding tolerance of {temporal_tolerance_days:.1f} days."
                    ),
                )
            )

        if after_offset_days > temporal_tolerance_days:
            warnings.append(
                AnalysisWarning(
                    code="TEMPORAL_AFTER_OFFSET_EXCEEDED",
                    severity=WarningSeverity.MEDIUM,
                    title="Temporal Offset Exceeded",
                    message=(
                        f"Optical and SAR after dates differ by {after_offset_days:.1f} days, "
                        f"exceeding tolerance of {temporal_tolerance_days:.1f} days."
                    ),
                )
            )

        # Interval Jaccard Overlap
        earliest_start = min(optical_before, sar_before)
        latest_end = max(optical_after, sar_after)
        union_seconds = max(1.0, (latest_end - earliest_start).total_seconds())

        latest_start = max(optical_before, sar_before)
        earliest_end = min(optical_after, sar_after)
        intersection_seconds = max(0.0, (earliest_end - latest_start).total_seconds())
        interval_overlap_ratio = min(1.0, intersection_seconds / union_seconds)

        # Event bracketing check
        bracketed_opt: bool | None = None
        bracketed_sar: bool | None = None
        if event_timestamp is not None:
            bracketed_opt = optical_before <= event_timestamp <= optical_after
            bracketed_sar = sar_before <= event_timestamp <= sar_after
            if not bracketed_opt or not bracketed_sar:
                warnings.append(
                    AnalysisWarning(
                        code="EVENT_NOT_BRACKETED",
                        severity=WarningSeverity.MEDIUM,
                        title="Event Not Bracketed",
                        message=(
                            f"Target event timestamp ({event_timestamp.isoformat()}) is not bracketed by both observation pairs "
                            f"(Optical bracketed: {bracketed_opt}, SAR bracketed: {bracketed_sar})."
                        ),
                    )
                )

        timing = MultimodalTimingMetrics(
            optical_before_timestamp=optical_before,
            optical_after_timestamp=optical_after,
            sar_before_timestamp=sar_before,
            sar_after_timestamp=sar_after,
            optical_duration_days=round(optical_duration_days, 2),
            sar_duration_days=round(sar_duration_days, 2),
            before_offset_days=round(before_offset_days, 2),
            after_offset_days=round(after_offset_days, 2),
            event_timestamp=event_timestamp,
            event_bracketed_by_optical=bracketed_opt,
            event_bracketed_by_sar=bracketed_sar,
            interval_overlap_ratio=round(interval_overlap_ratio, 4),
        )

        return timing, blocking_issues, warnings

    @classmethod
    def compute_coverage_partitions(
        cls,
        optical_valid_mask: np.ndarray[Any, Any],
        sar_valid_mask: np.ndarray[Any, Any],
        aoi_mask: np.ndarray[Any, Any] | None,
        pixel_size_x: float,
        pixel_size_y: float,
    ) -> tuple[CoveragePartitions, dict[str, np.ndarray[Any, Any]]]:
        """Partition the AOI domain into Joint, Optical-only, SAR-only, and Neither coverage zones."""
        height, width = optical_valid_mask.shape
        if aoi_mask is not None:
            aoi_domain = aoi_mask.astype(bool)
        else:
            aoi_domain = np.ones((height, width), dtype=bool)

        opt_valid = optical_valid_mask.astype(bool) & aoi_domain
        sar_valid = sar_valid_mask.astype(bool) & aoi_domain

        joint_mask = opt_valid & sar_valid
        opt_only_mask = opt_valid & (~sar_valid)
        sar_only_mask = sar_valid & (~opt_valid)
        neither_mask = aoi_domain & (~opt_valid) & (~sar_valid)

        total_aoi_px = int(np.sum(aoi_domain))
        joint_px = int(np.sum(joint_mask))
        opt_only_px = int(np.sum(opt_only_mask))
        sar_only_px = int(np.sum(sar_only_mask))
        neither_px = int(np.sum(neither_mask))

        pixel_area_m2 = abs(pixel_size_x * pixel_size_y)
        total_aoi_km2 = (total_aoi_px * pixel_area_m2) / 1_000_000.0
        joint_km2 = (joint_px * pixel_area_m2) / 1_000_000.0
        opt_only_km2 = (opt_only_px * pixel_area_m2) / 1_000_000.0
        sar_only_km2 = (sar_only_px * pixel_area_m2) / 1_000_000.0
        neither_km2 = (neither_px * pixel_area_m2) / 1_000_000.0

        if total_aoi_px > 0:
            joint_pct = round((joint_px / total_aoi_px) * 100.0, 2)
            opt_only_pct = round((opt_only_px / total_aoi_px) * 100.0, 2)
            sar_only_pct = round((sar_only_px / total_aoi_px) * 100.0, 2)
            neither_pct = round((neither_px / total_aoi_px) * 100.0, 2)
        else:
            joint_pct = opt_only_pct = sar_only_pct = neither_pct = 0.0

        partitions = CoveragePartitions(
            total_aoi_area_km2=round(total_aoi_km2, 6),
            jointly_observable_area_km2=round(joint_km2, 6),
            optical_only_area_km2=round(opt_only_km2, 6),
            sar_only_area_km2=round(sar_only_km2, 6),
            neither_area_km2=round(neither_km2, 6),
            joint_percent_of_aoi=joint_pct,
            optical_only_percent_of_aoi=opt_only_pct,
            sar_only_percent_of_aoi=sar_only_pct,
            neither_percent_of_aoi=neither_pct,
            pixel_counts=CoveragePartitionPixelCounts(
                total_aoi_pixels=total_aoi_px,
                jointly_observable_pixels=joint_px,
                optical_only_pixels=opt_only_px,
                sar_only_pixels=sar_only_px,
                neither_pixels=neither_px,
            ),
        )

        masks = {
            "joint": joint_mask,
            "optical_only": opt_only_mask,
            "sar_only": sar_only_mask,
            "neither": neither_mask,
            "aoi_domain": aoi_domain,
        }
        return partitions, masks

    @classmethod
    def classify_joint_observations(
        cls,
        optical_diff: np.ndarray[Any, Any],
        sar_delta_db: np.ndarray[Any, Any],
        joint_mask: np.ndarray[Any, Any],
        optical_pos_threshold: float,
        optical_neg_threshold: float,
        sar_increase_threshold_db: float,
        sar_decrease_threshold_db: float,
        pixel_size_x: float,
        pixel_size_y: float,
        uncertainty_mask: np.ndarray[Any, Any] | None = None,
    ) -> tuple[JointStateMetrics, np.ndarray[Any, Any]]:
        """Classify each pixel in J into one of 5 mutually exclusive observation states.

        Returns:
            (joint_metrics, state_classification_grid)
        """
        height, width = optical_diff.shape
        # 0: outside J, 1: both, 2: opt_only, 3: sar_only, 4: neither, 5: uncertain
        state_grid = np.zeros((height, width), dtype=np.uint8)

        # Segment changes
        opt_changed = (optical_diff >= optical_pos_threshold) | (
            optical_diff <= optical_neg_threshold
        )
        sar_changed = (sar_delta_db >= sar_increase_threshold_db) | (
            sar_delta_db <= sar_decrease_threshold_db
        )

        is_uncertain = np.zeros((height, width), dtype=bool)
        if uncertainty_mask is not None:
            is_uncertain = uncertainty_mask.astype(bool) & joint_mask

        # Assign states within J (uncertainty takes precedence if flagged)
        both_mask = joint_mask & opt_changed & sar_changed & (~is_uncertain)
        opt_only_resp_mask = joint_mask & opt_changed & (~sar_changed) & (~is_uncertain)
        sar_only_resp_mask = joint_mask & sar_changed & (~opt_changed) & (~is_uncertain)
        neither_mask = joint_mask & (~opt_changed) & (~sar_changed) & (~is_uncertain)
        uncertain_mask_final = joint_mask & is_uncertain

        state_grid[both_mask] = 1
        state_grid[opt_only_resp_mask] = 2
        state_grid[sar_only_resp_mask] = 3
        state_grid[neither_mask] = 4
        state_grid[uncertain_mask_final] = 5

        # Pixel counts
        both_px = int(np.sum(both_mask))
        opt_resp_px = int(np.sum(opt_only_resp_mask))
        sar_resp_px = int(np.sum(sar_only_resp_mask))
        neither_resp_px = int(np.sum(neither_mask))
        uncertain_px = int(np.sum(uncertain_mask_final))
        total_joint_px = int(np.sum(joint_mask))

        pixel_area_m2 = abs(pixel_size_x * pixel_size_y)
        joint_km2 = (total_joint_px * pixel_area_m2) / 1_000_000.0
        both_km2 = (both_px * pixel_area_m2) / 1_000_000.0
        opt_resp_km2 = (opt_resp_px * pixel_area_m2) / 1_000_000.0
        sar_resp_km2 = (sar_resp_px * pixel_area_m2) / 1_000_000.0
        neither_resp_km2 = (neither_resp_px * pixel_area_m2) / 1_000_000.0
        uncertain_km2 = (uncertain_px * pixel_area_m2) / 1_000_000.0

        # Percentage strictly with joint_km2 as denominator
        both_pct: float | None
        opt_resp_pct: float | None
        sar_resp_pct: float | None
        neither_resp_pct: float | None
        uncertain_pct: float | None

        if total_joint_px > 0:
            both_pct = round((both_px / total_joint_px) * 100.0, 2)
            opt_resp_pct = round((opt_resp_px / total_joint_px) * 100.0, 2)
            sar_resp_pct = round((sar_resp_px / total_joint_px) * 100.0, 2)
            neither_resp_pct = round((neither_resp_px / total_joint_px) * 100.0, 2)
            uncertain_pct = round((uncertain_px / total_joint_px) * 100.0, 2)
        else:
            both_pct = opt_resp_pct = sar_resp_pct = neither_resp_pct = uncertain_pct = None

        metrics = JointStateMetrics(
            joint_area_km2=round(joint_km2, 6),
            both_detect_change_area_km2=round(both_km2, 6),
            optical_response_only_area_km2=round(opt_resp_km2, 6),
            sar_response_only_area_km2=round(sar_resp_km2, 6),
            neither_above_threshold_area_km2=round(neither_resp_km2, 6),
            uncertain_area_km2=round(uncertain_km2, 6),
            both_detect_change_percent=both_pct,
            optical_response_only_percent=opt_resp_pct,
            sar_response_only_percent=sar_resp_pct,
            neither_above_threshold_percent=neither_resp_pct,
            uncertain_percent=uncertain_pct,
            pixel_counts=JointStatePixelCounts(
                both_detect_change_pixels=both_px,
                optical_response_only_pixels=opt_resp_px,
                sar_response_only_pixels=sar_resp_px,
                neither_above_threshold_pixels=neither_resp_px,
                uncertain_pixels=uncertain_px,
            ),
        )

        return metrics, state_grid

    @classmethod
    def vectorize_fusion_regions(
        cls,
        state_grid: np.ndarray[Any, Any],
        optical_diff: np.ndarray[Any, Any],
        sar_delta_db: np.ndarray[Any, Any],
        transform: list[float] | Affine,
        pixel_size_x: float,
        pixel_size_y: float,
        min_cluster_size_pixels: int = 5,
        simplify_tolerance_meters: float = 5.0,
        max_regions: int = 100,
    ) -> list[FusionRegion]:
        """Convert clustered joint state pixels into vectorized GeoJSON regions."""
        if isinstance(transform, list | tuple):
            aff = Affine(*transform[:6])
        else:
            aff = transform

        regions: list[FusionRegion] = []
        state_map = {
            1: JointObservationState.BOTH_DETECT_CHANGE,
            2: JointObservationState.OPTICAL_RESPONSE_ONLY,
            3: JointObservationState.SAR_RESPONSE_ONLY,
            5: JointObservationState.UNCERTAIN,
        }

        pixel_area_m2 = abs(pixel_size_x * pixel_size_y)

        for val, state_enum in state_map.items():
            mask = (state_grid == val).astype(np.uint8)
            if np.sum(mask) == 0:
                continue

            for geom_dict, shape_val in shapes(mask, mask=(mask != 0), transform=aff):
                if int(shape_val) != 1:
                    continue

                coords = geom_dict.get("coordinates", [])
                if not coords or len(coords[0]) < 4:
                    continue

                pts = coords[0]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)

                # Estimate pixel count inside bbox slice
                col_min = max(0, int((min_x - aff.c) / aff.a)) if aff.a != 0 else 0
                col_max = (
                    min(state_grid.shape[1], int((max_x - aff.c) / aff.a) + 1)
                    if aff.a != 0
                    else state_grid.shape[1]
                )
                row_min = max(0, int((max_y - aff.f) / aff.e)) if aff.e != 0 else 0
                row_max = (
                    min(state_grid.shape[0], int((min_y - aff.f) / aff.e) + 1)
                    if aff.e != 0
                    else state_grid.shape[0]
                )

                sub_mask = mask[row_min:row_max, col_min:col_max] == 1
                approx_px = int(np.sum(sub_mask))

                if approx_px < min_cluster_size_pixels:
                    continue

                reg_id = f"fusion-reg-{uuid4().hex[:8]}"

                if state_enum == JointObservationState.BOTH_DETECT_CHANGE:
                    explanation = (
                        "Co-observed response change detected by both optical index differencing "
                        "and calibrated SAR backscatter differencing within spatial-temporal tolerance."
                    )
                    confidence = 0.85
                elif state_enum == JointObservationState.OPTICAL_RESPONSE_ONLY:
                    explanation = (
                        "Optical sensor detected a spectral change while SAR backscatter delta remained "
                        "below the threshold."
                    )
                    confidence = 0.75
                elif state_enum == JointObservationState.SAR_RESPONSE_ONLY:
                    explanation = (
                        "SAR backscatter delta exceeded threshold while optical spectral index remained "
                        "below the threshold."
                    )
                    confidence = 0.75
                else:
                    explanation = (
                        "Observation state is uncertain due to quality or noise filtering."
                    )
                    confidence = 0.40

                area_km2 = round((approx_px * pixel_area_m2) / 1_000_000.0, 6)

                regions.append(
                    FusionRegion(
                        id=reg_id,
                        state=state_enum,
                        geometry=AOIGeometry(
                            type=GeometryType.POLYGON,
                            coordinates=coords,
                        ),
                        area_km2=area_km2,
                        pixel_count=approx_px,
                        mean_optical_difference=None,
                        mean_sar_difference_db=None,
                        optical_evidence_id=None,
                        sar_evidence_id=None,
                        rule_explanation=explanation,
                        confidence=confidence,
                        warnings=[],
                    )
                )

                if len(regions) >= max_regions:
                    break
            if len(regions) >= max_regions:
                break

        # Sort by area descending
        regions.sort(key=lambda r: r.area_km2, reverse=True)
        return regions[:max_regions]

    @classmethod
    def render_fusion_classified_png(
        cls,
        state_grid: np.ndarray[Any, Any],
    ) -> bytes:
        """Render discrete 5-state joint classification into a 4-channel RGBA preview PNG."""
        height, width = state_grid.shape
        rgba = np.zeros((4, height, width), dtype=np.uint8)

        for state_val, state_enum in [
            (1, JointObservationState.BOTH_DETECT_CHANGE),
            (2, JointObservationState.OPTICAL_RESPONSE_ONLY),
            (3, JointObservationState.SAR_RESPONSE_ONLY),
            (4, JointObservationState.NEITHER_ABOVE_THRESHOLD),
            (5, JointObservationState.UNCERTAIN),
        ]:
            mask = state_grid == state_val
            color = FUSION_STATE_RGBA[state_enum]
            rgba[0, mask] = color[0]
            rgba[1, mask] = color[1]
            rgba[2, mask] = color[2]
            rgba[3, mask] = color[3]

        return render(rgba, img_format="PNG")

    @classmethod
    def compute_quality_breakdown(
        cls,
        timing: MultimodalTimingMetrics,
        temporal_tolerance_days: float,
        optical_res_m: float,
        sar_res_m: float,
        sar_calibration: SARCalibrationStatus,
        coverage: CoveragePartitions,
    ) -> FusionQualityBreakdown:
        """Compute traceable scientific quality factors for multimodal fusion (0.0 to 1.0)."""
        limitations: list[str] = []

        # 1. Temporal alignment factor
        max_offset = max(timing.before_offset_days, timing.after_offset_days)
        if max_offset <= 1.0:
            temporal_factor = 1.0
        elif max_offset <= temporal_tolerance_days:
            temporal_factor = max(0.4, 1.0 - (max_offset / (temporal_tolerance_days * 1.5)))
        else:
            temporal_factor = 0.2
            limitations.append(
                f"High temporal acquisition offset ({max_offset:.1f} days) between sensors."
            )

        # 2. Spatial resolution factor
        res_ratio = min(optical_res_m, sar_res_m) / max(optical_res_m, sar_res_m)
        spatial_factor = max(0.5, round(res_ratio, 2))
        if res_ratio < 0.5:
            limitations.append(
                f"Resolution disparity between optical ({optical_res_m:.1f}m) and SAR ({sar_res_m:.1f}m)."
            )

        # 3. Calibration certainty factor
        if sar_calibration == SARCalibrationStatus.TERRAIN_CORRECTED:
            calibration_factor = 1.0
        elif sar_calibration == SARCalibrationStatus.CALIBRATED_ONLY:
            calibration_factor = 0.7
            limitations.append(
                "SAR backscatter is radiometrically calibrated but not terrain-corrected."
            )
        else:
            calibration_factor = 0.3
            limitations.append(
                "SAR backscatter is uncalibrated or geometric accuracy is unverified."
            )

        # 4. Valid coverage factor
        valid_cov_factor = (
            min(1.0, coverage.joint_percent_of_aoi / 100.0)
            if coverage.total_aoi_area_km2 > 0
            else 0.0
        )
        if valid_cov_factor < 0.5:
            limitations.append("Less than 50% of the AOI has valid joint observations.")

        score = round(
            temporal_factor * 0.35
            + spatial_factor * 0.20
            + calibration_factor * 0.25
            + valid_cov_factor * 0.20,
            3,
        )

        return FusionQualityBreakdown(
            score=min(1.0, max(0.0, score)),
            temporal_alignment_factor=round(temporal_factor, 3),
            spatial_resolution_factor=round(spatial_factor, 3),
            calibration_certainty_factor=round(calibration_factor, 3),
            valid_coverage_factor=round(valid_cov_factor, 3),
            factors={
                "temporal_alignment": round(temporal_factor, 3),
                "spatial_resolution": round(spatial_factor, 3),
                "calibration_certainty": round(calibration_factor, 3),
                "valid_coverage": round(valid_cov_factor, 3),
            },
            limitations=limitations,
        )
