"""Pydantic v2 schemas for optical and SAR evidence fusion."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    AOIGeometry,
    EvidenceItem,
    OverlayFeature,
)
from satquery.api.schemas.preparation import RasterProvenance
from satquery.api.schemas.providers import DataOrigin

FUSION_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"


class StrictFusionModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return value.astimezone(UTC)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SARBackscatterCoefficient(StrEnum):
    """SAR radiometric calibration conventions."""

    SIGMA0 = "sigma0"
    GAMMA0 = "gamma0"
    BETA0 = "beta0"
    UNKNOWN = "unknown"


class SARPowerUnit(StrEnum):
    """SAR numerical representation and units."""

    LINEAR_POWER = "linear_power"
    DECIBELS = "decibels"
    RAW_DN = "raw_dn"
    UNKNOWN = "unknown"


class SARPolarization(StrEnum):
    """SAR antenna transmit and receive polarizations."""

    VV = "VV"
    VH = "VH"
    HH = "HH"
    HV = "HV"


class SAROrbitDirection(StrEnum):
    """Satellite flight direction during acquisition."""

    ASCENDING = "ascending"
    DESCENDING = "descending"
    UNKNOWN = "unknown"


class SARCalibrationStatus(StrEnum):
    """Geometric and terrain radiometric correction level."""

    TERRAIN_CORRECTED = "terrain_corrected"
    CALIBRATED_ONLY = "calibrated_only"
    UNCALIBRATED = "uncalibrated"


class FusionCompatibilityStatus(StrEnum):
    """Multimodal compatibility assessment outcome."""

    VALID = "valid"
    COMPATIBLE_WITH_WARNINGS = "compatible_with_warnings"
    INCOMPATIBLE = "incompatible"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class JointObservationState(StrEnum):
    """Mutually exclusive observation status within the jointly observed area J."""

    BOTH_DETECT_CHANGE = "both_detect_change"
    OPTICAL_RESPONSE_ONLY = "optical_response_only"
    SAR_RESPONSE_ONLY = "sar_response_only"
    NEITHER_ABOVE_THRESHOLD = "neither_above_threshold"
    UNCERTAIN = "uncertain"


class CoveragePartitionCategory(StrEnum):
    """Coverage partitioning across the requested AOI."""

    JOINTLY_OBSERVABLE = "jointly_observable"
    OPTICAL_ONLY = "optical_only"
    SAR_ONLY = "sar_only"
    NEITHER = "neither"


class FusionRuleId(StrEnum):
    """Registered deterministic fusion rules."""

    CO_OBSERVED_RESPONSE_CHANGE = "co_observed_response_change"


# ---------------------------------------------------------------------------
# SAR Evidence Models
# ---------------------------------------------------------------------------


class SARThresholdConfig(StrictFusionModel):
    """Threshold settings for segmenting SAR backscatter change in dB."""

    increase_threshold_db: float = Field(
        default=2.0, ge=0.1, le=20.0, description="Positive backscatter delta cutoff (dB)"
    )
    decrease_threshold_db: float = Field(
        default=-2.0, ge=-20.0, le=-0.1, description="Negative backscatter delta cutoff (dB)"
    )
    min_cluster_size_pixels: int = Field(
        default=5,
        ge=1,
        le=1000,
        description="Minimum connected pixel cluster size for vectorization",
    )
    simplify_tolerance_meters: float = Field(
        default=5.0, ge=0.0, le=100.0, description="Geometric polygon simplification tolerance (m)"
    )

    @model_validator(mode="after")
    def validate_thresholds(self) -> Self:
        if self.increase_threshold_db <= self.decrease_threshold_db:
            raise ValueError(
                "increase_threshold_db must be strictly greater than decrease_threshold_db"
            )
        return self


class SARChangeEvidence(StrictFusionModel):
    """Calibrated SAR backscatter difference evidence."""

    evidence_id: str = Field(default_factory=lambda: f"sar-ev-{uuid4().hex[:8]}")
    before_scene_id: str
    after_scene_id: str
    before_asset_id: str
    after_asset_id: str
    difference_asset_id: str
    polarization: SARPolarization = SARPolarization.VV
    coefficient: SARBackscatterCoefficient = SARBackscatterCoefficient.SIGMA0
    unit: SARPowerUnit = SARPowerUnit.DECIBELS
    calibration_status: SARCalibrationStatus = SARCalibrationStatus.TERRAIN_CORRECTED
    orbit_direction: SAROrbitDirection = SAROrbitDirection.UNKNOWN
    before_timestamp: datetime
    after_timestamp: datetime
    increase_threshold_db: float
    decrease_threshold_db: float
    mean_delta_db: float
    min_delta_db: float
    max_delta_db: float
    std_delta_db: float
    valid_area_km2: float = Field(ge=0.0)
    data_origin: DataOrigin = DataOrigin.REAL
    warnings: list[str] = Field(default_factory=list)

    @field_validator("before_timestamp", "after_timestamp")
    @classmethod
    def normalize_dates(cls, value: datetime) -> datetime:
        return _as_utc(value, "timestamp")


# ---------------------------------------------------------------------------
# Temporal & Compatibility Models
# ---------------------------------------------------------------------------


class TemporalObservationRole(StrictFusionModel):
    """Observation metadata for one of the four temporal roles."""

    role: Literal["optical_before", "optical_after", "sar_before", "sar_after"]
    scene_id: str
    acquisition_timestamp: datetime
    prepared_asset_id: str
    sensor: str
    data_origin: DataOrigin = DataOrigin.REAL

    @field_validator("acquisition_timestamp")
    @classmethod
    def normalize_dates(cls, value: datetime) -> datetime:
        return _as_utc(value, "acquisition_timestamp")


class MultimodalTimingMetrics(StrictFusionModel):
    """Temporal relationship metrics between optical and SAR acquisitions."""

    optical_before_timestamp: datetime
    optical_after_timestamp: datetime
    sar_before_timestamp: datetime
    sar_after_timestamp: datetime
    optical_duration_days: float = Field(ge=0.0)
    sar_duration_days: float = Field(ge=0.0)
    before_offset_days: float = Field(
        description="Absolute difference between optical before and SAR before in days"
    )
    after_offset_days: float = Field(
        description="Absolute difference between optical after and SAR after in days"
    )
    event_timestamp: datetime | None = None
    event_bracketed_by_optical: bool | None = None
    event_bracketed_by_sar: bool | None = None
    interval_overlap_ratio: float = Field(
        ge=0.0, le=1.0, description="Jaccard overlap ratio between the two observation intervals"
    )

    @field_validator(
        "optical_before_timestamp",
        "optical_after_timestamp",
        "sar_before_timestamp",
        "sar_after_timestamp",
    )
    @classmethod
    def normalize_dates(cls, value: datetime) -> datetime:
        return _as_utc(value, "timestamp")

    @field_validator("event_timestamp")
    @classmethod
    def normalize_event_date(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "event_timestamp")


class CompatibilityAssessment(StrictFusionModel):
    """Scientific compatibility check between optical change and SAR change."""

    status: FusionCompatibilityStatus
    timing: MultimodalTimingMetrics | None = None
    optical_resolution_meters: float | None = None
    sar_resolution_meters: float | None = None
    common_crs: str | None = None
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    method_version: str = FUSION_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Coverage & Metrics Models
# ---------------------------------------------------------------------------


class CoveragePartitionPixelCounts(StrictFusionModel):
    """Pixel count accounting across coverage partitions."""

    total_aoi_pixels: int = Field(ge=0)
    jointly_observable_pixels: int = Field(ge=0)
    optical_only_pixels: int = Field(ge=0)
    sar_only_pixels: int = Field(ge=0)
    neither_pixels: int = Field(ge=0)


class CoveragePartitions(StrictFusionModel):
    """Partitioning of the AOI into mutually exclusive coverage zones."""

    total_aoi_area_km2: float = Field(ge=0.0)
    jointly_observable_area_km2: float = Field(ge=0.0)
    optical_only_area_km2: float = Field(ge=0.0)
    sar_only_area_km2: float = Field(ge=0.0)
    neither_area_km2: float = Field(ge=0.0)
    joint_percent_of_aoi: float = Field(ge=0.0, le=100.0)
    optical_only_percent_of_aoi: float = Field(ge=0.0, le=100.0)
    sar_only_percent_of_aoi: float = Field(ge=0.0, le=100.0)
    neither_percent_of_aoi: float = Field(ge=0.0, le=100.0)
    pixel_counts: CoveragePartitionPixelCounts


class JointStatePixelCounts(StrictFusionModel):
    """Pixel count accounting across the 5 mutually exclusive joint states."""

    both_detect_change_pixels: int = Field(ge=0)
    optical_response_only_pixels: int = Field(ge=0)
    sar_response_only_pixels: int = Field(ge=0)
    neither_above_threshold_pixels: int = Field(ge=0)
    uncertain_pixels: int = Field(ge=0)


class JointStateMetrics(StrictFusionModel):
    """Area and percentage breakdown within the jointly observable area J."""

    joint_area_km2: float = Field(ge=0.0)
    both_detect_change_area_km2: float = Field(ge=0.0)
    optical_response_only_area_km2: float = Field(ge=0.0)
    sar_response_only_area_km2: float = Field(ge=0.0)
    neither_above_threshold_area_km2: float = Field(ge=0.0)
    uncertain_area_km2: float = Field(ge=0.0)
    # Strictly calculated using joint_area_km2 as denominator; None if joint_area_km2 == 0.0
    both_detect_change_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    optical_response_only_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    sar_response_only_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    neither_above_threshold_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    uncertain_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    pixel_counts: JointStatePixelCounts


# ---------------------------------------------------------------------------
# Fusion Region & Quality Models
# ---------------------------------------------------------------------------


class FusionRegion(StrictFusionModel):
    """Vectorized polygon cluster representing a classified fused observation area."""

    id: str = Field(min_length=1, max_length=120)
    state: JointObservationState
    geometry: AOIGeometry
    area_km2: float = Field(ge=0.0)
    pixel_count: int = Field(ge=1)
    mean_optical_difference: float | None = None
    mean_sar_difference_db: float | None = None
    optical_evidence_id: str | None = None
    sar_evidence_id: str | None = None
    rule_explanation: str
    confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


class FusionQualityBreakdown(StrictFusionModel):
    """Traceable scientific quality factors for multimodal fusion."""

    score: float = Field(ge=0.0, le=1.0)
    temporal_alignment_factor: float = Field(ge=0.0, le=1.0)
    spatial_resolution_factor: float = Field(ge=0.0, le=1.0)
    calibration_certainty_factor: float = Field(ge=0.0, le=1.0)
    valid_coverage_factor: float = Field(ge=0.0, le=1.0)
    factors: dict[str, float] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class FusionRuleDefinition(StrictFusionModel):
    """Specification of an authoritative, versioned fusion rule."""

    rule_id: FusionRuleId
    name: str = Field(min_length=1, max_length=120)
    version: str = FUSION_SCHEMA_VERSION
    description: str = Field(min_length=1, max_length=500)
    supported_modalities: list[str] = Field(default_factory=lambda: ["Optical", "SAR"])
    disclaimer: str = Field(min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Requests and Responses
# ---------------------------------------------------------------------------


class FusionRequest(StrictFusionModel):
    """Request payload to perform optical and SAR evidence fusion."""

    request_id: str | None = None
    optical_change_result_id: str | None = Field(
        default=None, max_length=256, description="Result ID from Phase 4B optical change detection"
    )
    sar_prepared_pair_id: str | None = Field(
        default=None,
        max_length=256,
        description="Prepared pair ID from Phase 3B containing SAR rasters",
    )
    sar_before_asset_id: str | None = Field(
        default=None, max_length=256, description="Prepared SAR before asset ID"
    )
    sar_after_asset_id: str | None = Field(
        default=None, max_length=256, description="Prepared SAR after asset ID"
    )
    aoi: AOIGeometry
    rule_id: FusionRuleId = FusionRuleId.CO_OBSERVED_RESPONSE_CHANGE
    temporal_tolerance_days: float = Field(
        default=30.0,
        ge=1.0,
        le=365.0,
        description="Max acceptable offset between acquisition pairs (days)",
    )
    sar_threshold_config: SARThresholdConfig = Field(default_factory=SARThresholdConfig)
    event_timestamp: datetime | None = None
    allow_partial: bool = Field(
        default=True,
        description="Whether to return a single-modality result if SAR is absent or incompatible",
    )
    max_regions: int = Field(default=100, ge=1, le=500, description="Max vector regions to return")

    @field_validator("event_timestamp")
    @classmethod
    def normalize_event_date(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "event_timestamp")


class FusionResult(StrictFusionModel):
    """Complete envelope containing deterministic optical and SAR evidence fusion."""

    result_id: str = Field(min_length=1, max_length=120)
    rule_id: FusionRuleId
    rule_definition: FusionRuleDefinition
    compatibility: CompatibilityAssessment
    coverage: CoveragePartitions
    joint_metrics: JointStateMetrics
    regions: list[FusionRegion] = Field(default_factory=list)
    observations: list[TemporalObservationRole] = Field(default_factory=list)
    sar_evidence: SARChangeEvidence | None = None
    optical_change_result_id: str | None = None
    difference_overlay: OverlayFeature | None = None
    classified_overlay: OverlayFeature | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    quality: FusionQualityBreakdown
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
    provenance: RasterProvenance
    data_origin: DataOrigin = DataOrigin.REAL
    created_at: datetime
    interpretation_readiness: bool = False

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _as_utc(value, "created_at")


class FusionCapabilitiesResponse(StrictFusionModel):
    """Capabilities and supported rules for multimodal evidence fusion."""

    rules: list[FusionRuleDefinition]
    supported_polarizations: list[str] = Field(
        default_factory=lambda: [p.value for p in SARPolarization]
    )
    supported_coefficients: list[str] = Field(
        default_factory=lambda: [c.value for c in SARBackscatterCoefficient]
    )
    version: str = FUSION_SCHEMA_VERSION
