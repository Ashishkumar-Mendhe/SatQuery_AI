from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

CATALOG_SCHEMA_VERSION: Literal["1.0"] = "1.0"
CATALOG_MAX_COLLECTIONS = 50
CATALOG_MAX_ITEMS = 100
CATALOG_MAX_GEOMETRY_POSITIONS = 500
CATALOG_MAX_CURSOR_LENGTH = 2048

ProviderIdentifier = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9._-]*$"),
]
CollectionIdentifier = Annotated[str, Field(min_length=1, max_length=160)]
ProviderAssetIdentifier = Annotated[str, Field(min_length=1, max_length=512)]
type Coordinate = Annotated[float, Field(strict=True)]
type Position = tuple[Coordinate, Coordinate]
type LinearRing = list[Position]
type PolygonCoordinates = list[LinearRing]
type MultiPolygonCoordinates = list[PolygonCoordinates]
type BoundingBox = tuple[Coordinate, Coordinate, Coordinate, Coordinate]


class StrictCatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return value.astimezone(UTC)


def _validate_cursor(value: str | None) -> str | None:
    if value is None:
        return None
    if not value or len(value) > CATALOG_MAX_CURSOR_LENGTH:
        raise ValueError(f"cursor must contain 1 to {CATALOG_MAX_CURSOR_LENGTH} characters")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise ValueError("cursor must not contain control characters")
    return value


def _validate_position(position: Position) -> None:
    longitude, latitude = position
    if not isfinite(longitude) or not isfinite(latitude):
        raise ValueError("geometry positions must contain finite numbers")
    if not -180 <= longitude <= 180:
        raise ValueError("geometry longitude must be between -180 and 180")
    if not -90 <= latitude <= 90:
        raise ValueError("geometry latitude must be between -90 and 90")


def _orientation(a: Position, b: Position, c: Position) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Position, b: Position, point: Position) -> bool:
    epsilon = 1e-12
    return (
        min(a[0], b[0]) - epsilon <= point[0] <= max(a[0], b[0]) + epsilon
        and min(a[1], b[1]) - epsilon <= point[1] <= max(a[1], b[1]) + epsilon
        and abs(_orientation(a, b, point)) <= epsilon
    )


def _segments_intersect(a: Position, b: Position, c: Position, d: Position) -> bool:
    epsilon = 1e-12
    first = _orientation(a, b, c)
    second = _orientation(a, b, d)
    third = _orientation(c, d, a)
    fourth = _orientation(c, d, b)
    if ((first > epsilon and second < -epsilon) or (first < -epsilon and second > epsilon)) and (
        (third > epsilon and fourth < -epsilon) or (third < -epsilon and fourth > epsilon)
    ):
        return True
    return (
        (abs(first) <= epsilon and _on_segment(a, b, c))
        or (abs(second) <= epsilon and _on_segment(a, b, d))
        or (abs(third) <= epsilon and _on_segment(c, d, a))
        or (abs(fourth) <= epsilon and _on_segment(c, d, b))
    )


def _validate_ring(ring: LinearRing) -> None:
    if len(ring) < 4:
        raise ValueError("each geometry ring must contain at least four positions")
    for position in ring:
        _validate_position(position)
    if ring[0] != ring[-1]:
        raise ValueError("each geometry ring must be closed")
    if len(set(ring[:-1])) < 3:
        raise ValueError("each geometry ring must contain at least three distinct vertices")
    for index in range(len(ring) - 1):
        if ring[index] == ring[index + 1]:
            raise ValueError("geometry rings must not contain consecutive duplicate vertices")
        if abs(ring[index][0] - ring[index + 1][0]) > 180:
            raise ValueError("antimeridian-crossing geometry is not supported")
    signed_area = sum(
        ring[index][0] * ring[index + 1][1] - ring[index + 1][0] * ring[index][1]
        for index in range(len(ring) - 1)
    )
    if abs(signed_area) <= 1e-12:
        raise ValueError("geometry rings must enclose a non-zero area")
    edge_count = len(ring) - 1
    for first_index in range(edge_count):
        for second_index in range(first_index + 1, edge_count):
            if second_index in {first_index, first_index + 1}:
                continue
            if first_index == 0 and second_index == edge_count - 1:
                continue
            if _segments_intersect(
                ring[first_index],
                ring[first_index + 1],
                ring[second_index],
                ring[second_index + 1],
            ):
                raise ValueError("geometry rings must not self-intersect")


