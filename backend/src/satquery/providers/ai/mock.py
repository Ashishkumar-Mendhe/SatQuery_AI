"""Deterministic offline mock AI vision-language provider."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    Finding,
    FindingSeverity,
    WarningCode,
    WarningSeverity,
)
from satquery.api.schemas.providers import (
    DataOrigin,
    ProviderCapability,
    ProviderExecutionMetadata,
    ProviderInfo,
    ProviderMode,
    ProviderStatus,
)
from satquery.api.schemas.visual import (
    CoordinateStatus,
    ImageInputRole,
    MapGroundingStatus,
    ObservationSource,
    SemanticStatus,
    VisualObservation,
    VisualOperation,
)
from satquery.providers.ai.base import (
    AIInterpretationRequest,
    AIInterpretationResponse,
    AIProvider,
    VisualQARequest,
    VisualQAResponse,
)


class MockAIProvider(AIProvider):
    """Deterministic offline AI assistant provider for testing and disconnected demo mode."""

    def __init__(self, *, model_id: str = "mock-vlm-v1") -> None:
        self._model_id = model_id

    @property
    def provider_id(self) -> str:
        return "mock"

    @property
    def display_name(self) -> str:
        return "Mock Vision-Language Assistant (Offline Grounded)"

    @property
    def mode(self) -> ProviderMode:
        return ProviderMode.MOCK

    @property
    def capabilities(self) -> list[ProviderCapability]:
        return [
            ProviderCapability.VISUAL_QUESTION_ANSWERING,
            ProviderCapability.SPATIAL_GROUNDING,
        ]

    def is_configured(self) -> bool:
        return True

    async def health_check(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            provider_type="ai",
            mode=self.mode,
            status=ProviderStatus.READY,
            capabilities=self.capabilities,
            configured=True,
            healthy=True,
            data_origin=DataOrigin.MOCK,
            last_checked_at=datetime.now(UTC),
            message="Mock AI provider is ready for grounded offline interpretation.",
            limitations=[
                "Rule-based synthetic reasoning only",
                "Does not execute live deep learning models",
            ],
            metadata={"model_id": self._model_id},
        )

    async def generate_interpretation(
        self, request: AIInterpretationRequest
    ) -> AIInterpretationResponse:
        start_time = datetime.now(UTC)

        # -------------------------------------------------------------------
        # Grounding Rule: If no evidence is supplied, do NOT invent answers!
        # -------------------------------------------------------------------
        if not request.evidence:
            completed_time = datetime.now(UTC)
            return AIInterpretationResponse(
                answer=(
                    f"Unable to answer query '{request.question}' because no quantitative evidence "
                    "or satellite imagery measurements were provided for this Area of Interest."
                ),
                evidence_ids=[],
                findings=[],
                confidence=0.10,
                model_id=self._model_id,
                limitations=["No physical or spectral measurements available to support analysis."],
                warnings=[
                    AnalysisWarning(
                        code=WarningCode.INSUFFICIENT_EVIDENCE,
                        severity=WarningSeverity.HIGH,
                        title="Insufficient Evidence",
                        message=(
                            "Cannot provide a grounded analytical answer without measured "
                            "satellite evidence."
                        ),
                        suggested_action=(
                            "Select valid satellite scenes and compute spectral indices "
                            "or change metrics first."
                        ),
                    )
                ],
                execution_metadata=ProviderExecutionMetadata(
                    provider_id=self.provider_id,
                    provider_mode=self.mode,
                    data_origin=DataOrigin.MOCK,
                    requested_at=start_time,
                    completed_at=completed_time,
                    duration_milliseconds=max(
                        1, int((completed_time - start_time).total_seconds() * 1000)
                    ),
                    attempt_count=1,
                    limitations=["Deterministic offline mock reasoning"],
                ),
            )

        # -------------------------------------------------------------------
        # Grounded Reasoning: Base findings and answer on input evidence
        # -------------------------------------------------------------------
        evidence_ids = [e.id for e in request.evidence]
        avg_confidence = sum(e.confidence for e in request.evidence) / len(request.evidence)

        # Build grounded summary from evidence titles and measurements
        evidence_summaries = [f"- {e.title}: {e.description}" for e in request.evidence]
        grounded_answer = (
            f"Based on {len(request.evidence)} measured satellite evidence item(s), "
            f"analysis for '{request.question}' indicates the following observed conditions:\n"
            + "\n".join(evidence_summaries)
        )

        findings: list[Finding] = []
        for ev in request.evidence:
            findings.append(
                Finding(
                    id=f"fnd-{uuid4().hex[:8]}",
                    title=f"Observation: {ev.title}",
                    description=ev.description,
                    severity=(
                        FindingSeverity.INFORMATIONAL
                        if ev.confidence > 0.7
                        else FindingSeverity.LOW
                    ),
                    category=request.mode.value,
                    evidence_ids=[ev.id],
                    geometry=ev.geometry,
                    confidence=round(ev.confidence, 2),
                    interpretation=(
                        f"Interpreted from measured evidence {ev.id} ({ev.provenance.computation})."
                    ),
                    limitations=[
                        "Subject to sensor resolution and acquisition atmospheric conditions."
                    ],
                )
            )

        completed_time = datetime.now(UTC)
        return AIInterpretationResponse(
            answer=grounded_answer,
            evidence_ids=evidence_ids,
            findings=findings,
            confidence=round(avg_confidence, 2),
            model_id=self._model_id,
            limitations=["Synthetic reasoning grounded in provided evidence items."],
            warnings=[],
            execution_metadata=ProviderExecutionMetadata(
                provider_id=self.provider_id,
                provider_mode=self.mode,
                data_origin=DataOrigin.MOCK,
                requested_at=start_time,
                completed_at=completed_time,
                duration_milliseconds=max(
                    1, int((completed_time - start_time).total_seconds() * 1000)
                ),
                attempt_count=1,
                limitations=["Deterministic offline mock reasoning"],
            ),
        )

    async def generate_visual_qa(self, request: VisualQARequest) -> VisualQAResponse:
        start_time = datetime.now(UTC)

        if not request.manifests:
            completed_time = datetime.now(UTC)
            return VisualQAResponse(
                answer=(
                    f"Unable to answer visual query '{request.question}' because no imagery "
                    "or image manifests were provided."
                ),
                observations=[],
                model_id=self._model_id,
                warnings=[
                    AnalysisWarning(
                        code=WarningCode.INSUFFICIENT_EVIDENCE,
                        title="Insufficient Imagery",
                        message="No imagery assets available for visual question answering.",
                        severity=WarningSeverity.MEDIUM,
                    )
                ],
                limitations=["No image pixels available for visual inspection."],
                execution_metadata=ProviderExecutionMetadata(
                    provider_id=self.provider_id,
                    provider_mode=self.mode,
                    data_origin=DataOrigin.MOCK,
                    requested_at=start_time,
                    completed_at=completed_time,
                    duration_milliseconds=max(
                        1, int((completed_time - start_time).total_seconds() * 1000)
                    ),
                    attempt_count=1,
                    limitations=["Deterministic offline mock VQA reasoning"],
                ),
            )

        observations: list[VisualObservation] = []
        answer_parts: list[str] = []

        if len(request.manifests) == 1:
            manifest = request.manifests[0]
            answer_parts.append(
                f"Visual inspection of selected AOI crop from scene '{manifest.source_scene_id}' "
                f"({manifest.rendering_type}, {manifest.submitted_width}x{manifest.submitted_height} px) "
                f"for question '{request.question}':"
            )

            if request.operation == VisualOperation.LOCATE:
                obs1 = VisualObservation(
                    observation_id=f"obs-{uuid4().hex[:8]}",
                    input_image_id=manifest.input_image_id,
                    role=manifest.role,
                    label="Prominent Surface Feature",
                    description="Distinctive spatial cluster with higher visual contrast against background.",
                    canonical_box=[0.25, 0.25, 0.75, 0.75],
                    observation_source=ObservationSource.MODEL_PREDICTION,
                    coordinate_status=CoordinateStatus.VALID,
                    semantic_status=SemanticStatus.UNVERIFIED_PREDICTION,
                    map_grounding_status=(
                        MapGroundingStatus.AVAILABLE
                        if manifest.crs
                        else MapGroundingStatus.IMAGE_ONLY_NO_GEOREFERENCE
                    ),
                    model_confidence=0.88,
                    associated_evidence_ids=request.existing_evidence_ids,
                    warnings=[],
                )
                observations.append(obs1)
                answer_parts.append(
                    "Identified 1 prominent candidate visual region with bounding coordinates."
                )
            else:
                obs1 = VisualObservation(
                    observation_id=f"obs-{uuid4().hex[:8]}",
                    input_image_id=manifest.input_image_id,
                    role=manifest.role,
                    label="Central Visible Pattern",
                    description="Homogeneous texture corresponding to ground reflectance in central sector.",
                    canonical_box=[0.2, 0.2, 0.6, 0.6],
                    observation_source=ObservationSource.MODEL_PREDICTION,
                    coordinate_status=CoordinateStatus.VALID,
                    semantic_status=SemanticStatus.UNVERIFIED_PREDICTION,
                    map_grounding_status=(
                        MapGroundingStatus.AVAILABLE
                        if manifest.crs
                        else MapGroundingStatus.IMAGE_ONLY_NO_GEOREFERENCE
                    ),
                    model_confidence=0.92,
                    associated_evidence_ids=request.existing_evidence_ids,
                    warnings=[],
                )
                obs2 = VisualObservation(
                    observation_id=f"obs-{uuid4().hex[:8]}",
                    input_image_id=manifest.input_image_id,
                    role=manifest.role,
                    label="Peripheral Boundary Feature",
                    description="Narrow linear feature along southern sector boundary.",
                    canonical_box=[0.1, 0.65, 0.9, 0.85],
                    observation_source=ObservationSource.MODEL_PREDICTION,
                    coordinate_status=CoordinateStatus.VALID,
                    semantic_status=SemanticStatus.UNVERIFIED_PREDICTION,
                    map_grounding_status=(
                        MapGroundingStatus.AVAILABLE
                        if manifest.crs
                        else MapGroundingStatus.IMAGE_ONLY_NO_GEOREFERENCE
                    ),
                    model_confidence=0.85,
                    associated_evidence_ids=request.existing_evidence_ids,
                    warnings=[],
                )
                observations.extend([obs1, obs2])
                answer_parts.append(
                    "Identified 2 structured visual features (central pattern and peripheral boundary feature)."
                )

        else:
            # Bi-temporal comparison mode (before and after)
            before_manifest = request.manifests[0]
            after_manifest = request.manifests[1]
            answer_parts.append(
                f"Bi-temporal visual comparison between '{before_manifest.source_scene_id}' (before) "
                f"and '{after_manifest.source_scene_id}' (after):"
            )

            obs_before = VisualObservation(
                observation_id=f"obs-{uuid4().hex[:8]}",
                input_image_id=before_manifest.input_image_id,
                role=ImageInputRole.BEFORE,
                label="Baseline Surface State",
                description="Uniform baseline reflectance texture across central region in earlier image.",
                canonical_box=[0.25, 0.25, 0.65, 0.65],
                observation_source=ObservationSource.MODEL_PREDICTION,
                coordinate_status=CoordinateStatus.VALID,
                semantic_status=SemanticStatus.UNVERIFIED_PREDICTION,
                map_grounding_status=MapGroundingStatus.AVAILABLE,
                model_confidence=0.86,
                associated_evidence_ids=request.existing_evidence_ids,
                warnings=[],
            )
            obs_after = VisualObservation(
                observation_id=f"obs-{uuid4().hex[:8]}",
                input_image_id=after_manifest.input_image_id,
                role=ImageInputRole.AFTER,
                label="Candidate Visual Difference",
                description="Visual disturbance and reflectance contrast shift apparent in later image.",
                canonical_box=[0.25, 0.25, 0.65, 0.65],
                observation_source=ObservationSource.MODEL_PREDICTION,
                coordinate_status=CoordinateStatus.VALID,
                semantic_status=SemanticStatus.UNVERIFIED_PREDICTION,
                map_grounding_status=MapGroundingStatus.AVAILABLE,
                model_confidence=0.90,
                associated_evidence_ids=request.existing_evidence_ids,
                warnings=[],
            )
            observations.extend([obs_before, obs_after])
            answer_parts.append(
                "Apparent visual difference observed in central sector between baseline and later imagery. "
                "Candidate visual difference is proposed as unverified visual prediction."
            )

        completed_time = datetime.now(UTC)
        return VisualQAResponse(
            answer=" ".join(answer_parts),
            observations=observations,
            model_id=self._model_id,
            warnings=[],
            limitations=[
                "Model visual observations are unverified predictions and do not confirm physical ground truth.",
                "Visual appearance is subject to atmospheric stretching, sun angle, and sensor resolution limits.",
            ],
            execution_metadata=ProviderExecutionMetadata(
                provider_id=self.provider_id,
                provider_mode=self.mode,
                data_origin=DataOrigin.MOCK,
                requested_at=start_time,
                completed_at=completed_time,
                duration_milliseconds=max(
                    1, int((completed_time - start_time).total_seconds() * 1000)
                ),
                attempt_count=1,
                limitations=["Deterministic offline mock VQA reasoning"],
            ),
        )
