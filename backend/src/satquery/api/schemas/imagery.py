"""Pydantic v2 schemas for satellite imagery retrieval, map previews, and analysis rasters."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    AOIGeometry,
)
from satquery.api.schemas.providers import DataOrigin

IMAGERY_SCHEMA_VERSION: Literal["1.0"] = "1.0"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ImageryProductType(StrEnum):
    """Classification of the requested imagery product."""

    CATALOGUE_THUMBNAIL = "catalogue_thumbnail"
    MAP_PREVIEW = "map_preview"
    ANALYSIS_RASTER = "analysis_raster"


class VisualizationPreset(StrEnum):
    """Server-controlled visualization color composite presets."""

    TRUE_COLOR = "true_color"
    FALSE_COLOR = "false_color"
    VEGETATION = "vegetation"
    WATER = "water"
    URBAN = "urban"
    SAR_GRAYSCALE = "sar_grayscale"
    SAR_VV = "sar_vv"
    SAR_VH = "sar_vh"


class ImageryFormat(StrEnum):
    """Output raster and image format."""

    PNG = "png"
    JPEG = "jpeg"
    GEOTIFF = "geotiff"
    COG = "cog"


class ImageryJobStatus(StrEnum):
    """Lifecycle state of an imagery retrieval job."""

    QUEUED = "queued"
    VALIDATING = "validating"
    AUTHENTICATING = "authenticating"
    REQUESTING_PROVIDER = "requesting_provider"
    DOWNLOADING = "downloading"
    VALIDATING_RASTER = "validating_raster"
    PREPARING_PREVIEW = "preparing_preview"
    READY = "ready"
    PARTIALLY_READY = "partially_ready"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AlignmentStatus(StrEnum):
    """Multitemporal spatial grid and CRS alignment classification."""

    ALIGNED = "aligned"
    APPROXIMATELY_ALIGNED = "approximately_aligned"
    REQUIRES_ALIGNMENT = "requires_alignment"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Core Schema Models
# ---------------------------------------------------------------------------


class StrictImageryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return value.astimezone(UTC)


class RasterMetadata(StrictImageryModel):
    """Geospatial and technical metadata of a retrieved raster asset."""

    crs: str = Field(min_length=1, max_length=64)
    bbox: tuple[float, float, float, float]
    width: int = Field(gt=0, le=8192)
    height: int = Field(gt=0, le=8192)
    pixel_size_x: float = Field(gt=0)
    pixel_size_y: float = Field(gt=0)
    band_count: int = Field(gt=0, le=32)
    band_names: list[str] = Field(default_factory=list)
    data_type: str = Field(min_length=1, max_length=32)
    no_data_values: list[float | None] = Field(default_factory=list)
    acquisition_time: datetime | None = None
    scene_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    collection: str = Field(min_length=1)
    processing_level: str | None = None
    transform: list[float] | None = None
    statistics: dict[str, Any] | None = None

    @field_validator("acquisition_time")
    @classmethod
    def normalize_acquisition(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "acquisition_time")


class ImageryRequest(StrictImageryModel):
    """Request parameters for single scene imagery retrieval."""

    scene_id: str = Field(min_length=1, max_length=256)
    aoi: AOIGeometry
    product_type: ImageryProductType = ImageryProductType.MAP_PREVIEW
    visualization_preset: VisualizationPreset = VisualizationPreset.TRUE_COLOR
    output_format: ImageryFormat = ImageryFormat.PNG
    width: int | None = Field(default=None, gt=0, le=4096)
    height: int | None = Field(default=None, gt=0, le=4096)
    resolution_meters: float | None = Field(default=None, ge=1.0, le=1000.0)
    bands: list[str] | None = None
    polarizations: list[str] | None = None
    resampling_method: Literal["nearest", "bilinear", "cubic", "lanczos"] = "bilinear"
    map_projection: str = "EPSG:3857"
    include_metadata: bool = True
    request_id: str | None = None

    @model_validator(mode="after")
    def validate_preset_and_format(self) -> ImageryRequest:
        if self.product_type == ImageryProductType.ANALYSIS_RASTER:
            if self.output_format in {ImageryFormat.PNG, ImageryFormat.JPEG}:
                raise ValueError("analysis_raster product type requires geotiff or cog format")
        return self


class TemporalImageryRequest(StrictImageryModel):
    """Request parameters for multitemporal before/after imagery retrieval."""

    before_scene_id: str = Field(min_length=1, max_length=256)
    after_scene_id: str = Field(min_length=1, max_length=256)
    aoi: AOIGeometry
    product_type: ImageryProductType = ImageryProductType.MAP_PREVIEW
    before_preset: VisualizationPreset = VisualizationPreset.TRUE_COLOR
    after_preset: VisualizationPreset = VisualizationPreset.TRUE_COLOR
    output_format: ImageryFormat = ImageryFormat.PNG
    width: int | None = Field(default=None, gt=0, le=4096)
    height: int | None = Field(default=None, gt=0, le=4096)
    resolution_meters: float | None = Field(default=None, ge=1.0, le=1000.0)
    align_outputs: bool = True
    include_metadata: bool = True
    request_id: str | None = None

    @model_validator(mode="after")
    def validate_distinct_scenes(self) -> TemporalImageryRequest:
        if self.before_scene_id == self.after_scene_id:
            raise ValueError("before_scene_id and after_scene_id must be distinct")
        return self


class ImageryAsset(StrictImageryModel):
    """Normalized descriptor of a generated or retrieved imagery asset."""

    asset_id: str = Field(min_length=1, max_length=256)
    scene_id: str = Field(min_length=1, max_length=256)
    product_type: ImageryProductType
    format: ImageryFormat
    content_type: str = Field(min_length=1, max_length=64)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    resolution_meters: float = Field(gt=0)
    bbox: tuple[float, float, float, float]
    geometry: AOIGeometry | None = None
    crs: str = Field(min_length=1, max_length=64)
    bands: list[str] = Field(default_factory=list)
    size_bytes: int = Field(ge=0)
    checksum: str = Field(min_length=1, max_length=128)
    created_at: datetime
    expires_at: datetime | None = None
    data_origin: DataOrigin = DataOrigin.REAL
    provider_id: str = Field(min_length=1)
    visualization_preset: VisualizationPreset | None = None
    display_url: str = Field(min_length=1)
    metadata_url: str | None = None
    download_url: str | None = None
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    processing_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("created_at", "expires_at")
    @classmethod
    def normalize_dates(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "datetime")


class TemporalImageryResponse(StrictImageryModel):
    """Normalized response payload for before/after temporal imagery retrieval."""

    request_id: str = Field(min_length=1)
    pair_id: str = Field(min_length=1)
    before_asset: ImageryAsset
    after_asset: ImageryAsset
    alignment_status: AlignmentStatus
    data_origin: DataOrigin = DataOrigin.REAL
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    processing_metadata: dict[str, Any] = Field(default_factory=dict)
