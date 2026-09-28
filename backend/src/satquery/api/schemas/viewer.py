from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from satquery.api.schemas.catalog import (
    AcquisitionInterval,
    CollectionIdentifier,
    ProviderAssetIdentifier,
    ProviderIdentifier,
)

VIEWER_SCHEMA_VERSION: Literal["1.0"] = "1.0"
VIEWER_STATE_VERSION: Literal[1] = 1
VIEWER_MAX_TIMELINE_SCENES = 100

ViewerIdentifier = Annotated[
    str,
    Field(min_length=1, max_length=160, pattern=r"^[a-z0-9][a-z0-9._-]*$"),
]
type ViewerBounds = tuple[float, float, float, float]


class StrictViewerModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return value.astimezone(UTC)


def _validate_bounds(value: ViewerBounds) -> ViewerBounds:
    west, south, east, north = value
    if not all(isfinite(coordinate) for coordinate in value):
        raise ValueError("bounds coordinates must be finite")
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("bounds must be ordered west, south, east, north within WGS84")
    if east - west > 180:
        raise ValueError("antimeridian-crossing bounds are not supported")
    return value


def _require_unique_text(value: list[str], label: str) -> list[str]:
    if any(not item or len(item) > 1000 for item in value):
        raise ValueError(f"{label} must contain 1 to 1000 characters")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must be unique")
    return value


class ViewerSceneIdentity(StrictViewerModel):
    provider: ProviderIdentifier
    collection: CollectionIdentifier
    item: ProviderAssetIdentifier


class ResolvedImageryAssetIdentity(StrictViewerModel):
    scene: ViewerSceneIdentity
    asset: ProviderAssetIdentifier
    asset_version: str | None = Field(default=None, min_length=1, max_length=256)


class CatalogueAvailability(StrictViewerModel):
    state: Literal["available", "stale", "unavailable", "unknown"]
    reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def require_unavailable_reason(self) -> Self:
        if self.state in {"stale", "unavailable"} and self.reason is None:
            raise ValueError(f"catalogue state '{self.state}' requires a reason")
        return self


class AssetAccessibility(StrictViewerModel):
    state: Literal[
        "accessible",
        "requires_authorization",
        "requires_purchase",
        "expired",
        "unavailable",
        "unknown",
    ]
    method: Literal["none", "provider_reference", "backend_mediated"]
    reason: str | None = Field(default=None, min_length=1, max_length=1000)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def normalize_expiry(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "expires_at")

    @model_validator(mode="after")
    def validate_access_semantics(self) -> Self:
        if self.state == "accessible" and self.method == "none":
            raise ValueError("accessible imagery requires a provider or backend access method")
        if self.state != "accessible" and self.method != "none":
            raise ValueError(f"asset state '{self.state}' must not expose an access method")
        if self.state in {"requires_authorization", "requires_purchase", "expired", "unavailable"}:
            if self.reason is None:
                raise ValueError(f"asset state '{self.state}' requires a reason")
        if self.state == "expired" and self.expires_at is None:
            raise ValueError("expired imagery access requires expires_at")
        return self


class AnalysisReadiness(StrictViewerModel):
    state: Literal["not_assessed", "not_ready", "ready", "unsupported"]
    reason: str = Field(min_length=1, max_length=1000)


