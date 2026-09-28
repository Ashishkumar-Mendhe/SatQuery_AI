"""Registry and factory for AI vision-language reasoning providers."""

from __future__ import annotations

from typing import Any

from satquery.api.schemas.analysis import AnalysisWarning, WarningCode, WarningSeverity
from satquery.api.schemas.providers import (
    DataOrigin,
    ProviderInfo,
    ProviderMode,
    ProviderStatus,
)
from satquery.core.config import Settings
from satquery.core.logging import get_logger
from satquery.providers.ai.base import (
    AIInterpretationRequest,
    AIInterpretationResponse,
    AIProvider,
    AIProviderUnavailableError,
    VisualQARequest,
    VisualQAResponse,
)
from satquery.providers.ai.mock import MockAIProvider
from satquery.providers.ai.real_adapter import GeminiAIProviderAdapter

logger = get_logger(__name__)


class DisabledAIProvider(AIProvider):
    """Placeholder provider used when AI reasoning is disabled."""

    @property
    def provider_id(self) -> str:
        return "disabled"

    @property
    def display_name(self) -> str:
        return "Disabled AI Provider"

    @property
    def mode(self) -> ProviderMode:
        return ProviderMode.DISABLED

    @property
    def capabilities(self) -> list[Any]:
        return []

    def is_configured(self) -> bool:
        return False

    async def health_check(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id="disabled",
            display_name="Disabled AI Provider",
            provider_type="ai",
            mode=ProviderMode.DISABLED,
            status=ProviderStatus.DISABLED,
            capabilities=[],
            configured=False,
            healthy=False,
            data_origin=DataOrigin.MOCK,
            message="AI reasoning is disabled in current configuration.",
        )

    async def generate_interpretation(
        self, request: AIInterpretationRequest
    ) -> AIInterpretationResponse:
        raise AIProviderUnavailableError("disabled", "AI reasoning is disabled.")

    async def generate_visual_qa(self, request: VisualQARequest) -> VisualQAResponse:
        raise AIProviderUnavailableError("disabled", "AI reasoning is disabled.")


class AIProviderRegistry:
    """Manages active vision-language AI providers and controlled fallback."""

    def __init__(
        self,
        *,
        primary_provider: AIProvider,
        mock_provider: AIProvider | None = None,
        allow_fallback: bool = True,
    ) -> None:
        self.primary_provider = primary_provider
        self.mock_provider = mock_provider or MockAIProvider()
        self.allow_fallback = allow_fallback

    def get_active_provider(self) -> AIProvider:
        """Return the active primary AI provider."""
        return self.primary_provider

    @classmethod
    def from_settings(cls, settings: Settings) -> AIProviderRegistry:
        primary: AIProvider
        if not settings.ai_enabled or settings.ai_provider_mode == "disabled":
            primary = DisabledAIProvider()
        elif settings.ai_provider_mode == "mock":
            primary = MockAIProvider(model_id=settings.ai_model)
        else:
            primary = GeminiAIProviderAdapter.from_settings(settings)

        return cls(
            primary_provider=primary,
            mock_provider=MockAIProvider(model_id=settings.ai_model),
            allow_fallback=settings.allow_mock_fallback,
        )

    async def health_check(self) -> ProviderInfo:
        return await self.primary_provider.health_check()

    async def generate_interpretation(
        self, request: AIInterpretationRequest
    ) -> AIInterpretationResponse:
        try:
            return await self.primary_provider.generate_interpretation(request)
        except Exception as exc:
            if not self.allow_fallback:
                logger.error(
                    "ai_provider_interpretation_failed_no_fallback",
                    extra={"provider": self.primary_provider.provider_id, "error": str(exc)},
                )
                raise

            logger.warning(
                "ai_provider_interpretation_failed_using_mock_fallback",
                extra={"provider": self.primary_provider.provider_id, "error": str(exc)},
            )
            mock_resp = await self.mock_provider.generate_interpretation(request)
            mock_resp.execution_metadata.data_origin = DataOrigin.FALLBACK
            mock_resp.execution_metadata.fallback_used = True
            mock_resp.execution_metadata.fallback_reason = (
                f"Primary AI provider '{self.primary_provider.provider_id}' failed: {exc!s}"
            )
            mock_resp.warnings.append(
                AnalysisWarning(
                    code=WarningCode.MOCK_DATA_USED,
                    severity=WarningSeverity.MEDIUM,
                    title="Mock AI Fallback Used",
                    message=(
                        "AI interpretation used deterministic offline reasoning because "
                        f"primary provider '{self.primary_provider.provider_id}' was "
                        "unavailable or unconfigured."
                    ),
                    suggested_action=(
                        "Configure a valid AI API key (GEMINI_API_KEY) for production reasoning."
                    ),
                )
            )
            return mock_resp

    async def generate_visual_qa(self, request: VisualQARequest) -> VisualQAResponse:
        try:
            return await self.primary_provider.generate_visual_qa(request)
        except Exception as exc:
            if not self.allow_fallback:
                logger.error(
                    "ai_provider_visual_qa_failed_no_fallback",
                    extra={"provider": self.primary_provider.provider_id, "error": str(exc)},
                )
                raise

            logger.warning(
                "ai_provider_visual_qa_failed_using_mock_fallback",
                extra={"provider": self.primary_provider.provider_id, "error": str(exc)},
            )
            mock_resp = await self.mock_provider.generate_visual_qa(request)
            mock_resp.execution_metadata.data_origin = DataOrigin.FALLBACK
            mock_resp.execution_metadata.fallback_used = True
            mock_resp.execution_metadata.fallback_reason = (
                f"Primary AI provider '{self.primary_provider.provider_id}' failed: {exc!s}"
            )
            mock_resp.warnings.append(
                AnalysisWarning(
                    code=WarningCode.MOCK_DATA_USED,
                    severity=WarningSeverity.MEDIUM,
                    title="Mock AI Fallback Used",
                    message=(
                        "Visual QA used deterministic offline reasoning because "
                        f"primary provider '{self.primary_provider.provider_id}' was "
                        "unavailable or unconfigured."
                    ),
                    suggested_action=(
                        "Configure a valid AI API key (GEMINI_API_KEY) for production vision reasoning."
                    ),
                )
            )
            return mock_resp

    async def aclose(self) -> None:
        await self.primary_provider.aclose()
        await self.mock_provider.aclose()
