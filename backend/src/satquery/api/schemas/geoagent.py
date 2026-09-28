"""Closed Phase 10 conversation/intent contracts; not an execution API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from satquery.api.schemas.catalog import CatalogGeometry
from satquery.api.schemas.viewer import StrictViewerModel, ViewerSceneIdentity

GEOAGENT_SCHEMA_VERSION: Literal["1.0"] = "1.0"

type GeoIntent = Literal[
    "imagery_view",
    "single_image_question",
    "image_caption",
    "spatial_grounding",
    "before_after_change",
    "optical_sar_observation",
    "map_aoi_action",
]
type GeoTool = Literal[
    "imagery_tiles",
    "inference_vqa",
    "inference_caption",
    "inference_grounding",
    "optical_change",
    "optical_sar_observation",
    "map_aoi_control",
]
type MissingInput = Literal[
    "aoi",
    "optical_scene",
    "second_optical_scene",
    "sar_scene",
    "sar_polarization",
    "acquisition_time",
    "feature_to_locate",
    "clarify_intent",
]
type Dependency = Literal[
    "inference_model",
    "grounding_model",
    "protected_jobs",
    "provider_rasters",
    "map_control",
    "cross_modal_alignment",
]


class SelectedGeoScene(StrictViewerModel):
    source: ViewerSceneIdentity
    modality: Literal["optical", "sar"]
    acquired_at: datetime | None = None
    polarization: Literal["HH", "HV", "VH", "VV"] | None = None

    @field_validator("source")
    @classmethod
    def stable_source_only(cls, value: ViewerSceneIdentity) -> ViewerSceneIdentity:
        if (
            ":" in value.item
            or "/" in value.item
            or "\\" in value.item
            or value.item in {".", ".."}
        ):
            raise ValueError("selected scene must use a stable item identifier, not a URL or path")
        return value

    @field_validator("acquired_at")
    @classmethod
    def utc_acquisition(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("selected acquisition time must have a UTC offset")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_modality(self) -> Self:
        if self.modality == "optical" and self.polarization is not None:
            raise ValueError("optical selection cannot claim a SAR polarization")
        return self


class GeoAgentMessageRequest(StrictViewerModel):
    schema_version: Literal["1.0"] = GEOAGENT_SCHEMA_VERSION
    request_id: UUID
    conversation_id: UUID | None = None
    message: str = Field(min_length=1, max_length=1000)
    selected_aoi: CatalogGeometry | None = None
    selected_scenes: list[SelectedGeoScene] = Field(default_factory=list, max_length=2)

    @field_validator("message")
    @classmethod
    def bounded_message(cls, value: str) -> str:
        if not value.strip() or any(
            ord(character) < 32 or ord(character) == 127 for character in value
        ):
            raise ValueError("message must contain visible text without control characters")
        return value

    @model_validator(mode="after")
    def unique_sources(self) -> Self:
        sources = [scene.source.model_dump_json() for scene in self.selected_scenes]
        if len(sources) != len(set(sources)):
            raise ValueError("selected scenes must have distinct source identities")
        return self


class GeoAgentDependencyFinding(StrictViewerModel):
    dependency: Dependency
    state: Literal["available", "unavailable", "unknown"]
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_reason(self) -> Self:
        if self.state != "available" and self.reason is None:
            raise ValueError("unknown or unavailable dependency needs an explanation")
        return self


class GeoAgentToolResultReference(StrictViewerModel):
    tool: GeoTool
    job_id: UUID | None = None
    artifact_id: UUID | None = None
    tile_set_id: UUID | None = None
    source_scenes: list[ViewerSceneIdentity] = Field(max_length=2)

    @model_validator(mode="after")
    def require_scientific_source(self) -> Self:
        if self.tool == "map_aoi_control":
            if (
                self.source_scenes
                or self.job_id is not None
                or self.artifact_id is not None
                or self.tile_set_id is not None
            ):
                raise ValueError("map actions cannot claim job, artifact, or scene evidence")
        elif self.tool == "imagery_tiles":
            if (
                len(self.source_scenes) != 1
                or self.tile_set_id is None
                or self.job_id is not None
                or self.artifact_id is not None
            ):
                raise ValueError("imagery results require one source and a real tile-set ID")
        elif not self.source_scenes or self.job_id is None:
            raise ValueError("analytical tool results need job and source scene identities")
        return self


class GeoAgentMessageResponse(StrictViewerModel):
    schema_version: Literal["1.0"] = GEOAGENT_SCHEMA_VERSION
    request_id: UUID
    conversation_id: UUID | None
    status: Literal[
        "plan_ready", "clarification_required", "unavailable", "unsupported", "completed"
    ]
    intended_analysis: GeoIntent | None
    selected_aoi: CatalogGeometry | None
    selected_scenes: list[SelectedGeoScene] = Field(max_length=2)
    ordered_source_scenes: list[ViewerSceneIdentity] = Field(default_factory=list, max_length=2)
    proposed_tool: GeoTool | None = None
    map_action: Literal["draw_aoi", "zoom_to_aoi", "clear_aoi"] | None = None
    missing_inputs: list[MissingInput] = Field(default_factory=list)
    dependencies: list[GeoAgentDependencyFinding] = Field(default_factory=list)
    tool_results: list[GeoAgentToolResultReference] = Field(default_factory=list, max_length=8)
    answer: str = Field(min_length=1, max_length=2000)
    execution_state: Literal["not_started", "finished"] = "not_started"

    @model_validator(mode="after")
    def consistent_result(self) -> Self:
        if len(self.missing_inputs) != len(set(self.missing_inputs)):
            raise ValueError("missing inputs must be unique")
        if len([finding.dependency for finding in self.dependencies]) != len(self.dependencies):
            raise ValueError("dependency findings must be unique")
        selected = {scene.source.model_dump_json() for scene in self.selected_scenes}
        if any(scene.model_dump_json() not in selected for scene in self.ordered_source_scenes):
            raise ValueError("ordered source scenes must be selected scenes")
        if any(
            scene.model_dump_json() not in selected
            for result in self.tool_results
            for scene in result.source_scenes
        ):
            raise ValueError("tool result scenes must match the selected source identities")
        if self.status == "completed":
            if (
                self.execution_state != "finished"
                or not self.tool_results
                or self.proposed_tool is None
                or self.intended_analysis is None
            ):
                raise ValueError("completed answers require executed tool results")
            if any(result.tool != self.proposed_tool for result in self.tool_results):
                raise ValueError("tool result operation must match the proposed tool")
        elif self.execution_state != "not_started" or self.tool_results:
            raise ValueError("non-completed routing responses cannot claim tool results")
        if self.status == "plan_ready" and (self.proposed_tool is None or self.missing_inputs):
            raise ValueError("a ready plan requires a tool and no missing inputs")
        expected_tools: dict[GeoIntent, GeoTool] = {
            "imagery_view": "imagery_tiles",
            "single_image_question": "inference_vqa",
            "image_caption": "inference_caption",
            "spatial_grounding": "inference_grounding",
            "before_after_change": "optical_change",
            "optical_sar_observation": "optical_sar_observation",
            "map_aoi_action": "map_aoi_control",
        }
        if self.proposed_tool is not None and (
            self.intended_analysis is None
            or expected_tools[self.intended_analysis] != self.proposed_tool
        ):
            raise ValueError("proposed tool must match the intended analysis")
        if self.status in {"plan_ready", "completed"} and self.intended_analysis is not None:
            if (
                self.intended_analysis not in {"map_aoi_action", "imagery_view"}
                and self.selected_aoi is None
            ):
                raise ValueError("scientific plans require a selected AOI")
            expected_sources = (
                2
                if self.intended_analysis in {"before_after_change", "optical_sar_observation"}
                else 0
                if self.intended_analysis == "map_aoi_action"
                else 1
            )
            if len(self.ordered_source_scenes) != expected_sources:
                raise ValueError("ready plans require the expected ordered source scenes")
        if self.status == "clarification_required" and not self.missing_inputs:
            raise ValueError("clarification requires specific missing input")
        if self.status == "unavailable" and not any(
            finding.state == "unavailable" for finding in self.dependencies
        ):
            raise ValueError("unavailable status needs an unavailable dependency")
        if self.status == "unsupported" and self.proposed_tool is not None:
            raise ValueError("unsupported intent cannot propose a tool")
        if self.intended_analysis == "map_aoi_action":
            if self.map_action is None:
                raise ValueError("map/AOI intent requires an action")
        elif self.map_action is not None:
            raise ValueError("non-map intent cannot include a map action")
        return self
