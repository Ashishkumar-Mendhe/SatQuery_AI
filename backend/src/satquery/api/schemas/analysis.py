"""Pydantic v2 schemas for SatQuery AI multimodal analysis contracts.

Defines schemas for AOIs, scenes, spectral measurements, change detection,
findings, evidence, overlays, confidence breakdown, warnings, and responses.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite
from typing import Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

ANALYSIS_SCHEMA_VERSION: Literal["1.0"] = "1.0"
MAX_QUESTION_LENGTH = 1000
MIN_QUESTION_LENGTH = 3
MAX_AOI_POSITIONS = 500


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AnalysisMode(StrEnum):
    VISUAL_QUESTION_ANSWERING = "visual_question_answering"
    SPATIAL_GROUNDING = "spatial_grounding"
    CHANGE_DETECTION = "change_detection"
    SPECTRAL_ANALYSIS = "spectral_analysis"
    MULTIMODAL_ANALYSIS = "multimodal_analysis"
    # Domain specific aliases
    VEGETATION_HEALTH = "vegetation_health"
    WATER_BODY_MONITORING = "water_body_monitoring"


class AnalysisJobStatus(StrEnum):
    QUEUED = "queued"
    VALIDATING = "validating"
    DISCOVERING_IMAGERY = "discovering_imagery"
    DOWNLOADING_IMAGERY = "downloading_imagery"
    PREPROCESSING = "preprocessing"
    ANALYZING = "analyzing"
    GENERATING_OVERLAYS = "generating_overlays"
    GENERATING_REPORT = "generating_report"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"  # Alias for completed


class ImageryProvider(StrEnum):
    EARTH_SEARCH = "earth-search"
    SENTINEL_HUB = "sentinel_hub"
    COPERNICUS_DATASPACE = "copernicus_dataspace"
    PLANETARY_COMPUTER = "planetary_computer"
    LOCAL_UPLOAD = "local_upload"
    MOCK = "mock"


class SensorType(StrEnum):
    OPTICAL = "optical"
    SAR = "sar"
    MULTISPECTRAL = "multispectral"
    UNKNOWN = "unknown"


class GeometryType(StrEnum):
    POINT = "Point"
    POLYGON = "Polygon"
    MULTI_POLYGON = "MultiPolygon"


class OverlayType(StrEnum):
    POINT = "point"
    POLYGON = "polygon"
    BOUNDING_BOX = "bounding_box"
    HEATMAP = "heatmap"
    RASTER = "raster"
    MASK = "mask"


class EvidenceType(StrEnum):
    SOURCE_SCENE = "source_scene"
    SPECTRAL_MEASUREMENT = "spectral_measurement"
    CHANGE_MEASUREMENT = "change_measurement"
    DETECTED_REGION = "detected_region"
    MODEL_OBSERVATION = "model_observation"
    USER_INPUT = "user_input"


class WarningSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingSeverity(StrEnum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReportFormat(StrEnum):
    PDF = "pdf"
    JSON = "json"
    MARKDOWN = "markdown"


class APIErrorCode(StrEnum):
    INVALID_AOI = "INVALID_AOI"
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
    AOI_TOO_LARGE = "AOI_TOO_LARGE"
    NO_SCENES_FOUND = "NO_SCENES_FOUND"
    HIGH_CLOUD_COVER = "HIGH_CLOUD_COVER"
    LOW_IMAGE_QUALITY = "LOW_IMAGE_QUALITY"
    TEMPORAL_GAP_TOO_LARGE = "TEMPORAL_GAP_TOO_LARGE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    UNSUPPORTED_ANALYSIS_MODE = "UNSUPPORTED_ANALYSIS_MODE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RESOLUTION_LIMIT_WARNING = "RESOLUTION_LIMIT_WARNING"
    VALIDATION_FAILED = "VALIDATION_FAILED"


class WarningCode(StrEnum):
    HIGH_CLOUD_COVER = "HIGH_CLOUD_COVER"
    LOW_IMAGE_QUALITY = "LOW_IMAGE_QUALITY"
    TEMPORAL_GAP_TOO_LARGE = "TEMPORAL_GAP_TOO_LARGE"
    RESOLUTION_LIMIT_WARNING = "RESOLUTION_LIMIT_WARNING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNGEIGER_REFERENCED_IMAGE = "UNGEIGER_REFERENCED_IMAGE"
    MOCK_DATA_USED = "MOCK_DATA_USED"
    PARTIAL_COVERAGE = "PARTIAL_COVERAGE"


# ---------------------------------------------------------------------------
# Base Models & Helpers
# ---------------------------------------------------------------------------


class StrictAnalysisModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return value.astimezone(UTC)


def _validate_position(pos: tuple[float, float]) -> None:
    lon, lat = pos
    if not (isfinite(lon) and isfinite(lat)):
        raise ValueError("coordinates must contain finite numbers")
    if not -180 <= lon <= 180:
        raise ValueError(f"longitude {lon} must be between -180 and 180")
    if not -90 <= lat <= 90:
        raise ValueError(f"latitude {lat} must be between -90 and 90")


# ---------------------------------------------------------------------------
# Core Geometric & Spatial Schemas
# ---------------------------------------------------------------------------

type CoordinatePair = tuple[float, float]
type BoundingBox = tuple[float, float, float, float]


class AOIGeometry(StrictAnalysisModel):
    """Represents a validated GeoJSON geometry for the Area of Interest."""

    type: GeometryType
    coordinates: Any = Field(description="GeoJSON coordinates array in [longitude, latitude] order")
    bbox: BoundingBox | None = Field(
        default=None, description="Optional bounding box [minX, minY, maxX, maxY]"
    )
    crs: str = Field(default="EPSG:4326", description="Coordinate Reference System assumption")
    area_km2: float | None = Field(
        default=None, ge=0.0, description="Geodesic area in square kilometers"
    )

    @model_validator(mode="after")
    def validate_geometry_coordinates(self) -> Self:
        coords = self.coordinates
        if self.type == GeometryType.POINT:
            if not isinstance(coords, (list, tuple)) or len(coords) < 2:
                raise ValueError("Point coordinates must be a [longitude, latitude] pair")
            _validate_position((float(coords[0]), float(coords[1])))
        elif self.type == GeometryType.POLYGON:
            if not isinstance(coords, list) or len(coords) == 0:
                raise ValueError("Polygon must contain at least one linear ring")
            for ring in coords:
                if not isinstance(ring, list) or len(ring) < 4:
                    raise ValueError("Linear ring must contain at least 4 positions")
                for p in ring:
                    if not isinstance(p, (list, tuple)) or len(p) < 2:
                        raise ValueError("Position must have at least 2 numbers [lon, lat]")
                    _validate_position((float(p[0]), float(p[1])))
                # Check ring closure
                if ring[0][0] != ring[-1][0] or ring[0][1] != ring[-1][1]:
                    raise ValueError("Polygon linear ring must be closed (first == last position)")
        elif self.type == GeometryType.MULTI_POLYGON:
            if not isinstance(coords, list) or len(coords) == 0:
                raise ValueError("MultiPolygon must contain at least one polygon")
            for poly in coords:
                if not isinstance(poly, list) or len(poly) == 0:
                    raise ValueError("Polygon in MultiPolygon must contain at least one ring")
                for ring in poly:
                    if not isinstance(ring, list) or len(ring) < 4:
                        raise ValueError("Ring in MultiPolygon must contain at least 4 positions")
                    for p in ring:
                        _validate_position((float(p[0]), float(p[1])))
                    if ring[0][0] != ring[-1][0] or ring[0][1] != ring[-1][1]:
                        raise ValueError("MultiPolygon ring must be closed")
        return self


class DateRange(StrictAnalysisModel):
    """Calendar date or ISO timestamp range."""

    start_date: str = Field(description="Start date (YYYY-MM-DD or ISO 8601 UTC)")
    end_date: str = Field(description="End date (YYYY-MM-DD or ISO 8601 UTC)")

    @model_validator(mode="after")
    def validate_chronological_order(self) -> Self:
        start_raw = self.start_date.replace("Z", "+00:00")
        end_raw = self.end_date.replace("Z", "+00:00")
        try:
            start_dt = datetime.fromisoformat(start_raw)
            end_dt = datetime.fromisoformat(end_raw)
            if start_dt > end_dt:
                raise ValueError("start_date must not be after end_date")
        except ValueError as e:
            if "must not be after" in str(e):
                raise
            # Fallback to date string comparison if simple YYYY-MM-DD
            if self.start_date > self.end_date:
                raise ValueError("start_date must not be after end_date") from e
        return self


class CloudCoverFilter(StrictAnalysisModel):
    """Cloud cover tolerance filter."""

    maximum_percent: float = Field(default=100.0, ge=0.0, le=100.0)
    preferred_maximum_percent: float | None = Field(default=None, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def validate_preference_bounds(self) -> Self:
        if (
            self.preferred_maximum_percent is not None
            and self.preferred_maximum_percent > self.maximum_percent
        ):
            raise ValueError("preferred_maximum_percent must not exceed maximum_percent")
        return self


# ---------------------------------------------------------------------------
# Satellite Scene & Selection
# ---------------------------------------------------------------------------


class SatelliteScene(StrictAnalysisModel):
    """Normalized satellite scene descriptor."""

    id: str = Field(min_length=1, max_length=512, description="Unique scene identifier")
    provider: str = Field(description="Imagery provider identifier")
    collection: str = Field(description="Provider collection name")
    acquisition_time: datetime = Field(description="UTC timestamp of acquisition")
    sensor_type: SensorType = Field(default=SensorType.MULTISPECTRAL)
    platform: str | None = Field(default=None, max_length=120)
    cloud_cover: float | None = Field(default=None, ge=0.0, le=100.0)
    geometry: AOIGeometry | None = Field(default=None, description="Footprint geometry")
    bbox: BoundingBox = Field(description="Bounding box [minX, minY, maxX, maxY]")
    thumbnail_url: str | None = Field(default=None, description="Public preview URL")
    preview_url: str | None = Field(default=None, description="High-resolution preview URL")
    available_bands: list[str] = Field(
        default_factory=list, description="Available band identifiers"
    )
    resolution_meters: float | None = Field(default=None, gt=0.0)
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] | None = Field(
        default=None, description="Safe provider-specific metadata"
    )

    @field_validator("acquisition_time")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return _as_utc(value, "acquisition_time")


class SceneSelection(StrictAnalysisModel):
    """Scene references for single or comparative analysis."""

    before_scene_id: str | None = Field(default=None, min_length=1, max_length=512)
    after_scene_id: str | None = Field(default=None, min_length=1, max_length=512)
    primary_scene_id: str | None = Field(default=None, min_length=1, max_length=512)
    supporting_scene_ids: list[str] = Field(default_factory=list)
    selection_reason: str | None = Field(default=None, max_length=500)


class AnalysisOptions(StrictAnalysisModel):
    """Configurable analysis parameters."""

    spectral_indices: list[str] = Field(
        default_factory=lambda: ["NDVI", "NDWI"],
        description="Spectral indices to compute",
    )
    change_threshold: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Threshold for significant change detection",
    )
    include_overlays: bool = Field(default=True)
    include_raw_measurements: bool = Field(default=True)
    generate_report: bool = Field(default=False)
    requested_report_format: ReportFormat = Field(default=ReportFormat.PDF)
    maximum_cloud_cover: float = Field(default=20.0, ge=0.0, le=100.0)
    language: str = Field(default="en", max_length=10)
    output_resolution_meters: float | None = Field(default=None, gt=0.0)


class ClientContext(StrictAnalysisModel):
    """Safe client environment metadata."""

    locale: str | None = Field(default="en-US", max_length=20)
    timezone: str | None = Field(default="UTC", max_length=50)
    ui_version: str | None = Field(default="0.1.0", max_length=50)


# ---------------------------------------------------------------------------
# Analysis Request & Job
# ---------------------------------------------------------------------------


class AnalysisRequest(StrictAnalysisModel):
    """User request payload to initiate an analysis workflow."""

    request_id: str | None = Field(default=None, max_length=120)
    question: str = Field(min_length=MIN_QUESTION_LENGTH, max_length=MAX_QUESTION_LENGTH)
    mode: AnalysisMode
    aoi: AOIGeometry
    date_range: DateRange | None = None
    scene_selection: SceneSelection | None = None
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)
    client_context: ClientContext | None = None

    @field_validator("question")
    @classmethod
    def validate_non_blank_question(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < MIN_QUESTION_LENGTH:
            raise ValueError(
                f"Question must contain at least {MIN_QUESTION_LENGTH} non-whitespace characters"
            )
        return trimmed

    @model_validator(mode="after")
    def validate_mode_requirements(self) -> Self:
        if self.mode == AnalysisMode.CHANGE_DETECTION:
            if not self.scene_selection and not self.date_range:
                raise ValueError("Change detection requires either scene_selection or date_range")
            if self.scene_selection:
                if (
                    not self.scene_selection.before_scene_id
                    or not self.scene_selection.after_scene_id
                ):
                    raise ValueError(
                        "Change detection with scene_selection requires before and after IDs"
                    )
                if self.scene_selection.before_scene_id == self.scene_selection.after_scene_id:
                    raise ValueError(
                        "before_scene_id and after_scene_id must be distinct for change detection"
                    )
        return self


# ---------------------------------------------------------------------------
# Error Representation
# ---------------------------------------------------------------------------


class APIFieldError(StrictAnalysisModel):
    """Specific field validation error."""

    field: str
    message: str
    code: str | None = None


class APIError(StrictAnalysisModel):
    """Standardized API error envelope."""

    code: APIErrorCode | str
    message: str
    status: int
    request_id: str | None = None
    field_errors: list[APIFieldError] = Field(default_factory=list)
    retryable: bool = False
    suggested_action: str | None = None
    details: dict[str, Any] | None = None


class AnalysisJob(StrictAnalysisModel):
    """Execution state of an analysis task."""

    job_id: str = Field(min_length=1, max_length=120)
    request_id: str = Field(min_length=1, max_length=120)
    status: AnalysisJobStatus
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    current_stage: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    estimated_completion_seconds: float | None = Field(default=None, ge=0.0)
    error: APIError | None = None

    @field_validator("created_at", "started_at", "completed_at")
    @classmethod
    def normalize_job_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "timestamp")

    @model_validator(mode="after")
    def validate_chronology(self) -> Self:
        if self.completed_at and self.created_at and self.completed_at < self.created_at:
            raise ValueError("completed_at cannot precede created_at")
        return self


# ---------------------------------------------------------------------------
# Spectral & Change Measurement Models
# ---------------------------------------------------------------------------


class SpectralMeasurement(StrictAnalysisModel):
    """Calculated metric for a single spectral index."""

    index_name: str = Field(min_length=1, max_length=50)
    value: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    median: float | None = None
    standard_deviation: float | None = Field(default=None, ge=0.0)
    valid_pixel_count: int | None = Field(default=None, ge=0)
    unit: str = Field(default="index_value")
    scene_id: str = Field(min_length=1, max_length=512)
    geometry: AOIGeometry | None = None
    region_id: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class OverlayStyle(StrictAnalysisModel):
    """Styling parameters for map overlays."""

    stroke_color: str = Field(default="#ef4444")
    stroke_width: float = Field(default=2.0, ge=0.0)
    fill_color: str | None = Field(default="#ef4444")
    fill_opacity: float = Field(default=0.5, ge=0.0, le=1.0)
    radius: float | None = Field(default=None, ge=0.0)
    icon: str | None = None
    color_ramp: list[str] | None = None
    min_value: float | None = None
    max_value: float | None = None


class OverlayFeature(StrictAnalysisModel):
    """Visual map overlay feature (vector or raster)."""

    id: str = Field(min_length=1, max_length=120)
    type: OverlayType
    title: str = Field(min_length=1, max_length=120)
    description: str | None = None
    geometry: AOIGeometry | None = None
    raster_url: str | None = None
    mask_url: str | None = None
    bounds: BoundingBox | None = None
    style: OverlayStyle = Field(default_factory=OverlayStyle)
    visible_by_default: bool = True
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_overlay_requirements(self) -> Self:
        if self.type in {OverlayType.POINT, OverlayType.POLYGON, OverlayType.BOUNDING_BOX}:
            if self.geometry is None:
                raise ValueError(f"Vector overlay of type '{self.type}' requires a geometry")
        elif self.type in {OverlayType.RASTER, OverlayType.MASK, OverlayType.HEATMAP}:
            if not self.raster_url and not self.mask_url and not self.geometry:
                raise ValueError(f"Raster overlay of type '{self.type}' requires url or geometry")
            if (self.raster_url or self.mask_url) and self.bounds is None:
                raise ValueError("Raster overlay with URL requires bounds [minX, minY, maxX, maxY]")
        return self


class AnalysisWarning(StrictAnalysisModel):
    """Machine-readable caveat or limitation."""

    code: WarningCode | str
    severity: WarningSeverity
    title: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=5, max_length=500)
    affected_evidence_ids: list[str] = Field(default_factory=list)
    suggested_action: str | None = None
    details: dict[str, Any] | None = None


class SpectralIndexResult(StrictAnalysisModel):
    """Computed spectral indices over an AOI."""

    scene_id: str = Field(min_length=1, max_length=512)
    indices: list[SpectralMeasurement] = Field(default_factory=list)
    summary: str
    evidence_ids: list[str] = Field(min_length=1)
    overlays: list[OverlayFeature] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[AnalysisWarning] = Field(default_factory=list)


class ChangeMetrics(StrictAnalysisModel):
    """Quantitative metrics of land surface change."""

    changed_area_square_km: float = Field(ge=0.0)
    changed_area_percent: float = Field(ge=0.0, le=100.0)
    gained_area_square_km: float = Field(ge=0.0)
    lost_area_square_km: float = Field(ge=0.0)
    unchanged_area_square_km: float = Field(ge=0.0)
    pixel_count: int | None = Field(default=None, ge=0)
    threshold_used: float = Field(default=0.20)


class ChangeDetectionResult(StrictAnalysisModel):
    """Measured change detection analysis between two scenes."""

    before_scene_id: str = Field(min_length=1, max_length=512)
    after_scene_id: str = Field(min_length=1, max_length=512)
    metrics: ChangeMetrics
    detected_regions: list[AOIGeometry] = Field(default_factory=list)
    summary: str
    evidence_ids: list[str] = Field(min_length=1)
    overlays: list[OverlayFeature] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[AnalysisWarning] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Findings & Evidence
# ---------------------------------------------------------------------------


class EvidenceProvenance(StrictAnalysisModel):
    """Traceable processing lineage of an evidence item."""

    computation: str
    algorithm_name: str | None = None
    version: str | None = None
    processed_at: datetime
    parameters: dict[str, Any] | None = None

    @field_validator("processed_at")
    @classmethod
    def normalize_processed_at(cls, value: datetime) -> datetime:
        return _as_utc(value, "processed_at")


class EvidenceItem(StrictAnalysisModel):
    """Atomic piece of measured evidence."""

    id: str = Field(min_length=1, max_length=120)
    type: EvidenceType
    title: str = Field(min_length=1, max_length=120)
    description: str
    source_scene_ids: list[str] = Field(min_length=1)
    geometry: AOIGeometry | None = None
    measurement: dict[str, Any] | None = None
    observed_at: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: EvidenceProvenance
    metadata: dict[str, Any] | None = None

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "observed_at")


class Finding(StrictAnalysisModel):
    """Structured finding grounded in evidence."""

    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=3, max_length=120)
    description: str
    severity: FindingSeverity = Field(default=FindingSeverity.INFORMATIONAL)
    category: str = Field(default="general")
    evidence_ids: list[str] = Field(
        min_length=1, description="Must reference at least one evidence item"
    )
    geometry: AOIGeometry | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    interpretation: str
    limitations: list[str] | None = None
    recommended_follow_up: list[str] | None = None


# ---------------------------------------------------------------------------
# Confidence Breakdown
# ---------------------------------------------------------------------------


class ConfidenceFactor(StrictAnalysisModel):
    """Contributing factor to confidence calculation."""

    code: str
    label: str
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence_ids: list[str] = Field(default_factory=list)


class ConfidenceBreakdown(StrictAnalysisModel):
    """Multi-factor confidence scoring breakdown."""

    overall: float = Field(ge=0.0, le=1.0)
    data_quality: float = Field(ge=0.0, le=1.0)
    temporal_quality: float = Field(ge=0.0, le=1.0)
    spatial_quality: float = Field(ge=0.0, le=1.0)
    model_confidence: float = Field(ge=0.0, le=1.0)
    evidence_agreement: float = Field(ge=0.0, le=1.0)
    factors: list[ConfidenceFactor] = Field(default_factory=list)
    methodology: str
    limitations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Processing Metadata & Full Analysis Response
# ---------------------------------------------------------------------------


class ProcessingMetadata(StrictAnalysisModel):
    """Audit metadata for the analysis execution."""

    processing_started_at: datetime
    processing_completed_at: datetime
    duration_milliseconds: int = Field(ge=0)
    pipeline_version: str = Field(default="1.0.0")
    algorithms: list[str] = Field(default_factory=list)
    ai_provider: str | None = None
    ai_model: str | None = None
    is_mock_data: bool = False

    @field_validator("processing_started_at", "processing_completed_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _as_utc(value, "processing_timestamp")


class AnalysisResponse(StrictAnalysisModel):
    """Complete analysis result envelope returned to the client."""

    request_id: str = Field(min_length=1, max_length=120)
    job_id: str = Field(min_length=1, max_length=120)
    status: AnalysisJobStatus = Field(default=AnalysisJobStatus.COMPLETED)
    answer: str
    answer_type: str = Field(default="text_and_evidence")
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    spectral_result: SpectralIndexResult | None = None
    change_result: ChangeDetectionResult | None = None
    overlays: list[OverlayFeature] = Field(default_factory=list)
    confidence: ConfidenceBreakdown
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    scenes: list[SatelliteScene] = Field(default_factory=list)
    processing_metadata: ProcessingMetadata
