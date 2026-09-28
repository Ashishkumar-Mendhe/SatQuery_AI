"""Pydantic schemas and enums for Phase 5A Query Routing and Evidence-Grounded AI Answers."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from satquery.api.schemas.analysis import (
    AnalysisMode,
    AnalysisWarning,
    AOIGeometry,
    ConfidenceFactor,
)
from satquery.api.schemas.providers import DataOrigin, ProviderExecutionMetadata


class StrictQueryModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class QueryIntent(StrEnum):
    """Categorized intent of a user's natural language question."""

    EVIDENCE_SUMMARY = "evidence_summary"
    SPECTRAL_SUMMARY = "spectral_summary"
    CHANGE_SUMMARY = "change_summary"
    MULTIMODAL_SUMMARY = "multimodal_summary"
    LOCATE_EVIDENCE = "locate_evidence"
    EXPLAIN_QUALITY = "explain_quality"
    NEEDS_PROCESSING = "needs_processing"
    CLARIFICATION_REQUIRED = "clarification_required"
    UNSUPPORTED = "unsupported"


class SufficiencyStatus(StrEnum):
    """Evaluation of evidence sufficiency for answering the query."""

    ANSWERABLE = "answerable"
    PARTIALLY_ANSWERABLE = "partially_answerable"
    CLARIFICATION_REQUIRED = "clarification_required"
    NEEDS_PROCESSING = "needs_processing"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNSUPPORTED = "unsupported"


class GenerationMode(StrEnum):
    """Mode used to synthesize the natural language answer."""

    LLM_EXPLANATION = "llm_explanation"
    DETERMINISTIC_SUMMARY = "deterministic_summary"
    MOCK_DEMO = "mock_demo"


class ClaimKind(StrEnum):
    """Epistemic classification of a single statement or claim in the answer."""

    MEASUREMENT = "measurement"
    INTERPRETATION = "interpretation"
    BACKGROUND = "background"
    LIMITATION = "limitation"


class ClaimValidationStatus(StrEnum):
    """Server-side verification status of a proposed claim."""

    VALID = "valid"
    UNVERIFIED = "unverified"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Context Snapshot & Plan Models
# ---------------------------------------------------------------------------


class WorkspaceContextSnapshot(StrictQueryModel):
    """Server-side or client-provided snapshot of the active workspace state."""

    snapshot_id: str = Field(description="Unique snapshot identifier")
    fingerprint: str = Field(description="Deterministic hash of the active context parameters")
    aoi_geometry: AOIGeometry | None = Field(default=None, description="Current AOI geometry")
    aoi_id: str | None = Field(default=None, description="Current AOI identifier if saved")
    location_label: str | None = Field(default=None, description="Human-readable location label")
    scene_ids: list[str] = Field(default_factory=list, description="Currently selected scene IDs")
    active_mode: AnalysisMode | None = Field(
        default=None, description="Active analysis mode in the workspace"
    )
    active_spectral_result_id: str | None = Field(
        default=None, description="ID of active spectral index result"
    )
    active_change_result_id: str | None = Field(
        default=None, description="ID of active change detection result"
    )
    active_fusion_result_id: str | None = Field(
        default=None, description="ID of active multimodal fusion result"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Snapshot capture timestamp",
    )


class QueryPlan(StrictQueryModel):
    """Deterministic routing plan derived for the user query."""

    intent: QueryIntent = Field(description="Classified query intent")
    scope: str = Field(description="Evaluated spatial/temporal scope of the question")
    required_evidence: list[str] = Field(
        default_factory=list, description="Required evidence types or methods"
    )
    missing_inputs: list[str] = Field(
        default_factory=list, description="List of missing inputs needed to answer fully"
    )
    approved_operations: list[str] = Field(
        default_factory=list, description="Allowed service operations to fulfill query"
    )
    routing_reason: str = Field(description="Explanation of why this intent and plan were chosen")
    context_fingerprint: str = Field(description="Matching context snapshot fingerprint")


# ---------------------------------------------------------------------------
# Answer Components & Actions
# ---------------------------------------------------------------------------


