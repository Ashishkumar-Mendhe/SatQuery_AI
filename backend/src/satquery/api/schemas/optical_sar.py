"""Closed Phase 9E request and evidence contract for separate optical/SAR observations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from satquery.api.schemas.catalog import CatalogGeometry
from satquery.api.schemas.processing import OutputGrid, ProcessingJobStatus
from satquery.api.schemas.viewer import StrictViewerModel, ViewerSceneIdentity


class OpticalSarAnalysisRequest(StrictViewerModel):
    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    optical_scene: ViewerSceneIdentity
    sar_scene: ViewerSceneIdentity
    aoi: CatalogGeometry
    polarization: Literal["HH", "HV", "VH", "VV"]
    target_resolution_metres: float = Field(default=20.0, gt=0, le=30, strict=True)
    question: str = Field(min_length=1, max_length=500)

    @field_validator("target_resolution_metres")
    @classmethod
    def bounded_grid_resolution(cls, value: float) -> float:
        if value not in {20.0, 30.0}:
            raise ValueError("9E supports only 20 or 30 metre output cells")
        return value

    @model_validator(mode="after")
    def supported_sources(self) -> OpticalSarAnalysisRequest:
        if (
            self.optical_scene.provider != "earth-search"
            or self.optical_scene.collection != "sentinel-2-c1-l2a"
        ):
            raise ValueError("9E requires an Earth Search Sentinel-2 L2A optical scene")
        if self.sar_scene.provider != "inpe-bdc" or self.sar_scene.collection != "sentinel-1-rtc-1":
            raise ValueError("9E requires an INPE Sentinel-1 RTC C-band scene")
        return self


class OpticalSarObservation(StrictViewerModel):
    modality: Literal["optical", "sar"]
    source: ViewerSceneIdentity
    acquired_at: datetime
    layer: str
    measurement_name: str
    measured_value: float | None
    units: str
    valid_pixels: int = Field(ge=0)
    denominator_pixels: int = Field(gt=0)
    evidence_bounds: tuple[float, float, float, float] | None
    evidence_crs: str | None
    statement: str


class OpticalSarSourceEvidence(StrictViewerModel):
    source: ViewerSceneIdentity
    acquired_at: datetime
    source_version: str | None
    preparation_version: str | None
    checksum: str | None
    polarization: Literal["HH", "HV", "VH", "VV"] | None


class OpticalSarAnalysisResult(StrictViewerModel):
    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    job_id: UUID
    state: Literal["limited", "insufficient_evidence"]
    answer_kind: Literal["computed_observation_summary"] = "computed_observation_summary"
    answer: str
    optical: OpticalSarObservation
    sar: OpticalSarObservation
    source_evidence: tuple[OpticalSarSourceEvidence, OpticalSarSourceEvidence]
    aoi: CatalogGeometry
    grid: OutputGrid
    joint_usable_pixels: int = Field(ge=0)
    aoi_pixels: int = Field(gt=0)
    joint_usable_percent_of_aoi: float = Field(ge=0, le=100)
    joint_usable_area_square_metres: float = Field(ge=0)
    time_gap_hours: float = Field(ge=0)
    alignment_state: Literal["verified", "inconclusive", "unavailable"]
    agreement_state: Literal["not_assessed"] = "not_assessed"
    limitations: list[str]
    processing_version: str
    evidence_artifact_id: UUID


class OpticalSarJobStatus(ProcessingJobStatus):
    request_id: UUID
