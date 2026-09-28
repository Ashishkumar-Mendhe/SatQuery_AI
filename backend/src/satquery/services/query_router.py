"""Deterministic query router and intent classification engine."""

from __future__ import annotations

import re

from satquery.api.schemas.query import (
    QueryIntent,
    QueryPlan,
    WorkspaceContextSnapshot,
)


class QueryRouter:
    """Routes user questions to structured intents and execution plans."""

    def route(self, question: str, snapshot: WorkspaceContextSnapshot) -> QueryPlan:
        q_norm = question.strip().lower()

        # 1. Check for unsupported / out-of-domain questions
        unsupported_keywords = [
            "weather forecast",
            "car model",
            "license plate",
            "who won",
            "stock price",
            "bitcoin",
            "crypto",
            "temperature tomorrow",
            "facial recognition",
        ]
        if any(kw in q_norm for kw in unsupported_keywords):
            return QueryPlan(
                intent=QueryIntent.UNSUPPORTED,
                scope="out_of_domain",
                required_evidence=[],
                missing_inputs=[],
                approved_operations=[],
                routing_reason="Question pertains to domains outside satellite Earth observation and multimodal remote sensing.",
                context_fingerprint=snapshot.fingerprint,
            )

        # 2. Check for multimodal / optical+SAR comparison
        multimodal_patterns = [
            r"\b(optical\s+and\s+(sar|radar))\b",
            r"\b(radar\s+and\s+optical)\b",
            r"\b(both\s+sensors?)\b",
            r"\b(do\s+(they|optical\s+and\s+sar)\s+agree)\b",
            r"\b(sar\s+evidence|radar\s+evidence)\b",
            r"\b(multimodal|joint\s+observation|co-observed)\b",
        ]
        if any(re.search(pat, q_norm) for pat in multimodal_patterns):
            missing = []
            if not snapshot.active_fusion_result_id:
                missing.append("active_fusion_result")
            return QueryPlan(
                intent=QueryIntent.MULTIMODAL_SUMMARY,
                scope="multimodal_optical_sar",
                required_evidence=["multimodal_fusion", "optical_change", "sar_difference"],
                missing_inputs=missing,
                approved_operations=["summarize_multimodal_evidence"],
                routing_reason="User inquiry focuses on cross-sensor comparison between optical and SAR observations.",
                context_fingerprint=snapshot.fingerprint,
            )

        # 3. Check for quality / confidence / warnings questions
        quality_patterns = [
            r"\bwhy\s+is\s+confidence\s+(low|high|limited)\b",
            r"\b(explain\s+quality|confidence\s+score|what\s+are\s+the\s+warnings?|data\s+quality)\b",
            r"\b(limitations?|caveats?|uncertainty|quality\s+factors?)\b",
        ]
        if any(re.search(pat, q_norm) for pat in quality_patterns):
            return QueryPlan(
                intent=QueryIntent.EXPLAIN_QUALITY,
                scope="quality_and_uncertainty",
                required_evidence=["confidence_breakdown", "analysis_warnings"],
                missing_inputs=[],
                approved_operations=["explain_quality_factors"],
                routing_reason="User asks about confidence scores, uncertainty factors, or warning caveats.",
                context_fingerprint=snapshot.fingerprint,
            )

        # 4. Check for location / spatial grounding / region questions
        locate_patterns = [
            r"\b(where\s+did|where\s+is|show\s+(me\s+)?the\s+largest|locate|highlight|coordinates?\s+of)\b",
            r"\b(which\s+region|show\s+region|where\s+are\s+the\s+changes?)\b",
            r"\b(where\s+did\s+.*(decrease|increase|change))\b",
        ]
        if any(re.search(pat, q_norm) for pat in locate_patterns):
            required = ["detected_regions"]
            missing = []
            if (
                not snapshot.active_change_result_id
                and not snapshot.active_fusion_result_id
                and not snapshot.active_spectral_result_id
            ):
                missing.append("active_analysis_result")
            return QueryPlan(
                intent=QueryIntent.LOCATE_EVIDENCE,
                scope="spatial_regions",
                required_evidence=required,
                missing_inputs=missing,
                approved_operations=["extract_candidate_regions", "resolve_spatial_geometries"],
                routing_reason="User requests spatial localization or inspection of specific detected regions.",
                context_fingerprint=snapshot.fingerprint,
            )

        # 5. Check for change detection / temporal questions
        change_patterns = [
            r"\b(what\s+changed|how\s+much\s+changed|change\s+between|difference\s+between)\b",
            r"\b(vegetation\s+(decrease|increase|loss|gain))\b",
            r"\b(built-up\s+(increase|decrease)|construction|demolition)\b",
            r"\b(water\s+(increase|decrease|expansion|loss))\b",
            r"\b(valid\s+comparison\s+area|how\s+much\s+decreased|how\s+much\s+increased)\b",
            r"\b(temporal\s+change|bi-temporal|gain\s+or\s+loss)\b",
        ]
        if any(re.search(pat, q_norm) for pat in change_patterns):
            missing = []
            if not snapshot.active_change_result_id and not snapshot.active_fusion_result_id:
                missing.append("active_change_result")
            return QueryPlan(
                intent=QueryIntent.CHANGE_SUMMARY,
                scope="bi_temporal_change",
                required_evidence=["change_measurement", "change_metrics"],
                missing_inputs=missing,
                approved_operations=["summarize_change_metrics", "explain_change_classes"],
                routing_reason="User inquiry asks about bi-temporal difference, change magnitude, or area statistics.",
                context_fingerprint=snapshot.fingerprint,
            )

        # 6. Check for single-date spectral index questions
        spectral_patterns = [
            r"\b(ndvi|ndwi|ndbi|vegetation|water\s+bodies?|built-up|moisture|spectral)\b",
            r"\b(index\s+values?|mean\s+reflectance|spectral\s+response)\b",
        ]
        if any(re.search(pat, q_norm) for pat in spectral_patterns):
            missing = []
            if not snapshot.active_spectral_result_id and not snapshot.active_change_result_id:
                missing.append("active_spectral_result")
            return QueryPlan(
                intent=QueryIntent.SPECTRAL_SUMMARY,
                scope="spectral_indices",
                required_evidence=["spectral_measurement"],
                missing_inputs=missing,
                approved_operations=["summarize_spectral_indices"],
                routing_reason="User asks for spectral index measurements (e.g. NDVI, NDWI, NDBI).",
                context_fingerprint=snapshot.fingerprint,
            )

        # 7. Check for general evidence summary
        general_patterns = [
            r"\b(summarize|summary|overview|what\s+do\s+you\s+see|findings?|evidence\s+summary|tell\s+me\s+about\s+this\s+scene)\b",
            r"\b(what\s+is\s+in\s+this\s+area|describe\s+the\s+aoi)\b",
        ]
        if any(re.search(pat, q_norm) for pat in general_patterns):
            missing = []
            if (
                not snapshot.active_spectral_result_id
                and not snapshot.active_change_result_id
                and not snapshot.active_fusion_result_id
            ):
                missing.append("any_active_analysis_result")
            return QueryPlan(
                intent=QueryIntent.EVIDENCE_SUMMARY,
                scope="workspace_evidence_summary",
                required_evidence=["all_available_evidence"],
                missing_inputs=missing,
                approved_operations=["summarize_all_evidence"],
                routing_reason="User requests a general factual summary of all available workspace evidence.",
                context_fingerprint=snapshot.fingerprint,
            )

        # 8. Fallback to general evidence summary or clarification
        if len(q_norm.split()) <= 2:
            return QueryPlan(
                intent=QueryIntent.CLARIFICATION_REQUIRED,
                scope="clarification",
                required_evidence=[],
                missing_inputs=["specific_question"],
                approved_operations=[],
                routing_reason="The question is brief or ambiguous; clarification is required to determine the analysis intent.",
                context_fingerprint=snapshot.fingerprint,
            )

        return QueryPlan(
            intent=QueryIntent.EVIDENCE_SUMMARY,
            scope="general_inquiry",
            required_evidence=["all_available_evidence"],
            missing_inputs=[],
            approved_operations=["summarize_all_evidence"],
            routing_reason="Defaulting to evidence summary for general query.",
            context_fingerprint=snapshot.fingerprint,
        )