def _validate_polygon(coordinates: PolygonCoordinates) -> int:
    if not coordinates:
        raise ValueError("Polygon coordinates must contain an exterior ring")
    position_count = 0
    for ring in coordinates:
        _validate_ring(ring)
        position_count += len(ring)
    return position_count


class CatalogPolygon(StrictCatalogModel):
    type: Literal["Polygon"]
    coordinates: PolygonCoordinates

    @model_validator(mode="after")
    def validate_geometry(self) -> Self:
        position_count = _validate_polygon(self.coordinates)
        if position_count > CATALOG_MAX_GEOMETRY_POSITIONS:
            raise ValueError(
                f"geometry may contain at most {CATALOG_MAX_GEOMETRY_POSITIONS} positions"
            )
        return self


class CatalogMultiPolygon(StrictCatalogModel):
    type: Literal["MultiPolygon"]
    coordinates: MultiPolygonCoordinates

    @model_validator(mode="after")
    def validate_geometry(self) -> Self:
        if not self.coordinates:
            raise ValueError("MultiPolygon coordinates must contain at least one Polygon")
        position_count = sum(_validate_polygon(polygon) for polygon in self.coordinates)
        if position_count > CATALOG_MAX_GEOMETRY_POSITIONS:
            raise ValueError(
                f"geometry may contain at most {CATALOG_MAX_GEOMETRY_POSITIONS} positions"
            )
        return self


CatalogGeometry = Annotated[
    CatalogPolygon | CatalogMultiPolygon,
    Field(discriminator="type"),
]


class AcquisitionInterval(StrictCatalogModel):
    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def require_timezone(cls, value: datetime, info: object) -> datetime:
        field_name = getattr(info, "field_name", "timestamp")
        return _as_utc(value, str(field_name))

    @model_validator(mode="after")
    def require_ordered_interval(self) -> Self:
        if self.end < self.start:
            raise ValueError("acquisition interval end must not precede start")
        return self


class CloudCoverFilter(StrictCatalogModel):
    max_percent: float = Field(ge=0, le=100, strict=True)
    source: Literal["provider_reported"] = "provider_reported"
    include_unknown: bool = False


