"""Pydantic v2 schemas for SatQuery AI report generation contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    AOIGeometry,
    APIError,
    ConfidenceBreakdown,
    DateRange,
    ReportFormat,
    SatelliteScene,
    SpectralMeasurement,
)
from satquery.api.schemas.change import ChangeMetrics
from satquery.api.schemas.providers import DataOrigin
from satquery.api.schemas.query import AnswerClaim
from satquery.api.schemas.visual import VisualObservation

REPORT_SCHEMA_VERSION = "1.0.0"


class StrictReportModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return value.astimezone(UTC)


class ReportStatus(StrEnum):
    """Lifecycle state of a report generation request."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    # Legacy compatibility alias
    GENERATED = "generated"


class ReportSection(StrEnum):
    """Configurable sections in a dossier report."""

    SUMMARY = "summary"
    SOURCE_IMAGERY = "source_imagery"
    VISUAL_EVIDENCE = "visual_evidence"
    QUANTITATIVE_FINDINGS = "quantitative_findings"
    INTERPRETATION = "interpretation"
    CONFIDENCE_LIMITATIONS = "confidence_limitations"
    METHODS_PROVENANCE = "methods_provenance"


class ReportFigureType(StrEnum):
    """Types of rendered static visual evidence figures."""

    OVERVIEW_MAP = "overview_map"
    BEFORE_AFTER_PAIR = "before_after_pair"
    DIFFERENCE_COLORMAP = "difference_colormap"
    CLASSIFIED_MASK = "classified_mask"
    OBSERVATION_CROP = "observation_crop"
    SPECTRAL_CHART = "spectral_chart"


class ReportFigure(StrictReportModel):
    """Registered figure asset frozen in the report snapshot."""

    figure_id: str = Field(min_length=1, max_length=120)
    figure_type: ReportFigureType
    title: str = Field(min_length=1, max_length=150)
    caption: str = Field(max_length=500)
    asset_id: str | None = None
    relative_path: str | None = None
    width_px: int | None = Field(default=None, ge=1)
    height_px: int | None = Field(default=None, ge=1)
    data_origin: DataOrigin = DataOrigin.REAL
    associated_evidence_ids: list[str] = Field(default_factory=list)
    legend_items: list[dict[str, str]] = Field(default_factory=list)


class ReportSnapshot(StrictReportModel):
    """Immutable, server-resolved analytical snapshot of a report."""

    report_id: str = Field(min_length=1, max_length=120)
    schema_version: str = Field(default=REPORT_SCHEMA_VERSION)
    created_at: datetime
    analysis_timestamp: datetime
    title: str = Field(min_length=1, max_length=200)
    query: str | None = None
    analysis_mode: str | None = None
    aoi: AOIGeometry
    date_range: DateRange | None = None
    data_origin: DataOrigin = DataOrigin.REAL
    is_mock_data: bool = False
    is_fallback_data: bool = False
    is_cached_data: bool = False
    scenes: list[SatelliteScene] = Field(default_factory=list)
    answer: str | None = None
    claims: list[AnswerClaim] = Field(default_factory=list)
    observations: list[VisualObservation] = Field(default_factory=list)
    quantitative_summary: dict[str, Any] = Field(default_factory=dict)
    spectral_metrics: list[SpectralMeasurement] = Field(default_factory=list)
    change_metrics: ChangeMetrics | None = None
    confidence_breakdown: ConfidenceBreakdown | None = None
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    figures: list[ReportFigure] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    checksum_sha256: str | None = None

    @field_validator("created_at", "analysis_timestamp")
    @classmethod
    def normalize_snapshot_timestamps(cls, value: datetime) -> datetime:
        return _as_utc(value, "snapshot_timestamp")


class ReportRequest(StrictReportModel):
    """User request payload to generate an exportable report."""

    analysis_job_id: str | None = Field(default=None, max_length=120)
    result_id: str | None = Field(default=None, max_length=120)
    format: ReportFormat = Field(default=ReportFormat.PDF)
    formats: list[ReportFormat] = Field(default_factory=lambda: [ReportFormat.PDF])
    title: str | None = Field(default=None, max_length=150)
    include_map: bool = Field(default=True)
    include_evidence: bool = Field(default=True)
    include_methodology: bool = Field(default=True)
    include_warnings: bool = Field(default=True)
    included_sections: list[ReportSection] = Field(
        default_factory=lambda: [
            ReportSection.SUMMARY,
            ReportSection.SOURCE_IMAGERY,
            ReportSection.VISUAL_EVIDENCE,
            ReportSection.QUANTITATIVE_FINDINGS,
            ReportSection.INTERPRETATION,
            ReportSection.CONFIDENCE_LIMITATIONS,
            ReportSection.METHODS_PROVENANCE,
        ]
    )
    locale: str = Field(default="en", max_length=20)


class ReportFormatStatus(StrictReportModel):
    """Readiness status for an individual export format."""

    format: ReportFormat
    status: ReportStatus
    download_url: str | None = None
    file_size_bytes: int | None = Field(default=None, ge=0)
    error: APIError | None = None
    generated_at: datetime | None = None

    @field_validator("generated_at")
    @classmethod
    def normalize_format_timestamp(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "generated_at")


class ReportResponse(StrictReportModel):
    """Report creation status, format readiness, and download metadata."""

    report_id: str = Field(min_length=1, max_length=120)
    analysis_job_id: str | None = Field(default=None, max_length=120)
    status: ReportStatus = Field(default=ReportStatus.COMPLETED)
    format: ReportFormat = Field(default=ReportFormat.PDF)
    download_url: str | None = Field(default=None, max_length=512)
    created_at: datetime
    expires_at: datetime | None = None
    file_size_bytes: int | None = Field(default=None, ge=0)
    error: APIError | None = None
    title: str = Field(default="SatQuery Analysis Report")
    data_origin: DataOrigin = DataOrigin.REAL
    formats: dict[str, ReportFormatStatus] = Field(default_factory=dict)
    snapshot_checksum: str | None = None

    @field_validator("created_at", "expires_at")
    @classmethod
    def normalize_report_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "report_timestamp")
