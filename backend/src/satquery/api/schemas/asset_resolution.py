from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from satquery.api.schemas.catalog import CatalogueLicense, CataloguePreview
from satquery.api.schemas.viewer import (
    AnalysisReadiness,
    AssetAccessibility,
    CatalogueAvailability,
    RenderStatus,
    ResolvedImageryAsset,
    ResolvedImageryAssetIdentity,
    StrictViewerModel,
    ViewerSceneIdentity,
)

ASSET_RESOLUTION_SCHEMA_VERSION: Literal["1.0"] = "1.0"


class AssetResolutionRequest(StrictViewerModel):
    schema_version: Literal["1.0"] = ASSET_RESOLUTION_SCHEMA_VERSION
    scene: ViewerSceneIdentity


class ResolvedRasterComponent(StrictViewerModel):
    identity: ResolvedImageryAssetIdentity
    render_role: Literal["red", "green", "blue"]
    band_name: str = Field(min_length=1, max_length=160)
    common_name: Literal["red", "green", "blue"]
    band_index: int = Field(ge=1, le=256, strict=True)
    media_type: Literal["image/tiff"]
    scale: float | None = None
    offset: float | None = None
    nodata: float | Literal["nan", "inf", "-inf"] | None = None
    crs: str = Field(min_length=1, max_length=160)
    resolution_metres: float = Field(gt=0, strict=True)
    shape: tuple[int, int] | None = None
    transform: tuple[float, ...] | None = None
    access_check: Literal["head_succeeded"]
    content_length_bytes: int | None = Field(default=None, ge=0, strict=True)

    @field_validator("scale", "offset")
    @classmethod
    def require_finite_optional_numbers(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(value):
            raise ValueError("raster scale and offset must be finite")
        return value

    @field_validator("nodata")
    @classmethod
    def require_finite_numeric_nodata(
        cls, value: float | Literal["nan", "inf", "-inf"] | None
    ) -> float | Literal["nan", "inf", "-inf"] | None:
        if isinstance(value, float) and not isfinite(value):
            raise ValueError("non-finite nodata must use a named string value")
        return value

    @field_validator("shape")
    @classmethod
    def validate_shape(cls, value: tuple[int, int] | None) -> tuple[int, int] | None:
        if value is not None and (value[0] <= 0 or value[1] <= 0):
            raise ValueError("raster shape dimensions must be positive")
        return value

    @field_validator("transform")
    @classmethod
    def validate_transform(cls, value: tuple[float, ...] | None) -> tuple[float, ...] | None:
        if value is not None:
            if len(value) not in {6, 9} or not all(isfinite(number) for number in value):
                raise ValueError("raster transform must contain six or nine finite numbers")
        return value


class AssetResolutionStatus(StrictViewerModel):
    state: Literal[
        "supported",
        "unsupported_format",
        "unavailable_asset",
        "access_credentials_required",
    ]
    reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def require_failure_reason(self) -> Self:
        if self.state != "supported" and self.reason is None:
            raise ValueError(f"asset resolution state '{self.state}' requires a reason")
        if self.state == "supported" and self.reason is not None:
            raise ValueError("supported asset resolution must not include a failure reason")
        return self


class AssetResolutionResponse(StrictViewerModel):
    schema_version: Literal["1.0"] = ASSET_RESOLUTION_SCHEMA_VERSION
    scene: ViewerSceneIdentity
    status: AssetResolutionStatus
    catalogue_availability: CatalogueAvailability
    asset_accessibility: AssetAccessibility
    render_status: RenderStatus
    analysis_readiness: AnalysisReadiness
    resolved_asset: ResolvedImageryAsset | None = None
    components: list[ResolvedRasterComponent] = Field(default_factory=list, max_length=3)
    thumbnail: CataloguePreview | None = None
    license: CatalogueLicense | None = None
    attributions: list[str] = Field(min_length=1, max_length=20)
    checked_at: datetime

    @field_validator("attributions")
    @classmethod
    def require_unique_attributions(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("asset-resolution attributions must be unique")
        return value

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("checked_at must include a UTC offset")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_resolution_result(self) -> Self:
        if self.status.state == "supported":
            if self.resolved_asset is None:
                raise ValueError("supported resolution requires a resolved asset")
            roles = [component.render_role for component in self.components]
            if roles != ["red", "green", "blue"]:
                raise ValueError(
                    "supported RGB resolution requires ordered red, green, blue components"
                )
            if any(component.identity.scene != self.scene for component in self.components):
                raise ValueError("every raster component must belong to the requested scene")
            preset = self.resolved_asset.render_presets[0]
            if preset.bands != [component.identity.asset for component in self.components]:
                raise ValueError("the RGB render preset must reference the resolved components")
            if self.catalogue_availability.state != "available":
                raise ValueError("supported resolution requires available catalogue metadata")
            if self.asset_accessibility.state != "accessible":
                raise ValueError("supported resolution requires accessible assets")
        elif self.resolved_asset is not None or self.components:
            raise ValueError("failed resolution must not return a usable asset or components")
        if self.render_status.state != "not_requested":
            raise ValueError("asset resolution cannot claim a browser rendering outcome")
        if self.analysis_readiness.state != "not_assessed":
            raise ValueError("asset resolution cannot claim analysis readiness")
        return self
