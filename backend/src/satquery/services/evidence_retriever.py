"""Authorized evidence retriever and lineage deduplication service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    ConfidenceFactor,
    EvidenceItem,
    Finding,
)
from satquery.api.schemas.change import ChangeDetectionResult
from satquery.api.schemas.fusion import FusionResult
from satquery.api.schemas.query import QueryPlan, WorkspaceContextSnapshot
from satquery.api.schemas.spectral import SpectralIndexResult
from satquery.services.change_service import ChangeService
from satquery.services.fusion_service import FusionService
from satquery.services.spectral_service import SpectralService


@dataclass
class EvidenceBundle:
    """Consolidated and deduplicated evidence bundle for query answering."""

    selected_evidence: list[EvidenceItem] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    quality_factors: list[ConfidenceFactor] = field(default_factory=list)
    warnings: list[AnalysisWarning] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    measurements: dict[str, Any] = field(default_factory=dict)
    spatial_regions: list[dict[str, Any]] = field(default_factory=list)
    allowed_spatial_references: list[str] = field(default_factory=list)
    source_lineage: list[str] = field(default_factory=list)
    is_complete: bool = True
    overall_confidence: float = 0.85


class EvidenceRetriever:
    """Retrieves and normalizes authorized evidence from active analysis services."""

    def __init__(
        self,
        spectral_service: SpectralService | None = None,
        change_service: ChangeService | None = None,
        fusion_service: FusionService | None = None,
    ) -> None:
        self.spectral_service = spectral_service
        self.change_service = change_service
        self.fusion_service = fusion_service

    async def retrieve_for_snapshot(
        self,
        snapshot: WorkspaceContextSnapshot,
        *,
        override_change_result: ChangeDetectionResult | None = None,
        override_spectral_result: SpectralIndexResult | None = None,
        override_fusion_result: FusionResult | None = None,
    ) -> EvidenceBundle:
        """Retrieve evidence bundle directly for a workspace snapshot without requiring a plan."""
        return await self.retrieve(
            snapshot=snapshot,
            plan=None,
            override_change_result=override_change_result,
            override_spectral_result=override_spectral_result,
            override_fusion_result=override_fusion_result,
        )

    async def retrieve(
        self,
        snapshot: WorkspaceContextSnapshot,
        plan: QueryPlan | None = None,
        *,
        override_change_result: ChangeDetectionResult | None = None,
        override_spectral_result: SpectralIndexResult | None = None,
        override_fusion_result: FusionResult | None = None,
    ) -> EvidenceBundle:
        bundle = EvidenceBundle()
        seen_evidence_ids: set[str] = set()
        seen_lineages: set[str] = set()

        # 1. Retrieve Change Detection Evidence
        change_res = override_change_result
        if not change_res and snapshot.active_change_result_id and self.change_service:
            change_res = self.change_service.get_result(snapshot.active_change_result_id)

        if change_res:
            bundle.source_lineage.append(f"change_detection:{change_res.method}")
            bundle.measurements["change_detection"] = {
                "method": change_res.method,
                "before_scene_id": change_res.before_scene_id,
                "after_scene_id": change_res.after_scene_id,
                "metrics": change_res.metrics.model_dump(),
                "confidence": change_res.confidence,
            }
            bundle.overall_confidence = change_res.confidence

            # Include change regions as spatial references
            for chg_reg in change_res.regions:
                bundle.spatial_regions.append(
                    {
                        "id": chg_reg.id,
                        "state": getattr(
                            chg_reg, "category", getattr(chg_reg, "state", "detected_region")
                        ),
                        "area_km2": chg_reg.area_km2,
                        "pixel_count": chg_reg.pixel_count,
                        "confidence": chg_reg.confidence,
                        "geometry": chg_reg.geometry.model_dump()
                        if hasattr(chg_reg.geometry, "model_dump")
                        else chg_reg.geometry,
                    }
                )
                bundle.allowed_spatial_references.append(chg_reg.id)

            # Extract evidence items from change result
            for ev in change_res.evidence:
                if ev.id not in seen_evidence_ids:
                    seen_evidence_ids.add(ev.id)
                    bundle.selected_evidence.append(ev)

            # Append warnings and limitations
            bundle.warnings.extend(change_res.warnings)
            qual = getattr(change_res, "quality", getattr(change_res, "confidence_breakdown", None))
            if qual and hasattr(qual, "limitations") and qual.limitations:
                bundle.limitations.extend(qual.limitations)

            # Scientific Disclaimers for specific methods
            if change_res.method == "ndbi_difference":
                bundle.limitations.append(
                    "NDBI spectral change indicates built-up or bare surface reflectance variance; "
                    "it does not constitute ground-truth proof of new building construction."
                )
            elif change_res.method == "ndvi_difference":
                bundle.limitations.append(
                    "NDVI spectral decrease indicates vegetation canopy vigor or moisture loss; "
                    "it does not establish confirmed deforestation without field verification."
                )

        # 2. Retrieve Multimodal Fusion Evidence
        fusion_res = override_fusion_result
        if not fusion_res and snapshot.active_fusion_result_id and self.fusion_service:
            fusion_res = self.fusion_service.get_result(snapshot.active_fusion_result_id)

        if fusion_res:
            bundle.source_lineage.append(f"multimodal_fusion:{fusion_res.rule_id}")
            bundle.measurements["multimodal_fusion"] = {
                "rule_id": fusion_res.rule_id,
                "coverage": fusion_res.coverage.model_dump(),
                "joint_metrics": fusion_res.joint_metrics.model_dump(),
                "compatibility": fusion_res.compatibility.model_dump(),
                "confidence": fusion_res.quality.score,
            }

            for fus_reg in fusion_res.regions:
                bundle.spatial_regions.append(
                    {
                        "id": fus_reg.id,
                        "state": fus_reg.state,
                        "area_km2": fus_reg.area_km2,
                        "pixel_count": fus_reg.pixel_count,
                        "confidence": fus_reg.confidence,
                        "geometry": fus_reg.geometry.model_dump()
                        if hasattr(fus_reg.geometry, "model_dump")
                        else fus_reg.geometry,
                        "rule_explanation": fus_reg.rule_explanation,
                    }
                )
                bundle.allowed_spatial_references.append(fus_reg.id)

            for ev in fusion_res.evidence:
                if ev.id not in seen_evidence_ids:
                    seen_evidence_ids.add(ev.id)
                    bundle.selected_evidence.append(ev)

            bundle.warnings.extend(fusion_res.warnings)
            bundle.limitations.extend(fusion_res.quality.limitations)
            bundle.limitations.append(
                "Multimodal optical-SAR co-occurrence reflects concurrent sensor physical response changes; "
                "it does not establish verified ground-truth physical events."
            )

        # 3. Retrieve Spectral Index Evidence
        spectral_res = override_spectral_result
        if not spectral_res and snapshot.active_spectral_result_id and self.spectral_service:
            spectral_res = self.spectral_service.get_result(snapshot.active_spectral_result_id)

        if spectral_res:
            lineage_key = f"spectral:{spectral_res.scene_id}:{spectral_res.index_name}"
            if lineage_key not in seen_lineages:
                seen_lineages.add(lineage_key)
                bundle.source_lineage.append(lineage_key)
                bundle.measurements["spectral_indices"] = {
                    "scene_id": spectral_res.scene_id,
                    "index_name": str(spectral_res.index_name),
                    "statistics": spectral_res.statistics.model_dump(),
                    "confidence": spectral_res.confidence.overall,
                }
                for s_ev in spectral_res.evidence:
                    if s_ev.id not in seen_evidence_ids:
                        seen_evidence_ids.add(s_ev.id)
                        bundle.selected_evidence.append(s_ev)  # type: ignore[arg-type]
                bundle.warnings.extend(spectral_res.warnings)

        return bundle
