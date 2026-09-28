"""Pydantic v2 schemas for pixel-level change detection and change evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    AOIGeometry,
    ConfidenceBreakdown,
    EvidenceItem,
    OverlayFeature,
)
from satquery.api.schemas.preparation import (
    RasterProvenance,
)
from satquery.api.schemas.providers import DataOrigin
from satquery.api.schemas.spectral import MaskOptions

CHANGE_SCHEMA_VERSION = "1.0.0"


class StrictChangeModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return value.astimezone(UTC)


class ChangeDetectionMethod(StrEnum):
    """Supported pixel-level change detection algorithms."""

    NDVI_DIFFERENCE = "ndvi_difference"
    NDWI_DIFFERENCE = "ndwi_difference"
    NDBI_DIFFERENCE = "ndbi_difference"
    ABSOLUTE_INDEX_DIFFERENCE = "absolute_index_difference"
    MULTIBAND_CHANGE_MAGNITUDE = "multiband_change_magnitude"


class ThresholdStrategy(StrEnum):
    """Statistical and heuristic strategies for segmenting change."""

    FIXED = "fixed"
    STANDARD_DEVIATION = "standard_deviation"
    PERCENTILE = "percentile"
    OTSU = "otsu"
    MANUAL = "manual"


class ChangeDirectionality(StrEnum):
    """Polarity characteristics of a change calculation."""

    BIDIRECTIONAL = "bidirectional"
    MAGNITUDE_ONLY = "magnitude_only"


class ChangeThresholdConfig(StrictChangeModel):
    """Threshold settings and filtering parameters for change segmentation."""

    strategy: ThresholdStrategy = ThresholdStrategy.FIXED
    positive_threshold: float = Field(default=0.15, description="Gain cutoff threshold")
    negative_threshold: float = Field(default=-0.15, description="Loss cutoff threshold")
    std_multiplier: float = Field(
        default=1.5, ge=0.5, le=5.0, description="Multiplier k for mean +/- k*std"
    )
    percentile_cutoff: float = Field(
        default=95.0, ge=50.0, le=99.9, description="Upper percentile cutoff"
    )
    min_cluster_size_pixels: int = Field(
        default=5, ge=1, le=1000, description="Noise filter: minimum connected pixel cluster size"
    )
    simplify_tolerance_meters: float = Field(
        default=5.0, ge=0.0, le=100.0, description="Geometric simplification tolerance in meters"
    )

    @model_validator(mode="after")
    def validate_thresholds(self) -> Self:
        if self.strategy in {ThresholdStrategy.FIXED, ThresholdStrategy.MANUAL}:
            if self.positive_threshold < self.negative_threshold:
                raise ValueError(
                    "positive_threshold must be greater than or equal to negative_threshold"
                )
        return self


class ChangeDetectionDefinition(StrictChangeModel):
    """Authoritative metadata and mathematical specification for a change method."""

    method: ChangeDetectionMethod
    display_name: str = Field(min_length=1, max_length=120)
    formula: str = Field(min_length=1, max_length=256)
    input_type: str = Field(description="spectral_index or multiband_reflectance")
    directionality: ChangeDirectionality
    expected_range: tuple[float, float]
    default_threshold_config: ChangeThresholdConfig
    supported_sensors: list[str] = Field(
        default_factory=lambda: ["Sentinel-2", "Landsat-8", "Landsat-9"]
    )
    description: str = Field(min_length=1, max_length=500)
    limitations: str = Field(min_length=1, max_length=500)
    default_color_ramp: str = "RdYlGn"
    version: str = CHANGE_SCHEMA_VERSION


class ChangePixelCounts(StrictChangeModel):
    """Pixel count accounting over the co-registered grid."""

    total_aoi_pixels: int = Field(ge=0)
    shared_valid_pixels: int = Field(ge=0)
    gain_pixels: int = Field(ge=0)
    loss_pixels: int = Field(ge=0)
    stable_pixels: int = Field(ge=0)
    uncertain_pixels: int = Field(ge=0)
    gain_percent: float = Field(ge=0.0, le=100.0, description="% of shared valid pixels with gain")
    loss_percent: float = Field(ge=0.0, le=100.0, description="% of shared valid pixels with loss")
    stable_percent: float = Field(
        ge=0.0, le=100.0, description="% of shared valid pixels unchanged"
    )
    uncertain_percent: float = Field(
        ge=0.0, le=100.0, description="% of shared valid pixels uncertain"
    )


class ChangeMetrics(StrictChangeModel):
    """Spatial and statistical metrics of detected change."""

    gain_area_km2: float = Field(ge=0.0)
    loss_area_km2: float = Field(ge=0.0)
    stable_area_km2: float = Field(ge=0.0)
    net_change_area_km2: float = Field(description="gain_area - loss_area")
    shared_valid_area_km2: float = Field(ge=0.0)
    pixel_counts: ChangePixelCounts
    positive_threshold_applied: float
    negative_threshold_applied: float
    threshold_strategy: ThresholdStrategy


class ChangeRegion(StrictChangeModel):
    """Vectorized polygon cluster representing a candidate change area."""

    id: str = Field(min_length=1, max_length=120)
    category: str = Field(description="spectral_gain, spectral_loss, magnitude_high")
    geometry: AOIGeometry
    area_km2: float = Field(ge=0.0)
    pixel_count: int = Field(ge=1)
    mean_magnitude: float
    min_magnitude: float
    max_magnitude: float
    threshold_rule: str
    evidence_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


class ChangeDetectionRequest(StrictChangeModel):
    """Request payload to execute pixel-level change detection."""

    request_id: str | None = None
    prepared_pair_id: str = Field(min_length=1, max_length=256)
    before_prepared_asset_id: str = Field(min_length=1, max_length=256)
    after_prepared_asset_id: str = Field(min_length=1, max_length=256)
    aoi: AOIGeometry
    method: ChangeDetectionMethod = ChangeDetectionMethod.NDVI_DIFFERENCE
    threshold_config: ChangeThresholdConfig = Field(default_factory=ChangeThresholdConfig)
    mask_options: MaskOptions = Field(default_factory=MaskOptions)
    generate_overlay: bool = True
    generate_evidence: bool = True
    generate_regions: bool = True
    max_regions: int = Field(default=100, ge=1, le=500, description="Max vector regions to return")


class ChangeDetectionResult(StrictChangeModel):
    """Complete envelope for pixel-level change detection analysis."""

    result_id: str = Field(min_length=1, max_length=120)
    pair_id: str = Field(min_length=1, max_length=256)
    method: ChangeDetectionMethod
    definition: ChangeDetectionDefinition
    before_scene_id: str = Field(min_length=1, max_length=256)
    after_scene_id: str = Field(min_length=1, max_length=256)
    before_asset_id: str = Field(min_length=1, max_length=256)
    after_asset_id: str = Field(min_length=1, max_length=256)
    difference_asset_id: str = Field(min_length=1, max_length=256)
    preview_asset_id: str | None = None
    classified_preview_asset_id: str | None = None
    metrics: ChangeMetrics
    regions: list[ChangeRegion] = Field(default_factory=list)
    overlay: OverlayFeature | None = None
    classified_overlay: OverlayFeature | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    confidence_breakdown: ConfidenceBreakdown
    confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    provenance: RasterProvenance
    data_origin: DataOrigin = DataOrigin.REAL
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _as_utc(value, "created_at")


class ChangeMethodsResponse(StrictChangeModel):
    """Response payload listing all supported change detection methods."""

    methods: list[ChangeDetectionDefinition]
    total_count: int = Field(ge=0)
    version: str = CHANGE_SCHEMA_VERSION
