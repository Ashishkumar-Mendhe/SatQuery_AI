"""Pydantic v2 schemas for SatQuery AI spectral index contracts.

Defines schemas for index definitions, calculation requests, statistical summaries,
traceable evidence items, map overlays, and temporal spectral comparisons.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    AOIGeometry,
    ConfidenceBreakdown,
    EvidenceProvenance,
    OverlayFeature,
    _as_utc,
)
from satquery.api.schemas.preparation import (
    RasterProvenance,
)
from satquery.api.schemas.providers import DataOrigin

SPECTRAL_SCHEMA_VERSION: Literal["1.0"] = "1.0"


class StrictSpectralModel(BaseModel):
    """Base model enforcing strict type validation and zero extra fields."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SpectralIndexName(StrEnum):
    """Supported spectral index identifiers."""

    NDVI = "ndvi"
    NDWI = "ndwi"
    NDBI = "ndbi"
    EVI = "evi"
    SAVI = "savi"
    MNDWI = "mndwi"


class SpectralProcessingStatus(StrEnum):
    """Execution status for spectral index computation."""

    QUEUED = "queued"
    VALIDATING = "validating"
    LOADING_BANDS = "loading_bands"
    APPLYING_SCALE = "applying_scale"
    APPLYING_MASKS = "applying_masks"
    CALCULATING_INDEX = "calculating_index"
    CALCULATING_STATISTICS = "calculating_statistics"
    GENERATING_REGIONS = "generating_regions"
    GENERATING_OVERLAY = "generating_overlay"
    VALIDATING_OUTPUT = "validating_output"
    READY = "ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Index Definition & Registry Schemas
# ---------------------------------------------------------------------------


class SpectralIndexDefinition(StrictSpectralModel):
    """Formal scientific metadata for a registered spectral index."""

    name: SpectralIndexName
    display_name: str = Field(min_length=1, max_length=120)
    formula: str = Field(min_length=1, max_length=256)
    required_bands: list[str] = Field(min_length=2, max_length=6)
    expected_range: tuple[float, float] = Field(default=(-1.0, 1.0))
    description: str = Field(min_length=1, max_length=500)
    limitations: str = Field(min_length=1, max_length=500)
    default_color_ramp: str = Field(default="viridis", max_length=64)
    version: str = Field(default="1.0.0", max_length=32)


class SpectralIndicesResponse(StrictSpectralModel):
    """List of all registered and supported spectral index definitions."""

    indices: list[SpectralIndexDefinition]
    total_count: int = Field(ge=0)
    version: str = Field(default=SPECTRAL_SCHEMA_VERSION)


# ---------------------------------------------------------------------------
# Options & Request Schemas
# ---------------------------------------------------------------------------


class MaskOptions(StrictSpectralModel):
    """Masking options for spectral computation."""

    apply_no_data_mask: bool = True
    apply_cloud_mask: bool = True
    apply_quality_mask: bool = True
    include_shadow_mask: bool = False
    minimum_valid_data_percent: float = Field(default=1.0, ge=0.0, le=100.0)
    custom_mask_asset_id: str | None = Field(default=None, max_length=120)


class StatisticsOptions(StrictSpectralModel):
    """Statistical calculation configuration."""

    calculate_minimum: bool = True
    calculate_maximum: bool = True
    calculate_mean: bool = True
    calculate_median: bool = True
    calculate_standard_deviation: bool = True
    calculate_percentiles: bool = True
    percentiles: list[float] = Field(
        default_factory=lambda: [10.0, 25.0, 50.0, 75.0, 90.0],
        max_length=20,
    )
    calculate_histogram: bool = True
    histogram_bins: int = Field(default=20, ge=5, le=100)
    calculate_valid_pixel_count: bool = True

    @field_validator("percentiles")
    @classmethod
    def validate_percentiles(cls, value: list[float]) -> list[float]:
        for p in value:
            if not 0.0 <= p <= 100.0:
                raise ValueError(f"Percentile {p} must be between 0.0 and 100.0")
        return sorted(list(set(value)))


class SpectralHistogram(StrictSpectralModel):
    """Binned distribution of spectral index values."""

    bin_edges: list[float]
    counts: list[int]
    total_samples: int = Field(ge=0)


class SpectralIndexStatistics(StrictSpectralModel):
    """Measured quantitative statistics over valid AOI pixels."""

    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    median: float | None = None
    standard_deviation: float | None = Field(default=None, ge=0.0)
    percentiles: dict[str, float] = Field(default_factory=dict)
    histogram: SpectralHistogram | None = None
    valid_pixel_count: int = Field(ge=0)
    invalid_pixel_count: int = Field(ge=0)
    masked_pixel_count: int = Field(default=0, ge=0)
    valid_data_percent: float = Field(ge=0.0, le=100.0)
    units: str = Field(default="normalized_index", max_length=64)
    calculation_scope: str = Field(default="exact_aoi_polygon", max_length=120)


