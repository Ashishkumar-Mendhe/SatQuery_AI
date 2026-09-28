"""Sufficiency checker and actionable workflow recommendation engine."""

from __future__ import annotations

from satquery.api.schemas.query import (
    QueryIntent,
    QueryPlan,
    SufficiencyStatus,
    SuggestedNextAction,
    WorkspaceContextSnapshot,
)
from satquery.services.evidence_retriever import EvidenceBundle


class SufficiencyChecker:
    """Evaluates whether retrieved evidence is sufficient to answer the user query."""

    def check(
        self,
        snapshot: WorkspaceContextSnapshot,
        plan: QueryPlan,
        bundle: EvidenceBundle,
    ) -> tuple[SufficiencyStatus, list[SuggestedNextAction]]:
        suggested_actions: list[SuggestedNextAction] = []

        if plan.intent == QueryIntent.UNSUPPORTED:
            return SufficiencyStatus.UNSUPPORTED, suggested_actions

        if plan.intent == QueryIntent.CLARIFICATION_REQUIRED:
            return SufficiencyStatus.CLARIFICATION_REQUIRED, suggested_actions

        # If user has no AOI
        if not snapshot.aoi_geometry:
            suggested_actions.append(
                SuggestedNextAction(
                    action_id="draw_aoi",
                    label="Draw Area of Interest",
                    description="Draw a rectangle or polygon on the map to define the spatial search extent.",
                    workflow_target="map_aoi",
                )
            )
            return SufficiencyStatus.INSUFFICIENT_EVIDENCE, suggested_actions

        # If user asks about change detection or temporal difference
        if plan.intent == QueryIntent.CHANGE_SUMMARY:
            if "change_detection" in bundle.measurements:
                return SufficiencyStatus.ANSWERABLE, suggested_actions
            if "multimodal_fusion" in bundle.measurements:
                return SufficiencyStatus.ANSWERABLE, suggested_actions

            # Check if scenes exist in workspace
            if len(snapshot.scene_ids) >= 2:
                suggested_actions.append(
                    SuggestedNextAction(
                        action_id="run_change_detection",
                        label="Run Pixel-Level Change Detection",
                        description=f"Calculate bi-temporal spectral change between scenes {snapshot.scene_ids[0]} and {snapshot.scene_ids[1]}.",
                        workflow_target="change_detection",
                        parameters={
                            "before_scene_id": snapshot.scene_ids[0],
                            "after_scene_id": snapshot.scene_ids[1],
                        },
                    )
                )
                return SufficiencyStatus.NEEDS_PROCESSING, suggested_actions

            suggested_actions.append(
                SuggestedNextAction(
                    action_id="search_temporal_scenes",
                    label="Search Temporal Scene Pair",
                    description="Search the satellite catalogue for Before and After acquisitions over the active AOI.",
                    workflow_target="imagery_search",
                )
            )
            return SufficiencyStatus.INSUFFICIENT_EVIDENCE, suggested_actions

        # If user asks about multimodal optical & SAR comparison
        if plan.intent == QueryIntent.MULTIMODAL_SUMMARY:
            if "multimodal_fusion" in bundle.measurements:
                return SufficiencyStatus.ANSWERABLE, suggested_actions

            if "change_detection" in bundle.measurements:
                suggested_actions.append(
                    SuggestedNextAction(
                        action_id="run_multimodal_fusion",
                        label="Execute Multimodal Optical/SAR Fusion",
                        description="Combine current optical change results with calibrated Sentinel-1 SAR backscatter delta.",
                        workflow_target="multimodal_fusion",
                        parameters={"optical_result_id": snapshot.active_change_result_id},
                    )
                )
                return SufficiencyStatus.NEEDS_PROCESSING, suggested_actions

            suggested_actions.append(
                SuggestedNextAction(
                    action_id="run_change_and_fusion",
                    label="Prepare Optical and SAR Pairs",
                    description="Process bi-temporal optical and SAR pairs to enable multimodal evidence fusion.",
                    workflow_target="multimodal_fusion",
                )
            )
            return SufficiencyStatus.INSUFFICIENT_EVIDENCE, suggested_actions

        # If user asks about locating specific evidence regions
        if plan.intent == QueryIntent.LOCATE_EVIDENCE:
            if bundle.spatial_regions:
                return SufficiencyStatus.ANSWERABLE, suggested_actions
            if (
                "change_detection" in bundle.measurements
                or "spectral_indices" in bundle.measurements
            ):
                return SufficiencyStatus.ANSWERABLE, suggested_actions

            return SufficiencyStatus.INSUFFICIENT_EVIDENCE, [
                SuggestedNextAction(
                    action_id="run_analysis_for_regions",
                    label="Run Analysis to Detect Regions",
                    description="Execute spectral or change detection analysis to extract vectorized candidate regions.",
                    workflow_target="change_detection",
                )
            ]

        # If user asks for spectral index measurements
        if plan.intent == QueryIntent.SPECTRAL_SUMMARY:
            if (
                "spectral_indices" in bundle.measurements
                or "change_detection" in bundle.measurements
            ):
                return SufficiencyStatus.ANSWERABLE, suggested_actions

            if snapshot.scene_ids:
                suggested_actions.append(
                    SuggestedNextAction(
                        action_id="calculate_spectral_indices",
                        label="Calculate Spectral Indices",
                        description=f"Compute NDVI, NDWI, and NDBI on scene {snapshot.scene_ids[0]}.",
                        workflow_target="spectral_analysis",
                        parameters={"scene_id": snapshot.scene_ids[0]},
                    )
                )
                return SufficiencyStatus.NEEDS_PROCESSING, suggested_actions

            return SufficiencyStatus.INSUFFICIENT_EVIDENCE, [
                SuggestedNextAction(
                    action_id="search_scenes",
                    label="Search Satellite Scenes",
                    description="Discover satellite imagery over the active AOI to compute spectral indices.",
                    workflow_target="imagery_search",
                )
            ]

        # General evidence summary or quality explanation
        if bundle.selected_evidence or bundle.measurements:
            return SufficiencyStatus.ANSWERABLE, suggested_actions

        return SufficiencyStatus.INSUFFICIENT_EVIDENCE, [
            SuggestedNextAction(
                action_id="search_scenes",
                label="Search Satellite Imagery",
                description="Search Sentinel-2 or Sentinel-1 imagery for the active AOI to begin analysis.",
                workflow_target="imagery_search",
            )
        ]
