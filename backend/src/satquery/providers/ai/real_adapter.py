"""Real Gemini AI/VLM provider adapter boundary."""

from __future__ import annotations

from datetime import UTC, datetime

from satquery.api.schemas.providers import (
    DataOrigin,
    ProviderCapability,
    ProviderInfo,
    ProviderMode,
    ProviderStatus,
)
from satquery.core.config import Settings
from satquery.providers.ai.base import (
    AIInterpretationRequest,
    AIInterpretationResponse,
    AIProvider,
    AIProviderNotConfiguredError,
    VisualQARequest,
    VisualQAResponse,
)


class GeminiAIProviderAdapter(AIProvider):
    """Adapter boundary for Google Gemini multimodal vision-language models."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str = "gemini-2.0-flash",
        base_url: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    @classmethod
    def from_settings(cls, settings: Settings) -> GeminiAIProviderAdapter:
        return cls(
            api_key=settings.ai_api_key.get_secret_value() if settings.ai_api_key else None,
            model_name=settings.ai_model,
            base_url=str(settings.ai_base_url) if settings.ai_base_url else None,
            timeout_seconds=settings.ai_timeout_seconds,
            max_retries=settings.ai_max_retries,
        )

    @property
    def provider_id(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return f"Google Gemini VLM ({self._model_name})"

    @property
    def mode(self) -> ProviderMode:
        return ProviderMode.REAL

    @property
    def capabilities(self) -> list[ProviderCapability]:
        return [
            ProviderCapability.VISUAL_QUESTION_ANSWERING,
            ProviderCapability.SPATIAL_GROUNDING,
        ]

    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def health_check(self) -> ProviderInfo:
        configured = self.is_configured()
        status = ProviderStatus.READY if configured else ProviderStatus.NOT_CONFIGURED
        message = (
            f"Gemini AI provider is configured with model '{self._model_name}'."
            if configured
            else (
                "Gemini AI provider requires an API key (GEMINI_API_KEY / SATQUERY_AI_API_KEY) "
                "which is not configured."
            )
        )

        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            provider_type="ai",
            mode=self.mode,
            status=status,
            capabilities=self.capabilities,
            configured=configured,
            healthy=configured,
            data_origin=DataOrigin.REAL,
            last_checked_at=datetime.now(UTC),
            message=message,
            limitations=["Google AI rate limits apply", "Live network access required"],
            metadata={"model": self._model_name},
        )

    async def generate_interpretation(
        self, request: AIInterpretationRequest
    ) -> AIInterpretationResponse:
        if not self.is_configured():
            raise AIProviderNotConfiguredError(self.provider_id)
        # Phase 0C creates the typed boundary without making unverified external network calls
        raise NotImplementedError(
            "Live Gemini inference is implemented in the Phase 4 multimodal reasoning engine."
        )

    async def generate_visual_qa(self, request: VisualQARequest) -> VisualQAResponse:
        if not self.is_configured():
            raise AIProviderNotConfiguredError(self.provider_id)
        raise NotImplementedError(
            "Live Gemini visual inference requires active credentials and network access."
        )
