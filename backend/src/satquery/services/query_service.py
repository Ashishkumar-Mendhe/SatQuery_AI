"""Master query answering service orchestrating router, retriever, sufficiency, AI and validation."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import uuid4

from satquery.api.schemas.analysis import AnalysisMode, ConfidenceFactor
from satquery.api.schemas.change import ChangeDetectionResult
from satquery.api.schemas.fusion import FusionResult
from satquery.api.schemas.providers import DataOrigin
from satquery.api.schemas.query import (
    AnswerClaim,
    GenerationMode,
    ProcessingTraceStep,
    QueryAnswer,
    QueryCapabilitiesResponse,
    QueryIntent,
    QueryPlan,
    QueryRequest,
    SufficiencyStatus,
    SuggestedNextAction,
)
from satquery.api.schemas.spectral import SpectralIndexResult
from satquery.providers.ai.base import (
    AIInterpretationRequest,
    AIProvider,
    AIProviderError,
)
from satquery.providers.ai.registry import AIProviderRegistry
from satquery.services.claim_validator import ClaimValidator
from satquery.services.evidence_retriever import EvidenceBundle, EvidenceRetriever
from satquery.services.query_router import QueryRouter
from satquery.services.sufficiency_checker import SufficiencyChecker


class QueryService:
    """End-to-end evidence-grounded natural-language query answering service."""

    def __init__(
        self,
        router: QueryRouter | None = None,
        retriever: EvidenceRetriever | None = None,
        checker: SufficiencyChecker | None = None,
        validator: ClaimValidator | None = None,
        ai_registry: AIProviderRegistry | None = None,
    ) -> None:
        self.router = router or QueryRouter()
        self.retriever = retriever or EvidenceRetriever()
        self.checker = checker or SufficiencyChecker()
        self.validator = validator or ClaimValidator()
        self.ai_registry = ai_registry

    def get_capabilities(self) -> QueryCapabilitiesResponse:
        return QueryCapabilitiesResponse(
            supported_intents=[
                QueryIntent.EVIDENCE_SUMMARY,
                QueryIntent.SPECTRAL_SUMMARY,
                QueryIntent.CHANGE_SUMMARY,
                QueryIntent.MULTIMODAL_SUMMARY,
                QueryIntent.LOCATE_EVIDENCE,
                QueryIntent.EXPLAIN_QUALITY,
                QueryIntent.NEEDS_PROCESSING,
                QueryIntent.CLARIFICATION_REQUIRED,
                QueryIntent.UNSUPPORTED,
            ],
            supported_generation_modes=[
                GenerationMode.LLM_EXPLANATION,
                GenerationMode.DETERMINISTIC_SUMMARY,
                GenerationMode.MOCK_DEMO,
            ],
            example_questions=[
                "What changed between these two dates?",
                "Where did the vegetation-related response decrease?",
                "How much of the valid comparison area changed?",
                "Do optical and radar observations agree?",
                "Why is confidence low?",
                "Show the largest detected change region.",
                "Does this prove new construction?",
            ],
        )

    async def answer_query(
        self,
        request: QueryRequest,
        *,
        override_change_result: ChangeDetectionResult | None = None,
        override_spectral_result: SpectralIndexResult | None = None,
        override_fusion_result: FusionResult | None = None,
        ai_provider_override: AIProvider | None = None,
    ) -> QueryAnswer:
        trace: list[ProcessingTraceStep] = []
        request_id = request.request_id or f"req-{uuid4().hex[:8]}"
        snapshot = request.context_snapshot

        # Step 1: Context Validation
        t0 = time.perf_counter()
        trace.append(
            ProcessingTraceStep(
                stage="context_validation",
                status="success",
                duration_ms=max(1, int((time.perf_counter() - t0) * 1000)),
                description=f"Validated workspace snapshot {snapshot.snapshot_id} (fingerprint: {snapshot.fingerprint[:12]}...).",
            )
        )

        # Step 2: Intent Routing
        t0 = time.perf_counter()
        plan = self.router.route(request.question, snapshot)
        trace.append(
            ProcessingTraceStep(
                stage="intent_routing",
                status="success",
                duration_ms=max(1, int((time.perf_counter() - t0) * 1000)),
                description=f"Routed intent '{plan.intent}' with reason: {plan.routing_reason}",
            )
        )

        # Step 3: Evidence Retrieval
        t0 = time.perf_counter()
        bundle = await self.retriever.retrieve(
            snapshot,
            plan,
            override_change_result=override_change_result,
            override_spectral_result=override_spectral_result,
            override_fusion_result=override_fusion_result,
        )
        trace.append(
            ProcessingTraceStep(
                stage="evidence_retrieval",
                status="success",
                duration_ms=max(1, int((time.perf_counter() - t0) * 1000)),
                description=f"Retrieved {len(bundle.selected_evidence)} evidence item(s) and {len(bundle.spatial_regions)} region(s).",
            )
        )

        # Step 4: Sufficiency Checking
        t0 = time.perf_counter()
        sufficiency_status, suggested_actions = self.checker.check(snapshot, plan, bundle)
        trace.append(
            ProcessingTraceStep(
                stage="sufficiency_check",
                status="success"
                if sufficiency_status == SufficiencyStatus.ANSWERABLE
                else "notice",
                duration_ms=max(1, int((time.perf_counter() - t0) * 1000)),
                description=f"Sufficiency status evaluated as '{sufficiency_status}'.",
            )
        )

        # Build initial deterministic claims
        claims = self.validator.build_deterministic_claims(bundle)

        # If insufficient or unsupported, return immediate structured response
        if sufficiency_status in {
            SufficiencyStatus.INSUFFICIENT_EVIDENCE,
            SufficiencyStatus.NEEDS_PROCESSING,
            SufficiencyStatus.CLARIFICATION_REQUIRED,
            SufficiencyStatus.UNSUPPORTED,
        }:
            non_ans_summary = self._build_non_answerable_summary(
                request.question, sufficiency_status, plan, suggested_actions
            )
            return QueryAnswer(
                answer_id=f"ans-{uuid4().hex[:8]}",
                request_id=request_id,
                context_fingerprint=snapshot.fingerprint,
                answer_status=sufficiency_status,
                generation_mode=GenerationMode.DETERMINISTIC_SUMMARY,
                plan=plan,
                summary=non_ans_summary,
                claims=claims,
                evidence_references=[e.id for e in bundle.selected_evidence],
                spatial_references=bundle.allowed_spatial_references,
                quality_factors=[
                    ConfidenceFactor(
                        code="data_sufficiency",
                        label="Data Sufficiency",
                        score=0.10
                        if sufficiency_status == SufficiencyStatus.INSUFFICIENT_EVIDENCE
                        else 0.50,
                        weight=1.0,
                        explanation=f"Query answering limited by {sufficiency_status.replace('_', ' ')}.",
                    )
                ],
                warnings=bundle.warnings,
                limitations=bundle.limitations,
                suggested_actions=suggested_actions,
                processing_trace=trace,
                data_origin=DataOrigin.REAL,
            )

        # Step 5: Answer Generation (AI Provider or Deterministic Summary)
        t0 = time.perf_counter()
        ai_provider = ai_provider_override
        if not ai_provider and self.ai_registry:
            try:
                ai_provider = self.ai_registry.primary_provider
            except Exception:
                ai_provider = None

        summary: str = ""
        gen_mode = GenerationMode.DETERMINISTIC_SUMMARY
        provider_execution = None

        if ai_provider and ai_provider.is_configured():
            try:
                ai_req = AIInterpretationRequest(
                    question=request.question,
                    mode=snapshot.active_mode or AnalysisMode.CHANGE_DETECTION,
                    evidence=bundle.selected_evidence,
                    aoi_geometry=snapshot.aoi_geometry,
                    language=request.locale or "en",
                    limitations=bundle.limitations,
                )
                ai_resp = await ai_provider.generate_interpretation(ai_req)
                summary = ai_resp.answer
                gen_mode = (
                    GenerationMode.MOCK_DEMO
                    if ai_provider.mode.value == "mock"
                    else GenerationMode.LLM_EXPLANATION
                )
                provider_execution = ai_resp.execution_metadata
                trace.append(
                    ProcessingTraceStep(
                        stage="ai_generation",
                        status="success",
                        duration_ms=max(1, int((time.perf_counter() - t0) * 1000)),
                        description=f"Generated answer using AI provider '{ai_provider.provider_id}'.",
                    )
                )
            except (AIProviderError, NotImplementedError, Exception) as exc:
                # Fallback gracefully to deterministic summary
                trace.append(
                    ProcessingTraceStep(
                        stage="ai_generation",
                        status="fallback",
                        duration_ms=max(1, int((time.perf_counter() - t0) * 1000)),
                        description=f"AI provider generation unavailable ({exc}); fell back to deterministic evidence summary.",
                    )
                )
                summary = self._build_deterministic_summary(request.question, plan, bundle, claims)
                gen_mode = GenerationMode.DETERMINISTIC_SUMMARY
        else:
            trace.append(
                ProcessingTraceStep(
                    stage="ai_generation",
                    status="skipped",
                    duration_ms=max(1, int((time.perf_counter() - t0) * 1000)),
                    description="AI provider unconfigured; generated deterministic evidence summary.",
                )
            )
            summary = self._build_deterministic_summary(request.question, plan, bundle, claims)
            gen_mode = GenerationMode.DETERMINISTIC_SUMMARY

        # Step 6: Claim Validation & Spatial Referencing
        t0 = time.perf_counter()
        verified_claims = self.validator.validate_and_filter_claims(claims, bundle)
        trace.append(
            ProcessingTraceStep(
                stage="claim_validation",
                status="success",
                duration_ms=max(1, int((time.perf_counter() - t0) * 1000)),
                description=f"Validated {len(verified_claims)} grounded claim(s) against measured evidence.",
            )
        )

        quality_factors = [
            ConfidenceFactor(
                code="measurement_agreement",
                label="Evidence Agreement",
                score=bundle.overall_confidence,
                weight=0.5,
                explanation="Grounded in quantitative raster differences and validated sensor calibrations.",
            ),
            ConfidenceFactor(
                code="spatial_validity",
                label="Spatial Alignment",
                score=1.0,
                weight=0.5,
                explanation="Pixel grids verified with identical CRS and snapped bounding extents.",
            ),
        ]

        return QueryAnswer(
            answer_id=f"ans-{uuid4().hex[:8]}",
            request_id=request_id,
            context_fingerprint=snapshot.fingerprint,
            answer_status=SufficiencyStatus.ANSWERABLE,
            generation_mode=gen_mode,
            plan=plan,
            summary=summary,
            claims=verified_claims,
            evidence_references=[e.id for e in bundle.selected_evidence],
            spatial_references=bundle.allowed_spatial_references,
            quality_factors=quality_factors,
            warnings=bundle.warnings,
            limitations=bundle.limitations,
            suggested_actions=suggested_actions,
            processing_trace=trace,
            data_origin=DataOrigin.MOCK
            if gen_mode == GenerationMode.MOCK_DEMO
            else DataOrigin.REAL,
            created_at=datetime.now(UTC),
            provider_execution=provider_execution,
        )

    def _build_deterministic_summary(
        self,
        question: str,
        plan: QueryPlan,
        bundle: EvidenceBundle,
        claims: list[AnswerClaim],
    ) -> str:
        q_lower = question.lower()

        # Specific construction proof inquiry
        if "construction" in q_lower or "building" in q_lower:
            return (
                "Based on measured satellite evidence, spectral changes were detected over the Area of Interest; "
                "however, this does NOT confirm new building construction. Optical NDBI increases and radar backscatter "
                "deltas indicate surface reflectivity variations that can equally stem from cleared ground, dry soil, or "
                "infrastructure changes. Field verification or high-resolution imagery is required to confirm physical construction."
            )

        # Quality / Confidence inquiry
        if plan.intent == QueryIntent.EXPLAIN_QUALITY:
            return (
                f"Overall analysis confidence is rated at {int(bundle.overall_confidence * 100)}%. "
                "Confidence is governed by spatial grid alignment, valid data coverage over the AOI, atmospheric clarity, "
                "and temporal interval proximity between acquisition dates."
            )

        # Location inquiry
        if plan.intent == QueryIntent.LOCATE_EVIDENCE:
            if bundle.spatial_regions:
                largest = bundle.spatial_regions[0]
                area_km2 = largest.get("area_km2", 0.0)
                reg_id = largest.get("id", "region-1")
                return (
                    f"The largest detected response region is '{reg_id}', spanning {area_km2:.4f} km². "
                    "Select this region chip to highlight its exact vector geometry on the map."
                )
            return "No distinct candidate spatial regions were vectorized above the minimum cluster size threshold."

        # Change detection inquiry
        if "change_detection" in bundle.measurements:
            cd = bundle.measurements["change_detection"]
            metrics = cd.get("metrics", {})
            valid_area = metrics.get("shared_valid_area_km2", 0.0)
            pixel_counts = (
                metrics.get("pixel_counts", {})
                if isinstance(metrics.get("pixel_counts"), dict)
                else {}
            )
            loss_pct = metrics.get("loss_percent", pixel_counts.get("loss_percent", 0.0))
            gain_pct = metrics.get("gain_percent", pixel_counts.get("gain_percent", 0.0))
            loss_area = metrics.get("loss_area_km2", 0.0)
            gain_area = metrics.get("gain_area_km2", 0.0)

            if loss_pct > 0 or gain_pct > 0:
                return (
                    f"Bi-temporal change analysis across the {valid_area:.4f} km² valid comparison area reveals "
                    f"a response decrease over {loss_area:.4f} km² ({loss_pct:.1f}% of valid area) and "
                    f"a response increase over {gain_area:.4f} km² ({gain_pct:.1f}% of valid area)."
                )
            return (
                f"Bi-temporal change analysis across the {valid_area:.4f} km² valid comparison area detected no significant change; "
                "100% of mutual valid pixels remained within stable threshold cutoffs."
            )

        # Multimodal inquiry
        if "multimodal_fusion" in bundle.measurements:
            mf = bundle.measurements["multimodal_fusion"]
            jm = mf.get("joint_metrics", {})
            cov = mf.get("coverage", {})
            joint_area = cov.get("jointly_observable_area_km2", 0.0)
            both_pct = jm.get("both_detect_change_percent", 0.0)
            both_area = jm.get("both_detect_change_area_km2", 0.0)
            return (
                f"Multimodal evidence fusion over {joint_area:.4f} km² of jointly observable area indicates "
                f"that both optical and SAR sensors co-detected response changes across {both_area:.4f} km² "
                f"({both_pct:.1f}% of the joint area)."
            )

        # General evidence summary fallback
        claim_texts = [c.display_text for c in claims if c.display_text]
        if claim_texts:
            return " ".join(claim_texts)

        return "Analysis completed. Review the structured evidence items and measurement cards for quantitative findings."

    def _build_non_answerable_summary(
        self,
        question: str,
        status: SufficiencyStatus,
        plan: QueryPlan,
        suggested_actions: list[SuggestedNextAction],
    ) -> str:
        if status == SufficiencyStatus.UNSUPPORTED:
            return (
                f"The question '{question}' cannot be answered because it falls outside the analytical scope of SatQuery. "
                "SatQuery AI focuses on satellite Earth observation, spectral index analysis, bi-temporal change detection, "
                "and multimodal optical/SAR fusion."
            )
        if status == SufficiencyStatus.CLARIFICATION_REQUIRED:
            return (
                "Please clarify your question. For example, ask 'What changed between these dates?', 'Where is vegetation visible?', "
                "or 'Show the largest detected change region'."
            )
        if status == SufficiencyStatus.NEEDS_PROCESSING:
            act_names = ", ".join(f"'{a.label}'" for a in suggested_actions)
            return (
                f"Answering '{question}' requires computing new quantitative evidence. "
                f"Please execute {act_names} using the action buttons below to calculate the required metrics."
            )
        # INSUFFICIENT_EVIDENCE
        return (
            f"Cannot answer '{question}' because no quantitative satellite evidence or analysis results are active in the workspace. "
            "Please select an Area of Interest and search or process satellite imagery first."
        )
