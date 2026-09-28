"""Pydantic schemas for Area of Interest (AOI) validation contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from satquery.api.schemas.analysis import (
    AnalysisMode,
    AOIGeometry,
    BoundingBox,
    GeometryType,
    StrictAnalysisModel,
)

AOI_VALIDATION_SCHEMA_VERSION: Literal["1.0"] = "1.0"


class AoiValidationCode(StrEnum):
    AOI_REQUIRED = "AOI_REQUIRED"
    AOI_EMPTY = "AOI_EMPTY"
    INVALID_COORDINATE = "INVALID_COORDINATE"
    LONGITUDE_OUT_OF_RANGE = "LONGITUDE_OUT_OF_RANGE"
    LATITUDE_OUT_OF_RANGE = "LATITUDE_OUT_OF_RANGE"
    POLYGON_NOT_CLOSED = "POLYGON_NOT_CLOSED"
    INSUFFICIENT_VERTICES = "INSUFFICIENT_VERTICES"
    AOI_SELF_INTERSECTION = "AOI_SELF_INTERSECTION"
    AOI_TOO_SMALL = "AOI_TOO_SMALL"
    AOI_TOO_LARGE = "AOI_TOO_LARGE"
    TOO_MANY_COORDINATES = "TOO_MANY_COORDINATES"
    UNSUPPORTED_GEOMETRY = "UNSUPPORTED_GEOMETRY"
    UNSUPPORTED_ANTIMERIDIAN_CROSSING = "UNSUPPORTED_ANTIMERIDIAN_CROSSING"
    POLYGON_HOLES_UNSUPPORTED = "POLYGON_HOLES_UNSUPPORTED"


class AoiIssueSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class AoiValidationIssue(StrictAnalysisModel):
    """A structured warning or error message resulting from AOI validation."""

    code: AoiValidationCode = Field(description="Standardized machine-readable validation code")
    message: str = Field(description="Human-readable explanation of the validation issue")
    severity: AoiIssueSeverity = Field(
        default=AoiIssueSeverity.ERROR, description="Severity level of this issue"
    )
    field: str | None = Field(
        default=None, description="Path to the problematic property or coordinate"
    )


class AoiValidationRequest(StrictAnalysisModel):
    """Request payload for authoritative backend AOI geometry validation."""

    geometry: AOIGeometry = Field(description="The GeoJSON geometry of the Area of Interest")
    client_area_km2: float | None = Field(
        default=None, ge=0.0, description="Optional client-calculated geodesic area in km²"
    )
    intended_mode: AnalysisMode | None = Field(
        default=None, description="Optional intended analysis workflow mode"
    )


class AoiValidationResponse(BaseModel):
    """Authoritative response detailing validation status, normalized geometry, and metrics."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    valid: bool = Field(description="True if geometry meets all requirements for analysis")
    normalized_geometry: AOIGeometry | None = Field(
        default=None, description="Normalized GeoJSON geometry with counter-clockwise ring ordering"
    )
    bbox: BoundingBox | None = Field(
        default=None, description="Calculated WGS84 bounding box [minX, minY, maxX, maxY]"
    )
    area_km2: float | None = Field(
        default=None, ge=0.0, description="Authoritative geodesic area in square kilometers"
    )
    geometry_type: GeometryType | None = Field(
        default=None, description="Type of geometry validated"
    )
    coordinate_count: int = Field(default=0, ge=0, description="Total number of vertex positions")
    warnings: list[AoiValidationIssue] = Field(
        default_factory=list, description="Non-fatal notices or caveats"
    )
    errors: list[AoiValidationIssue] = Field(
        default_factory=list, description="Blocking validation errors"
    )
    validation_version: Literal["1.0"] = Field(
        default=AOI_VALIDATION_SCHEMA_VERSION, description="Contract version"
    )