class SupportedRenderPreset(StrictViewerModel):
    id: ViewerIdentifier
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=500)
    mode: Literal["rgb", "single_band"]
    bands: list[ProviderAssetIdentifier] = Field(min_length=1, max_length=3)
    purpose: Literal["visualization"] = "visualization"

    @field_validator("bands")
    @classmethod
    def require_unique_bands(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("render preset bands must be unique")
        return value

    @model_validator(mode="after")
    def validate_mode_band_count(self) -> Self:
        required = 3 if self.mode == "rgb" else 1
        if len(self.bands) != required:
            raise ValueError(f"{self.mode} render presets require exactly {required} band(s)")
        return self


class ResolvedImageryAsset(StrictViewerModel):
    schema_version: Literal["1.0"] = VIEWER_SCHEMA_VERSION
    identity: ResolvedImageryAssetIdentity
    acquisition: AcquisitionInterval
    media_type: str = Field(min_length=1, max_length=160, pattern=r"^image/[a-z0-9.+-]+$")
    bounds: ViewerBounds
    render_presets: list[SupportedRenderPreset] = Field(min_length=1, max_length=20)
    default_render_preset: ViewerIdentifier
    catalogue_availability: CatalogueAvailability
    asset_accessibility: AssetAccessibility
    analysis_readiness: AnalysisReadiness
    attributions: list[str] = Field(min_length=1, max_length=20)
    resolved_at: datetime

    @field_validator("bounds")
    @classmethod
    def validate_bounds(cls, value: ViewerBounds) -> ViewerBounds:
        return _validate_bounds(value)

    @field_validator("attributions")
    @classmethod
    def require_unique_attributions(cls, value: list[str]) -> list[str]:
        return _require_unique_text(value, "attributions")

    @field_validator("resolved_at")
    @classmethod
    def normalize_resolved_at(cls, value: datetime) -> datetime:
        return _as_utc(value, "resolved_at")

    @model_validator(mode="after")
    def validate_presets(self) -> Self:
        preset_ids = [preset.id for preset in self.render_presets]
        if len(preset_ids) != len(set(preset_ids)):
            raise ValueError("resolved imagery render preset identifiers must be unique")
        if self.default_render_preset not in preset_ids:
            raise ValueError("default_render_preset must identify a supported render preset")
        return self


class TileAccess(StrictViewerModel):
    state: Literal["available", "expired", "denied", "unavailable"]
    reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def require_failure_reason(self) -> Self:
        if self.state != "available" and self.reason is None:
            raise ValueError(f"tile access state '{self.state}' requires a reason")
        return self


class TileMetadataRequest(StrictViewerModel):
    schema_version: Literal["1.0"] = VIEWER_SCHEMA_VERSION
    scene: ViewerSceneIdentity
    render_preset: Literal["natural-color"] = "natural-color"
    tile_size: Literal[256] = 256


class TileMetadata(StrictViewerModel):
    schema_version: Literal["1.0"] = VIEWER_SCHEMA_VERSION
    tile_set_id: UUID
    asset: ResolvedImageryAssetIdentity
    render_preset: ViewerIdentifier
    bounds: ViewerBounds
    min_zoom: int = Field(ge=0, le=24, strict=True)
    max_zoom: int = Field(ge=0, le=24, strict=True)
    tile_size: Literal[256, 512]
    media_type: Literal["image/png", "image/jpeg", "image/webp"]
    url_template: str | None = Field(default=None, min_length=1, max_length=2048)
    expires_at: datetime | None = None
    attributions: list[str] = Field(min_length=1, max_length=20)
    access: TileAccess

    @field_validator("bounds")
    @classmethod
    def validate_bounds(cls, value: ViewerBounds) -> ViewerBounds:
        return _validate_bounds(value)

    @field_validator("expires_at")
    @classmethod
    def normalize_expiry(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value, "expires_at")

    @field_validator("attributions")
    @classmethod
    def require_unique_attributions(cls, value: list[str]) -> list[str]:
        return _require_unique_text(value, "attributions")

    @field_validator("url_template")
    @classmethod
    def require_mediated_tile_template(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("tile URL template must be a credential-free relative API path")
        if not value.startswith("/api/v1/") or not all(
            marker in value for marker in ("{z}", "{x}", "{y}")
        ):
            raise ValueError("tile URL template must use /api/v1/ and contain {z}, {x}, and {y}")
        return value

    @model_validator(mode="after")
    def validate_tile_access(self) -> Self:
        if self.max_zoom < self.min_zoom:
            raise ValueError("max_zoom must not be less than min_zoom")
        if self.access.state == "available":
            if self.url_template is None or self.expires_at is None:
                raise ValueError("available tile access requires a URL template and expires_at")
        elif self.url_template is not None:
            raise ValueError("unavailable tile access must not expose a URL template")
        if self.access.state == "expired" and self.expires_at is None:
            raise ValueError("expired tile access requires expires_at")
        return self


class ImageryDisplaySettings(StrictViewerModel):
    visible: bool = True
    opacity: float = Field(default=1.0, ge=0, le=1, strict=True)
    brightness_min: float = Field(default=0.0, ge=0, le=1, strict=True)
    brightness_max: float = Field(default=1.0, ge=0, le=1, strict=True)
    contrast: float = Field(default=0.0, ge=-1, le=1, strict=True)
    saturation: float = Field(default=0.0, ge=-1, le=1, strict=True)

    @model_validator(mode="after")
    def validate_brightness_range(self) -> Self:
        if self.brightness_max < self.brightness_min:
            raise ValueError("brightness_max must not be less than brightness_min")
        return self


class RenderStatus(StrictViewerModel):
    state: Literal["not_requested", "loading", "rendered", "failed", "expired"]
    reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def require_failure_reason(self) -> Self:
        if self.state in {"failed", "expired"} and self.reason is None:
            raise ValueError(f"render state '{self.state}' requires a reason")
        return self


class ActiveImageryLayer(StrictViewerModel):
    layer_id: ViewerIdentifier
    asset: ResolvedImageryAssetIdentity
    acquisition: AcquisitionInterval
    render_preset: ViewerIdentifier
    tile_set_id: UUID | None = None
    display: ImageryDisplaySettings
    catalogue_availability: CatalogueAvailability
    asset_accessibility: AssetAccessibility
    render_status: RenderStatus
    analysis_readiness: AnalysisReadiness

    @model_validator(mode="after")
    def validate_rendered_state(self) -> Self:
        if self.render_status.state == "rendered":
            if self.tile_set_id is None:
                raise ValueError("a rendered imagery layer requires tile_set_id")
            if self.asset_accessibility.state != "accessible":
                raise ValueError("a rendered imagery layer requires accessible asset state")
        return self


class ComparisonScene(StrictViewerModel):
    scene: ViewerSceneIdentity
    acquisition: AcquisitionInterval


class ComparisonSelection(StrictViewerModel):
    scene_a: ComparisonScene
    scene_b: ComparisonScene

    @model_validator(mode="after")
    def validate_distinct_ordered_scenes(self) -> Self:
        if self.scene_a.scene == self.scene_b.scene:
            raise ValueError("comparison scenes A and B must be distinct")
        if self.scene_a.acquisition.start >= self.scene_b.acquisition.start:
            raise ValueError("comparison scene A must be acquired before scene B")
        return self


class SavedComparisonSlots(StrictViewerModel):
    scene_a: ComparisonScene | None = None
    scene_b: ComparisonScene | None = None

    @model_validator(mode="after")
    def validate_slots(self) -> Self:
        if self.scene_a is None and self.scene_b is None:
            raise ValueError("at least one saved comparison slot is required")
        if (
            self.scene_a is not None
            and self.scene_b is not None
            and self.scene_a.scene == self.scene_b.scene
        ):
            raise ValueError("saved comparison slots must be distinct")
        return self


class TimelineScene(StrictViewerModel):
    scene: ViewerSceneIdentity
    acquisition: AcquisitionInterval


class TimelineSelection(StrictViewerModel):
    scenes: list[TimelineScene] = Field(min_length=1, max_length=VIEWER_MAX_TIMELINE_SCENES)
    selected_scene: ViewerSceneIdentity

    @model_validator(mode="after")
    def validate_timeline(self) -> Self:
        identities = [entry.scene for entry in self.scenes]
        identity_keys = [entry.model_dump_json() for entry in identities]
        if len(identity_keys) != len(set(identity_keys)):
            raise ValueError("timeline scene identities must be unique")
        if any(
            current.acquisition.start > following.acquisition.start
            for current, following in zip(self.scenes, self.scenes[1:], strict=False)
        ):
            raise ValueError("timeline scenes must be ordered by increasing acquisition time")
        if self.selected_scene not in identities:
            raise ValueError("selected_scene must identify a scene in the timeline")
        return self


class SavedImageryLayer(StrictViewerModel):
    layer_id: ViewerIdentifier
    asset: ResolvedImageryAssetIdentity
    acquisition: AcquisitionInterval
    render_preset: ViewerIdentifier
    display: ImageryDisplaySettings


class ViewerAoiReference(StrictViewerModel):
    storage_key: Literal["satquery.aoi-draft.v1"]
    geometry_fingerprint: str = Field(min_length=1, max_length=100_000)


class ViewerCamera(StrictViewerModel):
    center: tuple[float, float]
    zoom: float = Field(ge=0, le=24)
    bearing: float = Field(ge=-360, le=360)
    pitch: float = Field(ge=0, le=85)

    @field_validator("center")
    @classmethod
    def validate_center(cls, value: tuple[float, float]) -> tuple[float, float]:
        longitude, latitude = value
        if not all(isfinite(coordinate) for coordinate in value):
            raise ValueError("camera center coordinates must be finite")
        if not (-180 <= longitude <= 180 and -85.051129 <= latitude <= 85.051129):
            raise ValueError("camera center must be within the Web Mercator world")
        return value


class SavedViewerState(StrictViewerModel):
    version: Literal[1] = VIEWER_STATE_VERSION
    saved_at: datetime
    aoi_reference: ViewerAoiReference | None = None
    camera: ViewerCamera | None = None
    active_layer: SavedImageryLayer | None = None
    comparison_slots: SavedComparisonSlots | None = None
    comparison: ComparisonSelection | None = None
    timeline: TimelineSelection | None = None

    @field_validator("saved_at")
    @classmethod
    def normalize_saved_at(cls, value: datetime) -> datetime:
        return _as_utc(value, "saved_at")