class SpectralIndexRequest(StrictSpectralModel):
    """Request payload to compute a spectral index over a prepared raster."""

    request_id: str | None = Field(default=None, max_length=120)
    prepared_asset_id: str = Field(min_length=1, max_length=120)
    scene_id: str = Field(min_length=1, max_length=512)
    aoi: AOIGeometry
    index_name: SpectralIndexName
    mask_options: MaskOptions = Field(default_factory=MaskOptions)
    statistics_options: StatisticsOptions = Field(default_factory=StatisticsOptions)
    generate_overlay: bool = True
    generate_evidence: bool = True
    output_format: str = Field(default="geotiff", max_length=32)
    processing_version: str = Field(default="1.0.0", max_length=32)


class TemporalSpectralRequest(StrictSpectralModel):
    """Request payload to compute a spectral index over a prepared bi-temporal pair."""

    request_id: str | None = Field(default=None, max_length=120)
    prepared_pair_id: str = Field(min_length=1, max_length=120)
    before_prepared_asset_id: str = Field(min_length=1, max_length=120)
    after_prepared_asset_id: str = Field(min_length=1, max_length=120)
    aoi: AOIGeometry
    index_name: SpectralIndexName
    mask_options: MaskOptions = Field(default_factory=MaskOptions)
    statistics_options: StatisticsOptions = Field(default_factory=StatisticsOptions)
    generate_overlays: bool = True
    generate_evidence: bool = True


# ---------------------------------------------------------------------------
# Output & Evidence Schemas
# ---------------------------------------------------------------------------


class SpectralEvidenceItem(StrictSpectralModel):
    """Atomic piece of measured spectral evidence for downstream AI and audit."""

    id: str = Field(min_length=1, max_length=120)
    type: Literal["spectral_measurement"] = "spectral_measurement"
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    index_name: SpectralIndexName
    measured_statistics: SpectralIndexStatistics
    source_scene_ids: list[str] = Field(min_length=1)
    source_asset_ids: list[str] = Field(min_length=1)
    geometry: AOIGeometry | None = None
    result_asset_id: str = Field(min_length=1, max_length=120)
    observed_at: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: EvidenceProvenance
    limitations: list[str] = Field(default_factory=list)
    data_origin: DataOrigin = DataOrigin.REAL

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "observed_at")


class SpectralRegion(StrictSpectralModel):
    """Optional thresholded screening region polygon."""

    id: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=64)
    geometry: AOIGeometry
    area_square_km: float = Field(ge=0.0)
    pixel_count: int = Field(ge=1)
    mean_value: float
    minimum_value: float
    maximum_value: float
    threshold_rule: str = Field(min_length=1, max_length=256)
    evidence_id: str = Field(min_length=1, max_length=120)
    confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[AnalysisWarning] = Field(default_factory=list)


class SpectralIndexResult(StrictSpectralModel):
    """Complete calculation result for a single scene spectral index."""

    result_id: str = Field(min_length=1, max_length=120)
    index_name: SpectralIndexName
    definition: SpectralIndexDefinition
    scene_id: str = Field(min_length=1, max_length=512)
    prepared_asset_id: str = Field(min_length=1, max_length=120)
    source_asset_ids: list[str] = Field(default_factory=list)
    aoi_fingerprint: str = Field(min_length=1, max_length=120)
    output_asset_id: str = Field(min_length=1, max_length=120)
    preview_asset_id: str | None = Field(default=None, max_length=120)
    preview_url: str | None = None
    overlay: OverlayFeature | None = None
    statistics: SpectralIndexStatistics
    observed_range: tuple[float, float]
    valid_data_percent: float = Field(ge=0.0, le=100.0)
    evidence: list[SpectralEvidenceItem] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: ConfidenceBreakdown
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    provenance: RasterProvenance
    data_origin: DataOrigin = DataOrigin.REAL
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _as_utc(value, "created_at")


class TemporalSpectralResult(StrictSpectralModel):
    """Side-by-side spectral calculation result for a prepared before/after pair."""

    result_id: str = Field(min_length=1, max_length=120)
    pair_id: str = Field(min_length=1, max_length=120)
    index_name: SpectralIndexName
    definition: SpectralIndexDefinition
    before_result: SpectralIndexResult
    after_result: SpectralIndexResult
    comparability_warnings: list[AnalysisWarning] = Field(default_factory=list)
    shared_valid_percent: float = Field(ge=0.0, le=100.0)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _as_utc(value, "created_at")
