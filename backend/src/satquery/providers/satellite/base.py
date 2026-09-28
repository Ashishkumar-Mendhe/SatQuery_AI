"""Base interfaces, request/response models, and errors for satellite providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    AOIGeometry,
    DateRange,
    SatelliteScene,
    SensorType,
)
from satquery.api.schemas.providers import (
    DataOrigin,
    ProviderCapability,
    ProviderExecutionMetadata,
    ProviderInfo,
    ProviderMode,
)


class StrictSatelliteRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SceneSearchRequest(StrictSatelliteRequestModel):
    """Normalized query parameters for satellite scene catalog discovery."""

    aoi: AOIGeometry
    date_range: DateRange | None = None
    collections: list[str] = Field(default_factory=list)
    sensor_types: list[SensorType] = Field(default_factory=list)
    max_cloud_cover: float = Field(default=20.0, ge=0.0, le=100.0)
    limit: int = Field(default=50, ge=1, le=200)
    sort_order: Literal["asc", "desc"] = "desc"
    required_bands: list[str] = Field(default_factory=list)
    include_preview: bool = True
    cursor: str | None = None


class SceneSearchResponse(StrictSatelliteRequestModel):
    """Normalized response payload containing discovered satellite scenes."""

    request_id: str
    scenes: list[SatelliteScene]
    total_matched: int | None = None
    returned_count: int = Field(ge=0)
    next_cursor: str | None = None
    provider_id: str
    execution: ProviderExecutionMetadata
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    data_origin: DataOrigin


# ---------------------------------------------------------------------------
# Structured Provider Exceptions
# ---------------------------------------------------------------------------


class SatelliteProviderError(Exception):
    """Base error for satellite provider failures."""

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


class ProviderNotConfiguredError(SatelliteProviderError):
    def __init__(self, provider_id: str, message: str | None = None) -> None:
        msg = message or (
            f"Satellite provider '{provider_id}' is not configured with required credentials "
            "or endpoint."
        )
        super().__init__("PROVIDER_NOT_CONFIGURED", msg, status_code=503, retryable=False)


class ProviderAuthenticationError(SatelliteProviderError):
    def __init__(self, provider_id: str, message: str | None = None) -> None:
        msg = message or f"Authentication failed for satellite provider '{provider_id}'."
        super().__init__("PROVIDER_AUTHENTICATION_FAILED", msg, status_code=401, retryable=False)


class ProviderRateLimitError(SatelliteProviderError):
    def __init__(self, provider_id: str, message: str | None = None) -> None:
        msg = message or f"Rate limit exceeded for satellite provider '{provider_id}'."
        super().__init__("PROVIDER_RATE_LIMITED", msg, status_code=429, retryable=True)


class ProviderTimeoutError(SatelliteProviderError):
    def __init__(self, provider_id: str, message: str | None = None) -> None:
        msg = message or f"Timeout communicating with satellite provider '{provider_id}'."
        super().__init__("PROVIDER_TIMEOUT", msg, status_code=504, retryable=True)


class ProviderUnavailableError(SatelliteProviderError):
    def __init__(self, provider_id: str, message: str | None = None) -> None:
        msg = message or f"Satellite provider '{provider_id}' is currently unavailable."
        super().__init__("PROVIDER_UNAVAILABLE", msg, status_code=503, retryable=True)


class InvalidProviderResponseError(SatelliteProviderError):
    def __init__(self, provider_id: str, message: str | None = None) -> None:
        msg = message or (
            f"Received malformed or invalid response from satellite provider '{provider_id}'."
        )
        super().__init__("INVALID_PROVIDER_RESPONSE", msg, status_code=502, retryable=False)


class SceneNotFoundError(SatelliteProviderError):
    def __init__(self, scene_id: str) -> None:
        super().__init__(
            "SCENE_NOT_FOUND",
            f"Satellite scene '{scene_id}' was not found.",
            status_code=404,
            retryable=False,
        )


class UnsupportedProviderCapabilityError(SatelliteProviderError):
    def __init__(self, capability: str, provider_id: str) -> None:
        super().__init__(
            "UNSUPPORTED_PROVIDER_CAPABILITY",
            f"Capability '{capability}' is not supported by satellite provider '{provider_id}'.",
            status_code=400,
            retryable=False,
        )


# ---------------------------------------------------------------------------
# Provider Interface
# ---------------------------------------------------------------------------


class SatelliteProvider(ABC):
    """Abstract base class governing all satellite imagery providers."""

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
    async def search_scenes(self, request: SceneSearchRequest) -> SceneSearchResponse: ...

    @abstractmethod
    async def get_scene(self, scene_id: str) -> SatelliteScene: ...

    async def aclose(self) -> None:
        """Release any underlying client resources."""
        return None
