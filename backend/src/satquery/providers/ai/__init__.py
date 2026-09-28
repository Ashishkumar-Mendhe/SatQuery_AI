"""AI / VLM provider interfaces, mock provider, and registry."""

from satquery.providers.ai.base import (
    AIInterpretationRequest,
    AIInterpretationResponse,
    AIProvider,
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from satquery.providers.ai.mock import MockAIProvider
from satquery.providers.ai.real_adapter import GeminiAIProviderAdapter
from satquery.providers.ai.registry import (
    AIProviderRegistry,
    DisabledAIProvider,
)

__all__ = [
    "AIInterpretationRequest",
    "AIInterpretationResponse",
    "AIProvider",
    "AIProviderError",
    "AIProviderNotConfiguredError",
    "AIProviderRateLimitError",
    "AIProviderRegistry",
    "AIProviderTimeoutError",
    "AIProviderUnavailableError",
    "DisabledAIProvider",
    "GeminiAIProviderAdapter",
    "MockAIProvider",
]
