"""Pydantic v2 schemas for temporal scene discovery, pairing, and compatibility validation."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from satquery.api.schemas.analysis import (
    AnalysisMode,
    AnalysisWarning,
    AOIGeometry,
    BoundingBox,
    SatelliteScene,
    SceneSelection,
    SensorType,
    WarningSeverity,
)
from satquery.api.schemas.providers import (
    DataOrigin,
    ProviderExecutionMetadata,
)

TEMPORAL_PAIRING_SCHEMA_VERSION: Literal["1.0"] = "1.0"
MAX_TEMPORAL_WINDOW_DAYS: int = 730  # Max 2 years per window
MAX_TEMPORAL_GAP_DAYS: int = 1825  # Max 5 years gap between before/after acquisitions


class StrictTemporalModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PairCompatibilityStatus(StrEnum):
    COMPATIBLE = "compatible"
    COMPATIBLE_WITH_WARNINGS = "compatible_with_warnings"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Temporal Window & Search Models
# ---------------------------------------------------------------------------


class TemporalWindow(StrictTemporalModel):
    """Normalized temporal window specification with validation rules."""

    start_date: str = Field(description="Start date (YYYY-MM-DD or ISO 8601 UTC)")
    end_date: str = Field(description="End date (YYYY-MM-DD or ISO 8601 UTC)")
    label: str = Field(
        default="period",
        description="Human-readable label (e.g., 'before', 'after')",
    )
    target_date: str | None = Field(default=None, description="Optional target focus date")

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        start_raw = self.start_date.replace("Z", "+00:00")
        end_raw = self.end_date.replace("Z", "+00:00")
        try:
            start_dt = datetime.fromisoformat(start_raw)
            end_dt = datetime.fromisoformat(end_raw)
            if start_dt > end_dt:
                raise ValueError(
                    f"start_date ({self.start_date}) cannot be after end_date ({self.end_date})"
                )

            # Check window span
            delta_days = (end_dt - start_dt).total_seconds() / 86400.0
            if delta_days > MAX_TEMPORAL_WINDOW_DAYS:
                raise ValueError(
                    f"Temporal window duration ({delta_days:.1f} days) exceeds maximum allowed "
                    f"limit of {MAX_TEMPORAL_WINDOW_DAYS} days"
                )

            # Check target date if provided
            if self.target_date:
                target_raw = self.target_date.replace("Z", "+00:00")
                target_dt = datetime.fromisoformat(target_raw)
                if not (start_dt <= target_dt <= end_dt):
                    raise ValueError(
                        f"target_date ({self.target_date}) must fall within the window "
                        f"[{self.start_date}, {self.end_date}]"
                    )
        except ValueError as exc:
            if (
                "cannot be after" in str(exc)
                or "exceeds maximum" in str(exc)
                or "must fall within" in str(exc)
            ):
                raise
            # Fallback for simple YYYY-MM-DD strings
            if self.start_date > self.end_date:
                raise ValueError(
                    f"start_date ({self.start_date}) cannot be after end_date ({self.end_date})"
                ) from exc
        return self


class PairingPreferences(StrictTemporalModel):
    """User preferences for automatic and validated temporal pairing."""

    prefer_same_collection: bool = Field(
        default=True,
        description="Prefer scenes from identical collection",
    )
    prefer_same_platform: bool = Field(
        default=True,
        description="Prefer scenes from same platform family",
    )
    prefer_same_sensor: bool = Field(
        default=True,
        description="Prefer scenes from identical sensor type",
    )
    prefer_lowest_cloud_cover: bool = Field(
        default=True,
        description="Prefer optical scenes with lower cloud cover",
    )
    prefer_closest_season: bool = Field(
        default=False,
        description="Prefer pairs from matching seasonal phenology",
    )
    maximum_temporal_gap_days: int | None = Field(
        default=MAX_TEMPORAL_GAP_DAYS,
        ge=1,
        le=3650,
        description="Maximum acceptable temporal gap in days",
    )
    maximum_acquisition_time_difference_minutes: float | None = Field(
        default=None,
        ge=0.0,
        description="Maximum acquisition time-of-day delta in minutes",
    )
    required_polarizations: list[str] | None = Field(
        default=None,
        description="Required SAR polarizations (e.g. ['VV', 'VH'])",
    )
    required_bands: list[str] | None = Field(
        default=None,
        description="Required optical spectral bands",
    )
    min_aoi_coverage_percent: float = Field(
        default=10.0,
        ge=0.0,
        le=100.0,
        description="Minimum AOI intersection coverage percentage",
    )


class TemporalSearchRequest(StrictTemporalModel):
    """Query parameters for searching before and after scene candidates."""

    aoi: AOIGeometry = Field(description="Validated AOI geometry")
    before_window: TemporalWindow = Field(
        description="Temporal window for baseline 'before' period"
    )
    after_window: TemporalWindow = Field(
        description="Temporal window for comparative 'after' period"
    )
    collections: list[str] = Field(
        default_factory=list,
        description="Target satellite collections",
    )
    sensor_types: list[SensorType] = Field(
        default_factory=list,
        description="Sensor types",
    )
    max_cloud_cover: float = Field(
        default=20.0,
        ge=0.0,
        le=100.0,
        description="Cloud cover ceiling",
    )
    required_bands: list[str] = Field(
        default_factory=list,
        description="Required spectral bands",
    )
    limit_per_window: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Max scenes per window",
    )
    sort_order: Literal["asc", "desc"] = Field(
        default="desc",
        description="Chronological sort order",
    )
    include_preview: bool = Field(default=True, description="Include preview URLs")
    pairing_preferences: PairingPreferences | None = Field(
        default=None,
        description="Optional temporal pairing preferences",
    )

    @model_validator(mode="after")
    def validate_temporal_windows(self) -> Self:
        # Check start date ordering
        b_start = self.before_window.start_date.replace("Z", "+00:00")
        a_start = self.after_window.start_date.replace("Z", "+00:00")
        try:
            b_dt = datetime.fromisoformat(b_start)
            a_dt = datetime.fromisoformat(a_start)
            if b_dt > a_dt:
                raise ValueError("before_window start_date cannot be after after_window start_date")
        except ValueError as exc:
            if "cannot be after" in str(exc):
                raise
            if self.before_window.start_date > self.after_window.start_date:
                raise ValueError(
                    "before_window start_date cannot be after after_window start_date"
                ) from exc
        return self


# ---------------------------------------------------------------------------
# Compatibility & Validation Models
# ---------------------------------------------------------------------------


class PairCompatibilityIssue(StrictTemporalModel):
    """Structured issue or incompatibility descriptor for a scene pair."""

    code: str = Field(description="Stable issue code (e.g., SAME_SCENE_SELECTED)")
    severity: WarningSeverity = Field(description="Issue severity level")
    title: str = Field(description="Human-readable title")
    message: str = Field(description="Detailed explanation")
    field: str | None = Field(default=None, description="Affected field or property")
    suggested_action: str | None = Field(default=None, description="Actionable recommendation")
    blocking: bool = Field(
        default=False, description="Whether this issue prevents valid comparison"
    )
    metadata: dict[str, Any] | None = Field(default=None, description="Supplementary context")


class CompatibilityFactorScore(StrictTemporalModel):
    """Detailed score and rationale for an individual compatibility factor."""

    name: str = Field(
        description="Factor identifier (e.g., spatial_coverage, cloud_cover, collection)"
    )
    score: float = Field(ge=0.0, le=1.0, description="Normalized factor score [0.0 - 1.0]")
    weight: float = Field(ge=0.0, le=1.0, description="Normalized factor weight")
    weighted_score: float = Field(ge=0.0, le=1.0, description="weight * score")
    status: Literal["optimal", "acceptable", "suboptimal", "incompatible", "unknown"] = Field(
        description="Qualitative status"
    )
    details: str = Field(description="Human-readable assessment")


class SpatialOverlapMetrics(StrictTemporalModel):
    """Metadata-based spatial coverage and intersection metrics for the scene pair."""

    before_aoi_coverage_percent: float = Field(
        ge=0.0, le=100.0, description="Percentage of AOI covered by before scene"
    )
    after_aoi_coverage_percent: float = Field(
        ge=0.0, le=100.0, description="Percentage of AOI covered by after scene"
    )
    mutual_aoi_coverage_percent: float = Field(
        ge=0.0,
        le=100.0,
        description="Percentage of AOI covered by both scenes simultaneously",
    )
    scene_overlap_percent: float = Field(
        ge=0.0,
        le=100.0,
        description="Percentage overlap between the two scene footprints",
    )
    shared_bbox: BoundingBox | None = Field(
        default=None, description="Shared bounding box [minX, minY, maxX, maxY]"
    )


class RecommendedPair(StrictTemporalModel):
    """Top-ranked deterministic scene pair recommendation."""

    before_scene_id: str = Field(description="Recommended before scene ID")
    after_scene_id: str = Field(description="Recommended after scene ID")
    compatibility_score: float = Field(ge=0.0, le=1.0, description="Pair compatibility score")
    status: PairCompatibilityStatus = Field(description="Compatibility status")
    reason: str = Field(description="Summary rationale for recommendation")
    explanation: list[str] = Field(default_factory=list, description="Factor-by-factor explanation")


class TemporalSceneCandidates(StrictTemporalModel):
    """Discovered candidate scenes for both before and after periods."""

    search_id: str = Field(description="Unique search correlation ID")
    before_scenes: list[SatelliteScene] = Field(
        default_factory=list, description="Baseline before candidates"
    )
    after_scenes: list[SatelliteScene] = Field(
        default_factory=list, description="Comparative after candidates"
    )
    provider_id: str = Field(description="Provider identifier")
    execution: ProviderExecutionMetadata = Field(description="Provider execution telemetry")
    warnings: list[AnalysisWarning] = Field(default_factory=list, description="Search warnings")
    data_origin: DataOrigin = Field(description="Data origin (real, mock, fallback)")
    generated_at: datetime = Field(description="UTC timestamp of query execution")
    recommended_pair: RecommendedPair | None = Field(
        default=None, description="Top recommended candidate pair if available"
    )


class TemporalPairValidationRequest(StrictTemporalModel):
    """Request payload to validate compatibility between a before and after scene."""

    aoi: AOIGeometry = Field(description="Target AOI geometry")
    before_scene: SatelliteScene = Field(description="Baseline before satellite scene")
    after_scene: SatelliteScene = Field(description="Comparative after satellite scene")
    analysis_mode: AnalysisMode = Field(
        default=AnalysisMode.CHANGE_DETECTION, description="Intended analysis mode"
    )
    pairing_preferences: PairingPreferences | None = Field(
        default=None, description="Optional pairing preferences"
    )


class TemporalPairValidationResult(StrictTemporalModel):
    """Authoritative validation result for a candidate scene pair."""

    valid: bool = Field(description="True if pair is strictly valid for change detection")
    status: PairCompatibilityStatus = Field(description="Overall compatibility status")
    before_scene_id: str = Field(description="Selected before scene ID")
    after_scene_id: str = Field(description="Selected after scene ID")
    temporal_gap_days: float = Field(description="Temporal gap in days (T_after - T_before)")
    temporal_gap_hours: float | None = Field(default=None, description="Temporal gap in hours")
    compatibility_score: float = Field(
        ge=0.0, le=1.0, description="Overall compatibility score [0.0 - 1.0]"
    )
    factors: list[CompatibilityFactorScore] = Field(
        default_factory=list, description="Factor breakdown scores and descriptions"
    )
    issues: list[PairCompatibilityIssue] = Field(
        default_factory=list, description="Detected compatibility issues and warnings"
    )
    warnings: list[AnalysisWarning] = Field(
        default_factory=list, description="Standardized analysis warnings"
    )
    spatial_metrics: SpatialOverlapMetrics | None = Field(
        default=None, description="Spatial coverage and intersection metrics"
    )
    normalized_selection: SceneSelection | None = Field(
        default=None, description="Canonical normalized scene selection"
    )
    data_origin_status: str = Field(
        default="real",
        description="Origin alignment status ('real', 'mock', 'fallback', 'mixed')",
    )
    validation_version: str = Field(default=TEMPORAL_PAIRING_SCHEMA_VERSION)
