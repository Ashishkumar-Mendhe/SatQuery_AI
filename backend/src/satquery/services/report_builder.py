"""Builder service to assemble immutable, traceable ReportSnapshot instances."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    AOIGeometry,
    ConfidenceBreakdown,
    DateRange,
    SatelliteScene,
    SpectralMeasurement,
)
from satquery.api.schemas.change import ChangeDetectionResult, ChangeMetrics
from satquery.api.schemas.fusion import FusionResult
from satquery.api.schemas.providers import DataOrigin
from satquery.api.schemas.query import AnswerClaim, QueryAnswer
from satquery.api.schemas.reports import (
    REPORT_SCHEMA_VERSION,
    ReportFigure,
    ReportFigureType,
    ReportSnapshot,
)
from satquery.api.schemas.spectral import SpectralIndexResult
from satquery.api.schemas.visual import VisualObservation, VisualQueryResponse
from satquery.services.asset_store import AssetStore

logger = logging.getLogger(__name__)


class ReportSnapshotBuilder:
    """Constructs immutable, server-resolved ReportSnapshot instances from analysis results."""

    def __init__(self, asset_store: AssetStore | None = None) -> None:
        self.asset_store = asset_store

    def build_snapshot(
        self,
        *,
        report_id: str | None = None,
        title: str | None = None,
        aoi: AOIGeometry,
        query: str | None = None,
        analysis_mode: str | None = None,
        date_range: DateRange | None = None,
        scenes: list[SatelliteScene] | None = None,
        query_answer: QueryAnswer | None = None,
        visual_response: VisualQueryResponse | None = None,
        change_result: ChangeDetectionResult | None = None,
        spectral_result: SpectralIndexResult | None = None,
        fusion_result: FusionResult | None = None,
        data_origin: DataOrigin | None = None,
        custom_provenance: dict[str, Any] | None = None,
        analysis_timestamp: datetime | None = None,
    ) -> ReportSnapshot:
        """Assemble an immutable ReportSnapshot and compute its cryptographic SHA-256 fingerprint."""
        now = datetime.now(UTC)
        final_report_id = report_id or f"rep-{uuid4().hex[:12]}"
        final_analysis_timestamp = analysis_timestamp or now

        # Determine title
        sanitized_title = (title or "SatQuery Geospatial Analysis Dossier").strip()
        if not sanitized_title:
            sanitized_title = "SatQuery Geospatial Analysis Dossier"

        # Determine data origin and flags
        origin = data_origin or DataOrigin.REAL
        is_mock = origin == DataOrigin.MOCK
        is_fallback = origin == DataOrigin.FALLBACK
        is_cached = origin == DataOrigin.CACHED

        if query_answer and query_answer.data_origin == DataOrigin.MOCK:
            is_mock = True
            origin = DataOrigin.MOCK
        if visual_response and visual_response.data_origin == DataOrigin.MOCK:
            is_mock = True
            origin = DataOrigin.MOCK
        if change_result and change_result.data_origin == DataOrigin.MOCK:
            is_mock = True
            origin = DataOrigin.MOCK

        # Extract answer text and claims
        answer_text: str | None = None
        claims: list[AnswerClaim] = []
        observations: list[VisualObservation] = []
        warnings: list[AnalysisWarning] = []
        limitations: list[str] = []

        if query_answer:
            answer_text = query_answer.summary
            claims.extend(query_answer.claims)
            warnings.extend(query_answer.warnings)
            limitations.extend(query_answer.limitations)

        if visual_response:
            if answer_text:
                answer_text = f"{answer_text}\n\nVisual Inspection:\n{visual_response.answer}"
            else:
                answer_text = visual_response.answer
            observations.extend(visual_response.observations)
            limitations.extend(visual_response.limitations)

        # Extract scenes
        resolved_scenes: list[SatelliteScene] = list(scenes or [])

        # Extract quantitative metrics
        quantitative_summary: dict[str, Any] = {}
        spectral_metrics: list[SpectralMeasurement] = []
        change_metrics: ChangeMetrics | None = None
        confidence_breakdown: ConfidenceBreakdown | None = None

        aoi_total_area_km2 = float(aoi.area_km2) if aoi.area_km2 is not None else 0.0
        quantitative_summary["aoi_total_area_km2"] = round(aoi_total_area_km2, 4)

        if change_result:
            change_metrics = change_result.metrics
            confidence_breakdown = change_result.confidence_breakdown
            warnings.extend(change_result.warnings)

            shared_valid_km2 = float(change_metrics.shared_valid_area_km2)
            gain_km2 = float(change_metrics.gain_area_km2)
            loss_km2 = float(change_metrics.loss_area_km2)
            stable_km2 = float(change_metrics.stable_area_km2)
            uncertain_km2 = (
                max(0.0, shared_valid_km2 - (gain_km2 + loss_km2 + stable_km2))
                if hasattr(change_metrics.pixel_counts, "uncertain_pixels")
                else 0.0
            )
            excluded_km2 = max(0.0, aoi_total_area_km2 - shared_valid_km2)

            coverage_pct = (
                round((shared_valid_km2 / aoi_total_area_km2) * 100.0, 2)
                if aoi_total_area_km2 > 0
                else 0.0
            )

            gain_pct = (
                round((gain_km2 / shared_valid_km2) * 100.0, 2) if shared_valid_km2 > 0 else 0.0
            )
            loss_pct = (
                round((loss_km2 / shared_valid_km2) * 100.0, 2) if shared_valid_km2 > 0 else 0.0
            )
            stable_pct = (
                round((stable_km2 / shared_valid_km2) * 100.0, 2) if shared_valid_km2 > 0 else 0.0
            )
            uncertain_pct = (
                round((uncertain_km2 / shared_valid_km2) * 100.0, 2)
                if shared_valid_km2 > 0
                else 0.0
            )
            excluded_pct = (
                round((excluded_km2 / aoi_total_area_km2) * 100.0, 2)
                if aoi_total_area_km2 > 0
                else 0.0
            )

            quantitative_summary["valid_comparison_area_km2"] = round(shared_valid_km2, 4)
            quantitative_summary["valid_comparison_coverage_percent"] = coverage_pct
            quantitative_summary["gain_area_km2"] = round(gain_km2, 4)
            quantitative_summary["gain_percent_of_valid_comparison"] = gain_pct
            quantitative_summary["loss_area_km2"] = round(loss_km2, 4)
            quantitative_summary["loss_percent_of_valid_comparison"] = loss_pct
            quantitative_summary["stable_area_km2"] = round(stable_km2, 4)
            quantitative_summary["stable_percent_of_valid_comparison"] = stable_pct
            quantitative_summary["uncertain_area_km2"] = round(uncertain_km2, 4)
            quantitative_summary["uncertain_percent_of_valid_comparison"] = uncertain_pct
            quantitative_summary["excluded_area_km2"] = round(excluded_km2, 4)
            quantitative_summary["excluded_percent_of_aoi"] = excluded_pct
            quantitative_summary["denominator_explanation"] = (
                f"Class percentages use denominator: shared valid comparison area "
                f"({shared_valid_km2:.2f} km²). Coverage percentage uses denominator: "
                f"total AOI area ({aoi_total_area_km2:.2f} km²). Excluded area is not classified as stable."
            )

        if spectral_result:
            warnings.extend(spectral_result.warnings)
            if hasattr(spectral_result, "statistics") and spectral_result.statistics:
                stats = spectral_result.statistics
                scene_id_val = (
                    spectral_result.source_asset_ids[0]
                    if spectral_result.source_asset_ids
                    else spectral_result.result_id
                )
                spectral_metrics.append(
                    SpectralMeasurement(
                        index_name=spectral_result.index_name.value,
                        value=stats.mean,
                        mean=stats.mean,
                        minimum=stats.minimum,
                        maximum=stats.maximum,
                        median=stats.median,
                        standard_deviation=stats.standard_deviation,
                        valid_pixel_count=stats.valid_pixel_count,
                        unit=stats.units,
                        scene_id=scene_id_val,
                        confidence=spectral_result.confidence,
                    )
                )

        if fusion_result:
            warnings.extend(fusion_result.warnings)
            if hasattr(fusion_result, "quality") and fusion_result.quality:
                limitations.extend(fusion_result.quality.limitations)
            if hasattr(fusion_result, "coverage") and fusion_result.coverage:
                quantitative_summary["fusion_joint_observable_area_km2"] = round(
                    fusion_result.coverage.jointly_observable_area_km2, 4
                )
                quantitative_summary["fusion_optical_only_area_km2"] = round(
                    fusion_result.coverage.optical_only_area_km2, 4
                )
                quantitative_summary["fusion_sar_only_area_km2"] = round(
                    fusion_result.coverage.sar_only_area_km2, 4
                )

        # Build figures
        figures = self._resolve_figures(
            change_result=change_result,
            spectral_result=spectral_result,
            visual_response=visual_response,
            origin=origin,
        )

        # Build provenance
        provenance: dict[str, Any] = {
            "pipeline_version": "1.0.0",
            "report_schema_version": REPORT_SCHEMA_VERSION,
            "generated_at": now.isoformat(),
            "analysis_timestamp": final_analysis_timestamp.isoformat(),
        }
        if custom_provenance:
            provenance.update(custom_provenance)

        # Construct snapshot model (without checksum initially)
        snapshot = ReportSnapshot(
            report_id=final_report_id,
            schema_version=REPORT_SCHEMA_VERSION,
            created_at=now,
            analysis_timestamp=final_analysis_timestamp,
            title=sanitized_title,
            query=query,
            analysis_mode=analysis_mode,
            aoi=aoi,
            date_range=date_range,
            data_origin=origin,
            is_mock_data=is_mock,
            is_fallback_data=is_fallback,
            is_cached_data=is_cached,
            scenes=resolved_scenes,
            answer=answer_text,
            claims=claims,
            observations=observations,
            quantitative_summary=quantitative_summary,
            spectral_metrics=spectral_metrics,
            change_metrics=change_metrics,
            confidence_breakdown=confidence_breakdown,
            warnings=warnings,
            limitations=limitations,
            figures=figures,
            provenance=provenance,
            checksum_sha256=None,
        )

        # Compute SHA-256 digest
        digest = self.calculate_checksum(snapshot)
        return snapshot.model_copy(update={"checksum_sha256": digest})

    def calculate_checksum(self, snapshot: ReportSnapshot) -> str:
        """Compute deterministic SHA-256 hex digest of the snapshot content."""
        data_dict = snapshot.model_dump(mode="json", exclude={"checksum_sha256"})
        canonical_json = json.dumps(data_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def _resolve_figures(
        self,
        *,
        change_result: ChangeDetectionResult | None,
        spectral_result: SpectralIndexResult | None,
        visual_response: VisualQueryResponse | None,
        origin: DataOrigin,
    ) -> list[ReportFigure]:
        """Freeze and describe available figure assets for the snapshot."""
        figures: list[ReportFigure] = []

        if change_result:
            if change_result.preview_asset_id:
                figures.append(
                    ReportFigure(
                        figure_id=f"fig-chg-{change_result.result_id[:8]}",
                        figure_type=ReportFigureType.DIFFERENCE_COLORMAP,
                        title="Continuous Spectral Difference Colormap",
                        caption=(
                            f"Bi-temporal spectral differencing map ({change_result.method.value}). "
                            f"Positive delta indicates spectral increase, negative indicates decrease."
                        ),
                        asset_id=change_result.preview_asset_id,
                        data_origin=origin,
                        associated_evidence_ids=[e.id for e in change_result.evidence],
                        legend_items=[
                            {"label": "Gain / Increase", "color": "#10b981"},
                            {"label": "Stable / Minimal Change", "color": "#64748b"},
                            {"label": "Loss / Decrease", "color": "#ef4444"},
                        ],
                    )
                )
            if change_result.classified_preview_asset_id:
                figures.append(
                    ReportFigure(
                        figure_id=f"fig-cls-{change_result.result_id[:8]}",
                        figure_type=ReportFigureType.CLASSIFIED_MASK,
                        title="3-Class Change Segmentation Mask",
                        caption=(
                            f"Discrete threshold segmentation ({change_result.metrics.threshold_strategy.value}). "
                            f"Gain: {change_result.metrics.gain_area_km2:.2f} km², "
                            f"Loss: {change_result.metrics.loss_area_km2:.2f} km², "
                            f"Stable: {change_result.metrics.stable_area_km2:.2f} km²."
                        ),
                        asset_id=change_result.classified_preview_asset_id,
                        data_origin=origin,
                        associated_evidence_ids=[e.id for e in change_result.evidence],
                        legend_items=[
                            {"label": "Gain (> +threshold)", "color": "#10b981"},
                            {"label": "Stable", "color": "#94a3b8"},
                            {"label": "Loss (< -threshold)", "color": "#ef4444"},
                        ],
                    )
                )

        if visual_response:
            for _i, obs in enumerate(visual_response.observations):
                if obs.canonical_box:
                    figures.append(
                        ReportFigure(
                            figure_id=f"fig-vqa-{obs.observation_id}",
                            figure_type=ReportFigureType.OBSERVATION_CROP,
                            title=f"AI Visual Prediction: {obs.label}",
                            caption=(
                                f"Model prediction [{obs.coordinate_status}] with canonical box "
                                f"[{', '.join(f'{x:.2f}' for x in obs.canonical_box)}]. "
                                f"Grounding: {obs.map_grounding_status.value}. "
                                f"Disclaimer: AI model prediction, not ground truth."
                            ),
                            asset_id=None,
                            data_origin=origin,
                            associated_evidence_ids=obs.associated_evidence_ids,
                            legend_items=[{"label": "Predicted Bounding Box", "color": "#f59e0b"}],
                        )
                    )

        return figures
