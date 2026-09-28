from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from satquery.api.schemas.catalog import AcquisitionInterval, CatalogGeometry
from satquery.api.schemas.scene_metadata import SceneMetadataResponse
from satquery.api.schemas.viewer import StrictViewerModel, ViewerBounds, ViewerSceneIdentity


class SarDiscoveryRequest(StrictViewerModel):
    provider: Literal["inpe-bdc"] = "inpe-bdc"
    aoi: CatalogGeometry
    acquisition: AcquisitionInterval
    limit: int = Field(default=10, ge=1, le=25, strict=True)


class SarDiscoveryScene(StrictViewerModel):
    source: ViewerSceneIdentity
    acquisition: AcquisitionInterval
    footprint: CatalogGeometry
    polarizations: list[Literal["HH", "HV", "VH", "VV"]] = Field(min_length=1, max_length=4)
    instrument_mode: Literal["IW", "EW", "SM"]
    processing_level: Literal["RTCH"]
    native_resolution_metres: float = Field(gt=0)
    metadata: SceneMetadataResponse


class SarDiscoveryResponse(StrictViewerModel):
    scenes: list[SarDiscoveryScene] = Field(max_length=25)
    provider_attribution: str


class SarPreparationRequest(StrictViewerModel):
    scene: ViewerSceneIdentity
    aoi: CatalogGeometry
    polarization: Literal["HH", "HV", "VH", "VV"]
    max_pixels: int = Field(default=1_000_000, ge=1, le=1_000_000, strict=True)


class SarMaskStatistics(StrictViewerModel):
    aoi_pixels: int = Field(ge=0)
    valid_pixels: int = Field(ge=0)
    nodata_pixels: int = Field(ge=0)
    layover_or_shadow_pixels: int = Field(ge=0)


class SarPreparationResponse(StrictViewerModel):
    preparation_id: UUID
    source: ViewerSceneIdentity
    acquisition_time: datetime
    polarization: Literal["HH", "HV", "VH", "VV"]
    crs: Literal["EPSG:4326"]
    transform: tuple[float, float, float, float, float, float]
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    bounds: ViewerBounds
    native_resolution_metres: float = Field(gt=0)
    analysis_units: Literal["gamma0_power"]
    calibration: str
    geometric_processing: str
    terrain_model: str
    mask: SarMaskStatistics
    display_scaling: str
    preview_url: str
    processing_version: str
    source_checksum: str | None = None
    warnings: list[str]

    @field_validator("warnings")
    @classmethod
    def unique_warnings(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("warnings must be unique")
        return value