class AnswerClaim(StrictQueryModel):
    """Structured, verifiable claim grounded in specific evidence."""

    claim_id: str = Field(description="Unique claim identifier")
    kind: ClaimKind = Field(description="Kind of claim (measurement, interpretation, etc.)")
    evidence_ids: list[str] = Field(
        default_factory=list, description="IDs of backing evidence items"
    )
    metric_references: list[str] = Field(
        default_factory=list, description="Referenced metric fields or facts"
    )
    resolved_measurement: dict[str, Any] | None = Field(
        default=None, description="Server-resolved numeric measurements, units, and denominators"
    )
    region_ids: list[str] = Field(default_factory=list, description="Referenced spatial region IDs")
    display_text: str = Field(description="Formatted human-readable claim sentence")
    validation_status: ClaimValidationStatus = Field(
        default=ClaimValidationStatus.VALID,
        description="Server verification status",
    )


class SuggestedNextAction(StrictQueryModel):
    """Typed actionable next step to resolve missing data or execute next analysis."""

    action_id: str = Field(description="Unique action identifier")
    label: str = Field(description="Button or action label")
    description: str = Field(description="Explanation of what this action will perform")
    workflow_target: str = Field(
        description="Target workspace workflow (e.g. spectral, change, fusion, search)"
    )
    parameters: dict[str, Any] | None = Field(
        default=None, description="Preset parameters to populate target workflow"
    )


class ProcessingTraceStep(StrictQueryModel):
    """Audit record of an execution stage in the question answering pipeline."""

    stage: str = Field(description="Pipeline stage name")
    status: str = Field(description="Status of this stage (success, skipped, failed)")
    duration_ms: int = Field(ge=0, description="Duration in milliseconds")
    description: str = Field(description="Description of operation performed")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Stage completion timestamp",
    )


# ---------------------------------------------------------------------------
# Query Request & Answer Envelope
# ---------------------------------------------------------------------------


class QueryRequest(StrictQueryModel):
    """Request payload sent to POST /api/v1/query/ask."""

    question: str = Field(
        min_length=3, max_length=1000, description="User's natural language question"
    )
    workspace_id: str | None = Field(default=None, description="Active workspace identifier")
    context_snapshot: WorkspaceContextSnapshot = Field(
        description="Current workspace snapshot and result references"
    )
    conversation_id: str | None = Field(
        default=None, description="Optional conversation session ID"
    )
    reply_to_answer_id: str | None = Field(
        default=None, description="Optional previous answer ID for follow-ups"
    )
    locale: str | None = Field(default="en", description="Preferred output language/locale")
    request_id: str | None = Field(default=None, description="Correlation request ID")


class QueryAnswer(StrictQueryModel):
    """Complete, evidence-grounded answer returned to the client."""

    answer_id: str = Field(description="Unique answer identifier")
    request_id: str = Field(description="Correlation request ID")
    context_fingerprint: str = Field(
        description="Context snapshot fingerprint this answer binds to"
    )
    answer_status: SufficiencyStatus = Field(description="Overall sufficiency / answer status")
    generation_mode: GenerationMode = Field(description="Mode used to generate the answer")
    plan: QueryPlan = Field(description="Query routing plan")
    summary: str = Field(description="Main natural language answer text")
    claims: list[AnswerClaim] = Field(default_factory=list, description="Structured factual claims")
    evidence_references: list[str] = Field(
        default_factory=list, description="IDs of all referenced evidence items"
    )
    spatial_references: list[str] = Field(
        default_factory=list, description="IDs of all referenced map regions or overlays"
    )
    quality_factors: list[ConfidenceFactor] = Field(
        default_factory=list, description="Confidence factors contributing to score"
    )
    warnings: list[AnalysisWarning] = Field(
        default_factory=list, description="Warnings or caveats associated with this answer"
    )
    limitations: list[str] = Field(
        default_factory=list, description="Explicit limitations and non-physical disclaimers"
    )
    suggested_actions: list[SuggestedNextAction] = Field(
        default_factory=list, description="Suggested next actions if inputs are missing"
    )
    processing_trace: list[ProcessingTraceStep] = Field(
        default_factory=list, description="Complete execution trace"
    )
    data_origin: DataOrigin = Field(
        default=DataOrigin.REAL, description="Data origin (real, mock, fallback)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Answer creation timestamp",
    )
    provider_execution: ProviderExecutionMetadata | None = Field(
        default=None, description="AI provider execution metadata if LLM was invoked"
    )


class QueryCapabilitiesResponse(StrictQueryModel):
    """Capabilities and supported intents of the query answering engine."""

    supported_intents: list[QueryIntent] = Field(description="List of supported intents")
    supported_generation_modes: list[GenerationMode] = Field(
        description="Supported generation modes"
    )
    example_questions: list[str] = Field(description="Curated example questions")