class CatalogueSearchRequest(StrictCatalogModel):
    schema_version: Literal["1.0"] = CATALOG_SCHEMA_VERSION
    provider: ProviderIdentifier
    aoi: CatalogGeometry
    acquisition: AcquisitionInterval
    collections: list[CollectionIdentifier] = Field(
        default_factory=list,
        max_length=CATALOG_MAX_COLLECTIONS,
    )
    cloud_cover: CloudCoverFilter | None = None
    limit: int = Field(default=25, ge=1, le=CATALOG_MAX_ITEMS, strict=True)
    cursor: str | None = None
    sort: Literal["acquired_desc", "acquired_asc"] = "acquired_desc"

    @field_validator("collections")
    @classmethod
    def require_unique_collections(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("collection identifiers must be unique")
        return value

    @field_validator("cursor")
    @classmethod
    def validate_cursor(cls, value: str | None) -> str | None:
        return _validate_cursor(value)


class ProviderIdentity(StrictCatalogModel):
    id: ProviderIdentifier
    name: str = Field(min_length=1, max_length=160)


class CollectionIdentity(StrictCatalogModel):
    id: CollectionIdentifier
    title: str | None = Field(default=None, min_length=1, max_length=300)


class CatalogueCollectionSummary(StrictCatalogModel):
    id: CollectionIdentifier
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    license_name: str | None = Field(default=None, min_length=1, max_length=200)
    license_url: AnyHttpUrl | None = None
    temporal_start: datetime | None = None
    temporal_end: datetime | None = None
    platforms: list[str] = Field(default_factory=list, max_length=32)
    instruments: list[str] = Field(default_factory=list, max_length=32)
    spatial_resolutions_metres: list[float] = Field(default_factory=list, max_length=3)

    @field_validator("license_url")
    @classmethod
    def require_safe_license_url(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is not None and (value.scheme != "https" or value.username or value.password):
            raise ValueError("license URL must use HTTPS without embedded credentials")
        return value

    @field_validator("temporal_start", "temporal_end")
    @classmethod
    def normalize_temporal_bound(cls, value: datetime | None, info: object) -> datetime | None:
        field_name = getattr(info, "field_name", "temporal bound")
        return None if value is None else _as_utc(value, str(field_name))

    @field_validator("platforms", "instruments")
    @classmethod
    def require_unique_collection_labels(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 160 for item in value):
            raise ValueError("collection labels must contain 1 to 160 characters")
        if len(value) != len(set(value)):
            raise ValueError("collection labels must be unique")
        return value

    @field_validator("spatial_resolutions_metres")
    @classmethod
    def require_positive_resolutions(cls, value: list[float]) -> list[float]:
        if any(not isfinite(item) or item <= 0 for item in value):
            raise ValueError("collection resolutions must be positive finite values")
        return value

    @model_validator(mode="after")
    def require_ordered_temporal_extent(self) -> Self:
        if (
            self.temporal_start is not None
            and self.temporal_end is not None
            and self.temporal_end < self.temporal_start
        ):
            raise ValueError("collection temporal end must not precede start")
        return self


class CatalogueCollectionsResponse(StrictCatalogModel):
    schema_version: Literal["1.0"] = CATALOG_SCHEMA_VERSION
    provider: ProviderIdentity
    items: list[CatalogueCollectionSummary] = Field(max_length=CATALOG_MAX_COLLECTIONS)
    returned_count: int = Field(ge=0, le=CATALOG_MAX_COLLECTIONS, strict=True)

    @model_validator(mode="after")
    def validate_count(self) -> Self:
        if self.returned_count != len(self.items):
            raise ValueError("returned_count must equal the number of collections")
        return self


class SpatialResolution(StrictCatalogModel):
    value: float = Field(gt=0, strict=True)
    unit: Literal["metre"] = "metre"
    axis: Literal["nominal", "x", "y"] = "nominal"
    source_field: str = Field(min_length=1, max_length=256)


class CloudCoverMetadata(StrictCatalogModel):
    percent: float = Field(ge=0, le=100, strict=True)
    source_field: str = Field(min_length=1, max_length=256)
    semantics: str = Field(min_length=1, max_length=500)


class CatalogueLicense(StrictCatalogModel):
    name: str = Field(min_length=1, max_length=200)
    url: AnyHttpUrl | None = None
    permits_analytical_use: bool | None = None
    summary: str | None = Field(default=None, min_length=1, max_length=1000)

    @field_validator("url")
    @classmethod
    def require_safe_license_url(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is not None and (value.scheme != "https" or value.username or value.password):
            raise ValueError("license URL must use HTTPS without embedded credentials")
        return value


class CataloguePreview(StrictCatalogModel):
    purpose: Literal["thumbnail", "preview"]
    access: Literal["public", "temporary", "backend_mediated", "unavailable"]
    href: AnyHttpUrl | None = None
    media_type: str | None = Field(default=None, min_length=1, max_length=160)
    width: int | None = Field(default=None, gt=0, le=20_000, strict=True)
    height: int | None = Field(default=None, gt=0, le=20_000, strict=True)
    expires_at: datetime | None = None
    attribution: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("href")
    @classmethod
    def require_safe_preview_url(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is not None and (value.scheme != "https" or value.username or value.password):
            raise ValueError("preview URL must use HTTPS without embedded credentials")
        return value

    @field_validator("expires_at")
    @classmethod
    def normalize_expiry(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "expires_at")

    @model_validator(mode="after")
    def validate_access_semantics(self) -> Self:
        if self.access in {"backend_mediated", "unavailable"} and self.href is not None:
            raise ValueError(f"{self.access} previews must not expose an href")
        if self.access == "public" and self.href is None:
            raise ValueError("public previews require an href")
        if self.access == "public" and self.expires_at is not None:
            raise ValueError("public previews must not declare an expiry")
        if self.access == "temporary" and (self.href is None or self.expires_at is None):
            raise ValueError("temporary previews require an href and expires_at")
        return self


class AssetAccess(StrictCatalogModel):
    state: Literal[
        "metadata_only",
        "provider_accessible",
        "requires_authorization",
        "requires_purchase",
        "unavailable",
        "unknown",
    ]
    method: Literal["none", "provider_reference", "backend_mediated"]
    reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_access_method(self) -> Self:
        if self.state in {"metadata_only", "unavailable", "unknown"} and self.method != "none":
            raise ValueError(f"{self.state} access must use method 'none'")
        if self.state == "provider_accessible" and self.method == "none":
            raise ValueError("provider-accessible assets require a mediated reference method")
        return self


class FieldProvenance(StrictCatalogModel):
    normalized_field: str = Field(min_length=1, max_length=256)
    source: Literal["provider_record", "provider_api", "adapter_derived"]
    source_field: str = Field(min_length=1, max_length=256)
    method: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_derived_method(self) -> Self:
        if self.source == "adapter_derived" and self.method is None:
            raise ValueError("adapter-derived metadata requires a method")
        return self


class CatalogueProvenance(StrictCatalogModel):
    adapter: str = Field(min_length=1, max_length=128)
    adapter_version: str = Field(min_length=1, max_length=128)
    retrieved_at: datetime
    source_record_id: str = Field(min_length=1, max_length=512)
    source_record_version: str | None = Field(default=None, min_length=1, max_length=256)
    metadata_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fields: list[FieldProvenance] = Field(min_length=1, max_length=100)

    @field_validator("retrieved_at")
    @classmethod
    def normalize_retrieved_at(cls, value: datetime) -> datetime:
        return _as_utc(value, "retrieved_at")

    @field_validator("fields")
    @classmethod
    def require_unique_field_provenance(cls, value: list[FieldProvenance]) -> list[FieldProvenance]:
        normalized_fields = [item.normalized_field for item in value]
        if len(normalized_fields) != len(set(normalized_fields)):
            raise ValueError("normalized provenance fields must be unique")
        return value


class FieldAvailability(StrictCatalogModel):
    field: str = Field(min_length=1, max_length=256)
    availability: Literal["unavailable"] = "unavailable"
    reason: str = Field(min_length=1, max_length=500)


def _geometry_bbox(geometry: CatalogGeometry) -> BoundingBox:
    polygons = (
        [geometry.coordinates] if isinstance(geometry, CatalogPolygon) else geometry.coordinates
    )
    positions = [position for polygon in polygons for ring in polygon for position in ring]
    longitudes = [position[0] for position in positions]
    latitudes = [position[1] for position in positions]
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)


class CatalogueScene(StrictCatalogModel):
    provider: ProviderIdentity
    provider_asset_id: ProviderAssetIdentifier
    provider_asset_version: str | None = Field(default=None, min_length=1, max_length=256)
    collection: CollectionIdentity
    acquisition: AcquisitionInterval
    platform: str | None = Field(default=None, min_length=1, max_length=160)
    instruments: list[str] = Field(default_factory=list, max_length=32)
    product_type: str | None = Field(default=None, min_length=1, max_length=160)
    processing_level: str | None = Field(default=None, min_length=1, max_length=160)
    footprint: CatalogGeometry
    bbox: BoundingBox
    cloud_cover: CloudCoverMetadata | None = None
    spatial_resolution: list[SpatialResolution] = Field(default_factory=list, max_length=3)
    bands: list[str] = Field(default_factory=list, max_length=256)
    polarizations: list[str] = Field(default_factory=list, max_length=16)
    preview: CataloguePreview | None = None
    license: CatalogueLicense | None = None
    asset_access: AssetAccess
    provenance: CatalogueProvenance
    unavailable_fields: list[FieldAvailability] = Field(default_factory=list, max_length=100)

    @field_validator("instruments", "bands", "polarizations")
    @classmethod
    def require_unique_bounded_labels(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 160 for item in value):
            raise ValueError("metadata labels must contain 1 to 160 characters")
        if len(value) != len(set(value)):
            raise ValueError("metadata labels must be unique")
        return value

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, value: BoundingBox) -> BoundingBox:
        west, south, east, north = value
        if not all(isfinite(coordinate) for coordinate in value):
            raise ValueError("bbox coordinates must be finite")
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("bbox must be ordered west, south, east, north within WGS84 bounds")
        if east - west > 180:
            raise ValueError("antimeridian-crossing bbox is not supported")
        return value

    @model_validator(mode="after")
    def require_core_provenance(self) -> Self:
        derived_bbox = _geometry_bbox(self.footprint)
        if any(
            abs(actual - derived) > 1e-9
            for actual, derived in zip(self.bbox, derived_bbox, strict=True)
        ):
            raise ValueError("bbox must match the bounds derived from footprint")
        documented = {item.normalized_field for item in self.provenance.fields}
        required = {
            "provider_asset_id",
            "collection.id",
            "acquisition.start",
            "acquisition.end",
            "footprint",
            "bbox",
            "asset_access",
        }
        optional_fields = {
            "provider_asset_version": self.provider_asset_version,
            "platform": self.platform,
            "instruments": self.instruments,
            "product_type": self.product_type,
            "processing_level": self.processing_level,
            "cloud_cover": self.cloud_cover,
            "spatial_resolution": self.spatial_resolution,
            "bands": self.bands,
            "polarizations": self.polarizations,
            "preview": self.preview,
            "license": self.license,
        }
        required.update(field for field, value in optional_fields.items() if value)
        missing = sorted(required - documented)
        if missing:
            raise ValueError(f"provenance is missing normalized fields: {', '.join(missing)}")
        return self


class CatalogueSearchResponse(StrictCatalogModel):
    schema_version: Literal["1.0"] = CATALOG_SCHEMA_VERSION
    search_id: UUID
    status: Literal["succeeded", "partial"]
    query: CatalogueSearchRequest
    provider: ProviderIdentity
    items: list[CatalogueScene] = Field(max_length=CATALOG_MAX_ITEMS)
    returned_count: int = Field(ge=0, le=CATALOG_MAX_ITEMS, strict=True)
    next_cursor: str | None = None
    searched_at: datetime
    attributions: list[str] = Field(min_length=1, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("next_cursor")
    @classmethod
    def validate_next_cursor(cls, value: str | None) -> str | None:
        return _validate_cursor(value)

    @field_validator("searched_at")
    @classmethod
    def normalize_searched_at(cls, value: datetime) -> datetime:
        return _as_utc(value, "searched_at")

    @field_validator("attributions", "warnings")
    @classmethod
    def require_bounded_messages(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 1000 for item in value):
            raise ValueError("attribution and warning text must contain 1 to 1000 characters")
        return value

    @model_validator(mode="after")
    def validate_page(self) -> Self:
        if self.query.provider != self.provider.id:
            raise ValueError("response provider must match the requested provider")
        if self.returned_count != len(self.items):
            raise ValueError("returned_count must equal the number of items")
        if len(self.items) > self.query.limit:
            raise ValueError("response items must not exceed the requested limit")
        if any(item.provider.id != self.provider.id for item in self.items):
            raise ValueError("every scene provider must match the response provider")
        if self.status == "partial" and not self.warnings:
            raise ValueError("partial responses require at least one warning")
        return self
