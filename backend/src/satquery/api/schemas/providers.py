"""Pydantic v2 schemas for provider readiness, capabilities, and execution metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware (UTC)")
    return value.astimezone(UTC)


class ProviderMode(StrEnum):
    MOCK = "mock"
    REAL = "real"
    DISABLED = "disabled"


class ProviderStatus(StrEnum):
    READY = "ready"
    NOT_CONFIGURED = "not_configured"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class DataOrigin(StrEnum):
    REAL = "real"
    MOCK = "mock"
    FALLBACK = "fallback"
    UPLOADED = "uploaded"
    CACHED = "cached"


class ProviderCapability(StrEnum):
    SCENE_SEARCH = "scene_search"
    SCENE_METADATA = "scene_metadata"
    SCENE_PREVIEW = "scene_preview"
    IMAGERY_DOWNLOAD = "imagery_download"
    OPTICAL_IMAGERY = "optical_imagery"
    SAR_IMAGERY = "sar_imagery"
    SPECTRAL_PROCESSING = "spectral_processing"
    CHANGE_DETECTION = "change_detection"
    VISUAL_QUESTION_ANSWERING = "visual_question_answering"
    SPATIAL_GROUNDING = "spatial_grounding"
    REPORT_GENERATION = "report_generation"


class StrictProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class ProviderInfo(StrictProviderModel):
    """Detailed capability and health report of an external or mock provider."""

    provider_id: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=120)
    provider_type: Literal["satellite", "ai", "processing"]
    mode: ProviderMode
    status: ProviderStatus
    capabilities: list[ProviderCapability] = Field(default_factory=list)
    configured: bool
    healthy: bool
    data_origin: DataOrigin
    last_checked_at: datetime | None = None
    message: str | None = None
    limitations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None

    @field_validator("last_checked_at")
    @classmethod
    def normalize_last_checked(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "last_checked_at")


class ProviderExecutionMetadata(StrictProviderModel):
    """Auditable execution provenance attached to provider outputs."""

    provider_id: str = Field(min_length=1, max_length=120)
    provider_mode: ProviderMode
    data_origin: DataOrigin
    requested_at: datetime
    completed_at: datetime | None = None
    duration_milliseconds: int | None = Field(default=None, ge=0)
    attempt_count: int = Field(default=1, ge=1)
    fallback_used: bool = False
    fallback_reason: str | None = None
    cached: bool = False
    provider_request_id: str | None = None
    limitations: list[str] = Field(default_factory=list)

    @field_validator("requested_at", "completed_at")
    @classmethod
    def normalize_execution_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "execution_timestamp")


class ProvidersStatusResponse(StrictProviderModel):
    """Aggregated status and readiness report of all backend providers."""

    environment: str
    contract_version: str = "1.0"
    satellite_provider: ProviderInfo
    ai_provider: ProviderInfo
    processing_mode: str
    mock_fallback_enabled: bool
    overall_readiness: bool
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _as_utc(value, "timestamp")
