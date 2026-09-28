"""Base interfaces, request/response models, and errors for AI/VLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from satquery.api.schemas.analysis import (
    AnalysisMode,
    AnalysisWarning,
    AOIGeometry,
    EvidenceItem,
    Finding,
    SatelliteScene,
)
from satquery.api.schemas.providers import (
    ProviderCapability,
    ProviderExecutionMetadata,
    ProviderInfo,
    ProviderMode,
)
from satquery.api.schemas.visual import (
    ImageManifest,
    VisualObservation,
    VisualOperation,
)


class StrictAIRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AIInterpretationRequest(StrictAIRequestModel):
    """Contextual evidence and question sent to the vision-language assistant."""

    question: str = Field(min_length=3, max_length=1000)
    mode: AnalysisMode
    scenes: list[SatelliteScene] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    aoi_geometry: AOIGeometry | None = None
    language: str = "en"
    limitations: list[str] = Field(default_factory=list)


class AIInterpretationResponse(StrictAIRequestModel):
    """Structured natural language interpretation and candidate findings grounded in evidence."""

    answer: str
    evidence_ids: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    model_id: str
    limitations: list[str] = Field(default_factory=list)
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    execution_metadata: ProviderExecutionMetadata


class VisualQARequest(StrictAIRequestModel):
    """Visual Question Answering request payload sent to the vision-capable AI provider."""

    question: str = Field(min_length=3, max_length=1000)
    manifests: list[ImageManifest] = Field(default_factory=list)
    image_payloads: list[bytes] = Field(default_factory=list)
    operation: VisualOperation = Field(default=VisualOperation.DESCRIBE)
    existing_evidence_ids: list[str] = Field(default_factory=list)
    language: str = "en"


class VisualQAResponse(StrictAIRequestModel):
    """Structured VQA response containing natural language synthesis and visual observations."""

    answer: str
    observations: list[VisualObservation] = Field(default_factory=list)
    model_id: str
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    execution_metadata: ProviderExecutionMetadata


# ---------------------------------------------------------------------------
# AI Provider Exceptions
# ---------------------------------------------------------------------------


class AIProviderError(Exception):
    """Base error for AI provider failures."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 500,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}


class AIProviderNotConfiguredError(AIProviderError):
    def __init__(self, provider_id: str, message: str | None = None) -> None:
        msg = (
            message
            or f"AI provider '{provider_id}' is not configured with required API key or endpoint."
        )
        super().__init__("AI_PROVIDER_NOT_CONFIGURED", msg, status_code=503, retryable=False)


class AIProviderRateLimitError(AIProviderError):
    def __init__(self, provider_id: str, message: str | None = None) -> None:
        msg = message or f"Rate limit exceeded for AI provider '{provider_id}'."
        super().__init__("AI_PROVIDER_RATE_LIMITED", msg, status_code=429, retryable=True)


class AIProviderTimeoutError(AIProviderError):
    def __init__(self, provider_id: str, message: str | None = None) -> None:
        msg = message or f"Timeout communicating with AI provider '{provider_id}'."
        super().__init__("AI_PROVIDER_TIMEOUT", msg, status_code=504, retryable=True)


class AIProviderUnavailableError(AIProviderError):
    def __init__(self, provider_id: str, message: str | None = None) -> None:
        msg = message or f"AI provider '{provider_id}' is currently unavailable."
        super().__init__("AI_PROVIDER_UNAVAILABLE", msg, status_code=503, retryable=True)


# ---------------------------------------------------------------------------
# AI Provider Interface
# ---------------------------------------------------------------------------


class AIProvider(ABC):
    """Abstract interface governing vision-language reasoning providers."""

    @property
    @abstractmethod
    def provider_id(self) -> str: ...

    @property
    @abstractmethod
    def display_name(self) -> str: ...

    @property
    @abstractmethod
    def mode(self) -> ProviderMode: ...

    @property
    @abstractmethod
    def capabilities(self) -> list[ProviderCapability]: ...

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    async def health_check(self) -> ProviderInfo: ...

    @abstractmethod
    async def generate_interpretation(
        self, request: AIInterpretationRequest
    ) -> AIInterpretationResponse: ...

    @abstractmethod
    async def generate_visual_qa(self, request: VisualQARequest) -> VisualQAResponse: ...

    async def aclose(self) -> None:
        """Release underlying client resources."""
        return None
