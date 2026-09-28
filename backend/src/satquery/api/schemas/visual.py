"""Pydantic schemas and enums for Phase 5B Image VQA and Verified Spatial Grounding."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    AOIGeometry,
)
from satquery.api.schemas.providers import DataOrigin, ProviderExecutionMetadata
from satquery.api.schemas.query import GenerationMode, WorkspaceContextSnapshot


class StrictVisualModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ImageInputRole(StrEnum):
    """Role of an image within a visual query context."""

    SINGLE = "single"
    BEFORE = "before"
    AFTER = "after"
    COMPOSITE = "composite"


class ObservationSource(StrEnum):
    """Source of a visual observation."""

    MODEL_PREDICTION = "model_prediction"
    COMPUTED_EVIDENCE = "computed_evidence"


class CoordinateStatus(StrEnum):
    """Validation status of an image-space bounding box."""

    VALID = "valid"
    INVALID_PADDING_ONLY = "invalid_padding_only"
    PARTIAL_CLAMPED = "partial_clamped"
    OUT_OF_BOUNDS = "out_of_bounds"
    UNAVAILABLE = "unavailable"


class SemanticStatus(StrEnum):
    """Verification status of a model visual interpretation."""

    UNVERIFIED_PREDICTION = "unverified_prediction"
    EVIDENCE_SUPPORTED = "evidence_supported"
    EVIDENCE_CONFLICTED = "evidence_conflicted"
    INDEPENDENTLY_REVIEWED = "independently_reviewed"


class MapGroundingStatus(StrEnum):
    """Geographic placement feasibility of a visual observation."""

    AVAILABLE = "available"
    IMAGE_ONLY_NO_GEOREFERENCE = "image_only_no_georeference"
    UNAVAILABLE_OUT_OF_BOUNDS = "unavailable_out_of_bounds"


class VisualOperation(StrEnum):
    """Requested visual analysis operation."""

    DESCRIBE = "describe"
    LOCATE = "locate"
    COMPARE = "compare"


# ---------------------------------------------------------------------------
# Image Manifest & Spatial Transformation Models
# ---------------------------------------------------------------------------


class ImageManifest(StrictVisualModel):
    """Immutable record of the exact image bytes, dimensions, and georeferencing sent to the model."""

    manifest_id: str = Field(description="Unique manifest identifier")
    input_image_id: str = Field(description="Opaque ID assigned to this input image")
    source_scene_id: str = Field(description="Original satellite scene identifier")
    source_asset_id: str = Field(description="Asset store ID of the backing raster/preview")
    role: ImageInputRole = Field(default=ImageInputRole.SINGLE, description="Role of this image")
    content_hash: str = Field(description="SHA-256 digest of the submitted image bytes")
    submitted_width: int = Field(gt=0, description="Width of the submitted image in pixels")
    submitted_height: int = Field(gt=0, description="Height of the submitted image in pixels")
    content_rectangle: tuple[int, int, int, int] = Field(
        description="Content rectangle [x, y, width, height] excluding outer padding"
    )
    rendering_type: str = Field(
        default="true_color",
        description="Rendering style (true_color, false_color, sar_grayscale, overlay)",
    )
    crs: str | None = Field(
        default=None, description="Coordinate Reference System (e.g. EPSG:32644)"
    )
    affine_transform: list[float] | None = Field(
        default=None,
        description="6-element Affine transform [a, b, c, d, e, f] in pixel-edge coordinates",
    )
    crop_window: tuple[int, int, int, int] | None = Field(
        default=None,
        description="Source raster crop window [col_offset, row_offset, width, height]",
    )
    resize_dimensions: tuple[int, int] | None = Field(
        default=None,
        description="Dimensions [width, height] after resizing crop before padding",
    )
    padding: tuple[int, int, int, int] | None = Field(
        default=None,
        description="Padding added around content [left, top, right, bottom]",
    )
    data_origin: DataOrigin = Field(
        default=DataOrigin.REAL, description="Data origin (real, mock, fallback)"
    )
    acquisition_time: datetime | None = Field(
        default=None, description="Exact UTC acquisition timestamp"
    )
    provider: str | None = Field(default="earth-search", description="Data provider identifier")
    collection: str | None = Field(
        default="sentinel-2-l2a", description="STAC collection identifier"
    )
    platform: str | None = Field(default="Sentinel-2", description="Platform / satellite name")
    sensor: str | None = Field(default="MSI", description="Sensor / instrument name")
    media_type: str = Field(default="image/png", description="Submitted image media type")
    scene_bbox: tuple[float, float, float, float] | None = Field(
        default=None, description="Scene bounding box [min_lon, min_lat, max_lon, max_lat]"
    )
    aoi_id: str | None = Field(default=None, description="Associated AOI identifier")
    aoi_revision: int | None = Field(default=None, description="Associated AOI revision number")
    aoi_fingerprint: str | None = Field(
        default=None, description="AOI context fingerprint / geometry hash at submission time"
    )
    crop_bounds: tuple[float, float, float, float] | None = Field(
        default=None, description="Requested crop/render bounding box in WGS84"
    )
    resolution_meters: float | None = Field(
        default=10.0, description="Spatial resolution of the crop in meters"
    )
    preview_type: str = Field(
        default="aoi_crop",
        description="Preview type (aoi_crop, full_scene_thumbnail, analysis_raster)",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Manifest creation timestamp"
    )


class GroundedVisualRegion(StrictVisualModel):
    """Geographically placed region derived from an image-space prediction."""

    region_id: str = Field(description="Unique region identifier")
    observation_id: str = Field(description="Backing observation ID")
    manifest_id: str = Field(description="Source image manifest ID")
    source_image_box: list[float] = Field(
        description="Canonical [xmin, ymin, xmax, ymax] normalized in 0..1"
    )
    wgs84_geometry: AOIGeometry | None = Field(
        default=None, description="WGS84 GeoJSON polygon of the grounded region"
    )
    bbox_wgs84: tuple[float, float, float, float] | None = Field(
        default=None, description="[min_lon, min_lat, max_lon, max_lat] in WGS84"
    )
    projected_bbox: tuple[float, float, float, float] | None = Field(
        default=None, description="[west, south, east, north] in native projected CRS units"
    )
    transform_provenance: str = Field(
        description="Description of mathematical transformation chain applied"
    )
    clipping_status: CoordinateStatus = Field(
        default=CoordinateStatus.VALID, description="Clipping/padding status"
    )
    matched_evidence_ids: list[str] = Field(
        default_factory=list, description="IDs of overlapping computed change/fusion evidence"
    )
    overlap_area_km2: float | None = Field(
        default=None, description="Area in km2 of overlap with existing evidence"
    )
    limitations: list[str] = Field(
        default_factory=list, description="Analytical and geometric limitations"
    )


class VisualObservation(StrictVisualModel):
    """Structured visual observation proposed by the vision model or extracted from evidence."""

    observation_id: str = Field(description="Unique observation identifier")
    input_image_id: str = Field(description="Target input image ID this observation refers to")
    role: ImageInputRole = Field(
        default=ImageInputRole.SINGLE, description="Image role (single, before, after)"
    )
    label: str = Field(description="Short descriptive label (e.g. 'Dense Vegetation Cluster')")
    description: str = Field(description="Detailed visual description of visible appearance")
    canonical_box: list[float] | None = Field(
        default=None,
        description="Canonical [xmin, ymin, xmax, ymax] normalized to 0.0..1.0, top-left origin",
    )
    observation_source: ObservationSource = Field(
        default=ObservationSource.MODEL_PREDICTION,
        description="Source of this observation (model prediction vs computed evidence)",
    )
    coordinate_status: CoordinateStatus = Field(
        default=CoordinateStatus.VALID, description="Bounding box validation status"
    )
    semantic_status: SemanticStatus = Field(
        default=SemanticStatus.UNVERIFIED_PREDICTION,
        description="Semantic verification status (predictions remain unverified by default)",
    )
    map_grounding_status: MapGroundingStatus = Field(
        default=MapGroundingStatus.AVAILABLE,
        description="Feasibility of placing this observation on the map",
    )
    model_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Optional uncalibrated model score"
    )
    associated_evidence_ids: list[str] = Field(
        default_factory=list, description="Referenced computed evidence IDs"
    )
    warnings: list[AnalysisWarning] = Field(
        default_factory=list, description="Data quality or resolution warnings"
    )


# ---------------------------------------------------------------------------
# Visual Query Request & Response Envelopes
# ---------------------------------------------------------------------------


class VisualQueryRequest(StrictVisualModel):
    """Request payload sent to POST /api/v1/query/visual."""

    question: str = Field(
        min_length=3,
        max_length=1000,
        description="Natural language question referring to the selected image(s)",
    )
    workspace_id: str | None = Field(default=None, description="Active workspace identifier")
    context_snapshot: WorkspaceContextSnapshot = Field(
        description="Current workspace snapshot and context references"
    )
    selected_image_asset_ids: list[str] = Field(
        min_length=1,
        max_length=2,
        description="Asset IDs of selected image(s) to inspect (1 for single, 2 for temporal pair)",
    )
    operation: VisualOperation = Field(
        default=VisualOperation.DESCRIBE,
        description="Requested visual operation (describe, locate, compare)",
    )
    existing_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Optional list of computed evidence IDs to cross-reference",
    )
    locale: str | None = Field(default="en", description="Preferred response locale")
    request_id: str | None = Field(default=None, description="Correlation request ID")


class VisualQueryResponse(StrictVisualModel):
    """Structured response containing visual observations, manifests, and map groundings."""

    answer_id: str = Field(description="Unique visual answer identifier")
    request_id: str = Field(description="Correlation request ID")
    context_fingerprint: str = Field(description="Matching workspace context fingerprint")
    answer: str = Field(description="Natural language synthesis answering the question")
    observations: list[VisualObservation] = Field(
        default_factory=list, description="List of structured visual observations"
    )
    manifests: list[ImageManifest] = Field(
        default_factory=list, description="Immutable manifests for all submitted images"
    )
    grounded_regions: list[GroundedVisualRegion] = Field(
        default_factory=list, description="Geographically grounded regions for map overlay"
    )
    evidence_references: list[str] = Field(
        default_factory=list, description="IDs of cross-referenced computed evidence"
    )
    generation_mode: GenerationMode = Field(
        default=GenerationMode.LLM_EXPLANATION, description="Generation mode used"
    )
    data_origin: DataOrigin = Field(
        default=DataOrigin.REAL, description="Data origin of the underlying imagery"
    )
    warnings: list[AnalysisWarning] = Field(
        default_factory=list, description="Quality, atmospheric, or resolution warnings"
    )
    limitations: list[str] = Field(
        default_factory=list, description="Analytical and semantic limitations"
    )
    provider_execution: ProviderExecutionMetadata | None = Field(
        default=None, description="AI provider metadata if live model was invoked"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Creation timestamp"
    )


class VisualCapabilitiesResponse(StrictVisualModel):
    """Capabilities of the visual question answering and spatial grounding subsystem."""

    supported_operations: list[VisualOperation] = Field(description="Supported visual operations")
    supports_bounding_boxes: bool = Field(
        default=True, description="Whether bounding box localization is supported"
    )
    supports_temporal_comparison: bool = Field(
        default=True, description="Whether bi-temporal multi-image VQA is supported"
    )
    max_images_per_query: int = Field(default=2, description="Maximum images per query")
    example_questions: list[str] = Field(description="Curated example visual questions")
