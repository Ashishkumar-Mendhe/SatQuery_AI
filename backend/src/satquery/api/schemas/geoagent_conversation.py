"""Bounded, owner-scoped GeoAgent conversation state and turn contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from satquery.api.schemas.catalog import CatalogGeometry
from satquery.api.schemas.geoagent import GeoIntent, GeoTool, SelectedGeoScene
from satquery.api.schemas.geoagent_execution import GeoAgentExecutionResponse
from satquery.api.schemas.viewer import StrictViewerModel, ViewerSceneIdentity


class ConversationSelection(StrictViewerModel):
    aoi: CatalogGeometry | None = None
    scenes: list[SelectedGeoScene] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def unique_sources(self) -> Self:
        identities = [scene.source.model_dump_json() for scene in self.scenes]
        if len(identities) != len(set(identities)):
            raise ValueError("conversation scenes must have distinct source identities")
        return self


class ConversationTurnRequest(StrictViewerModel):
    request_id: UUID
    expected_selection_revision: int = Field(ge=0, strict=True)
    message: str = Field(min_length=1, max_length=1000)
    # Omitted means reuse the conversation selection; an explicit empty selection clears it.
    selection: ConversationSelection | None = None

    @field_validator("message")
    @classmethod
    def visible_message(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("message must contain visible text without control characters")
        return value


class ConversationToolReference(StrictViewerModel):
    request_id: UUID
    tool: GeoTool
    job_id: UUID | None = None
    result_id: UUID | None = None
    status: Literal["submitted", "result_pending", "completed", "failed", "unavailable"]
    aoi_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_scenes: list[ViewerSceneIdentity] = Field(max_length=2)

    @model_validator(mode="after")
    def truthful_result(self) -> Self:
        if self.status == "completed" and (
            self.result_id is None or (self.tool != "imagery_tiles" and self.job_id is None)
        ):
            raise ValueError("completed tool reference requires its actual result and job IDs")
        if self.status in {"submitted", "result_pending"} and self.job_id is None:
            raise ValueError("pending tool reference requires a job ID")
        if self.status != "completed" and self.result_id is not None:
            raise ValueError("uncommitted tool reference cannot claim a result ID")
        return self


class VerifiedAnalysisReference(StrictViewerModel):
    tool: Literal[
        "inference_vqa",
        "inference_caption",
        "inference_grounding",
        "optical_change",
        "optical_sar_observation",
    ]
    job_id: UUID
    result_id: UUID
    aoi_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_scenes: list[ViewerSceneIdentity] = Field(min_length=1, max_length=2)
    verified_at: datetime


class ConversationState(StrictViewerModel):
    conversation_id: UUID
    selection: ConversationSelection = Field(default_factory=ConversationSelection)
    selection_revision: int = Field(default=0, ge=0)
    earlier_optical_scenes: list[SelectedGeoScene] = Field(default_factory=list, max_length=8)
    last_intent: GeoIntent | None = None
    last_verified: VerifiedAnalysisReference | None = None
    tool_references: list[ConversationToolReference] = Field(default_factory=list, max_length=8)


class ConversationTurnResponse(StrictViewerModel):
    conversation_id: UUID
    request_id: UUID
    status: Literal["clarification_required", "executed", "unavailable", "stale"]
    message: str = Field(min_length=1, max_length=1000)
    selection_revision: int = Field(ge=0)
    selection: ConversationSelection
    missing_reference: Literal["aoi", "earlier_scene", "change_result", "intent"] | None = None
    resolved_result: VerifiedAnalysisReference | None = None
    execution: GeoAgentExecutionResponse | None = None


def verified_reference(response: GeoAgentExecutionResponse) -> VerifiedAnalysisReference | None:
    """A queued job, tile set or missing committed result is never analysis evidence."""
    if (
        response.status != "completed"
        or response.job_id is None
        or response.result_id is None
        or response.summary.aoi_sha256 is None
        or response.summary.tool
        not in {
            "inference_vqa",
            "inference_caption",
            "inference_grounding",
            "optical_change",
            "optical_sar_observation",
        }
    ):
        return None
    return VerifiedAnalysisReference(
        tool=response.summary.tool,
        job_id=response.job_id,
        result_id=response.result_id,
        aoi_sha256=response.summary.aoi_sha256,
        source_scenes=response.summary.input_scenes,
        verified_at=datetime.now(UTC),
    )
