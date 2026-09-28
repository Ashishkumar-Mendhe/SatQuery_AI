"""Pydantic v2 schemas for raster harmonization, reprojection, and analysis preparation."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    AOIGeometry,
)
from satquery.api.schemas.imagery import (
    AlignmentStatus,
    ImageryFormat,
)
from satquery.api.schemas.providers import DataOrigin

PREPARATION_SCHEMA_VERSION: Literal["1.0"] = "1.0"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RasterPreparationMode(StrEnum):
    """Scope and modality of raster preparation."""

    SINGLE_SCENE = "single_scene"
    TEMPORAL_PAIR = "temporal_pair"
    OPTICAL_PAIR = "optical_pair"
    SAR_PAIR = "sar_pair"
    MULTIMODAL_INPUTS = "multimodal_inputs"


class TargetGridStrategy(StrEnum):
    """Strategy for determining common temporal spatial grid."""

    REFERENCE_BEFORE = "reference_before"
    REFERENCE_AFTER = "reference_after"
    HIGHEST_RESOLUTION = "highest_resolution"
    LOWEST_RESOLUTION = "lowest_resolution"
    CONFIGURED_RESOLUTION = "configured_resolution"
    COMMON_INTERSECTION = "common_intersection"


class ResamplingMethod(StrEnum):
    """Spatial interpolation algorithm for reprojection and resampling."""

    NEAREST = "nearest"
    BILINEAR = "bilinear"
    CUBIC = "cubic"
    AVERAGE = "average"


class PreparationStatus(StrEnum):
    """Execution status for raster harmonization pipeline."""

    QUEUED = "queued"
    INSPECTING_INPUTS = "inspecting_inputs"
    VALIDATING_INPUTS = "validating_inputs"
    CLIPPING = "clipping"
    REPROJECTING = "reprojecting"
    RESAMPLING = "resampling"
    ALIGNING = "aligning"
    APPLYING_MASKS = "applying_masks"
    VALIDATING_OUTPUTS = "validating_outputs"
    GENERATING_PREVIEWS = "generating_previews"
    READY = "ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class StrictPreparationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return value.astimezone(UTC)


class RasterQualityMetrics(StrictPreparationModel):
    """Scientific quality and consistency metrics of prepared rasters."""

    valid_data_percent: float = Field(ge=0.0, le=100.0)
    no_data_percent: float = Field(ge=0.0, le=100.0)
    aoi_coverage_percent: float = Field(ge=0.0, le=100.0)
    shared_coverage_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    resolution_consistency: float = Field(ge=0.0, le=1.0)
    grid_alignment_score: float = Field(ge=0.0, le=1.0)
    metadata_completeness: float = Field(ge=0.0, le=1.0)
    quality_score: float = Field(ge=0.0, le=1.0)
    factors: dict[str, float] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class RasterProvenance(StrictPreparationModel):
    """Immutable audit trail of spatial transformations applied to the raster."""

    pipeline_version: str = Field(default=PREPARATION_SCHEMA_VERSION)
    source_asset_ids: list[str] = Field(min_length=1)
    source_scene_ids: list[str] = Field(min_length=1)
    operations: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    software: str = Field(default="SatQuery Raster Harmonizer 1.0 (Rasterio/GDAL)")
    started_at: datetime
    completed_at: datetime
    duration_milliseconds: float = Field(ge=0.0)
    data_origin: DataOrigin = DataOrigin.REAL

    @field_validator("started_at", "completed_at")
    @classmethod
    def normalize_dates(cls, value: datetime) -> datetime:
        return _as_utc(value, "timestamp")


class RasterPreparationRequest(StrictPreparationModel):
    """Request payload to harmonise and reproject a single analysis raster."""

    request_id: str | None = None
    source_asset_id: str = Field(min_length=1, max_length=256)
    scene_id: str = Field(min_length=1, max_length=256)
    aoi: AOIGeometry
    target_crs: str | None = Field(default=None, max_length=64)
    target_resolution_meters: float | None = Field(default=None, ge=1.0, le=1000.0)
    resampling_method: ResamplingMethod = ResamplingMethod.BILINEAR
    selected_bands: list[str] = Field(default_factory=list)
    clip_to_aoi: bool = True
    mask_no_data: bool = True
    generate_preview: bool = True
    output_format: ImageryFormat = ImageryFormat.GEOTIFF
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_format(self) -> RasterPreparationRequest:
        if self.output_format not in {ImageryFormat.GEOTIFF, ImageryFormat.COG}:
            raise ValueError("Prepared analysis rasters must use geotiff or cog format")
        return self


class TemporalRasterPreparationRequest(StrictPreparationModel):
    """Request payload to harmonise, reproject, and grid-align a multitemporal pair."""

    request_id: str | None = None
    pair_id: str = Field(min_length=1, max_length=256)
    before_asset_id: str = Field(min_length=1, max_length=256)
    after_asset_id: str = Field(min_length=1, max_length=256)
    aoi: AOIGeometry
    strategy: TargetGridStrategy = TargetGridStrategy.COMMON_INTERSECTION
    target_crs: str | None = Field(default=None, max_length=64)
    target_resolution_meters: float | None = Field(default=None, ge=1.0, le=1000.0)
    optical_resampling_method: ResamplingMethod = ResamplingMethod.BILINEAR
    sar_resampling_method: ResamplingMethod = ResamplingMethod.BILINEAR
    mask_resampling_method: ResamplingMethod = ResamplingMethod.NEAREST
    use_common_intersection: bool = True
    selected_bands: list[str] = Field(default_factory=list)
    required_polarizations: list[str] = Field(default_factory=list)
    generate_previews: bool = True
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_distinct_assets(self) -> TemporalRasterPreparationRequest:
        if self.before_asset_id == self.after_asset_id:
            raise ValueError("before_asset_id and after_asset_id must be distinct")
        return self


class PreparedRasterAsset(StrictPreparationModel):
    """Descriptor of a prepared, georeferenced analysis-grade raster asset."""

    asset_id: str = Field(min_length=1, max_length=256)
    source_asset_ids: list[str] = Field(min_length=1)
    scene_ids: list[str] = Field(min_length=1)
    role: str = Field(default="single", max_length=64)
    format: ImageryFormat = ImageryFormat.GEOTIFF
    crs: str = Field(min_length=1, max_length=64)
    bbox: tuple[float, float, float, float]
    geometry: AOIGeometry | None = None
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    pixel_size_x: float = Field(gt=0)
    pixel_size_y: float = Field(gt=0)
    transform: list[float] = Field(min_length=6, max_length=9)
    band_count: int = Field(gt=0)
    band_names: list[str] = Field(default_factory=list)
    data_type: str = Field(min_length=1)
    no_data_values: list[float | None] = Field(default_factory=list)
    valid_pixel_count: int = Field(ge=0)
    invalid_pixel_count: int = Field(ge=0)
    valid_data_percent: float = Field(ge=0.0, le=100.0)
    resolution_meters: float = Field(gt=0)
    resampling_method: ResamplingMethod = ResamplingMethod.BILINEAR
    clip_applied: bool = True
    mask_applied: bool = True
    created_at: datetime
    expires_at: datetime | None = None
    data_origin: DataOrigin = DataOrigin.REAL
    provenance: RasterProvenance
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    preview_url: str | None = None
    metadata_url: str | None = None

    @field_validator("created_at", "expires_at")
    @classmethod
    def normalize_dates(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "datetime")


class PreparedTemporalPair(StrictPreparationModel):
    """Response payload containing harmonized, co-aligned before/after rasters."""

    preparation_id: str = Field(min_length=1)
    pair_id: str = Field(min_length=1)
    before_asset: PreparedRasterAsset
    after_asset: PreparedRasterAsset
    common_crs: str = Field(min_length=1, max_length=64)
    common_bbox: tuple[float, float, float, float]
    common_width: int = Field(gt=0)
    common_height: int = Field(gt=0)
    common_transform: list[float] = Field(min_length=6, max_length=9)
    common_resolution_meters: float = Field(gt=0)
    shared_valid_pixel_count: int = Field(ge=0)
    shared_valid_percent: float = Field(ge=0.0, le=100.0)
    alignment_status: AlignmentStatus = AlignmentStatus.ALIGNED
    quality: RasterQualityMetrics
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
    ready_for_analysis: bool = False
    created_at: datetime
    expires_at: datetime | None = None
    processing_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("created_at", "expires_at")
    @classmethod
    def normalize_dates(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "datetime")
