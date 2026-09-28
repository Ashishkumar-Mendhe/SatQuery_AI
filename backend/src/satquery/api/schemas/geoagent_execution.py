"""Phase 10C bounded tool-dispatch outcome, separate from scientific results."""

from __future__ import annotations

from typing import Any, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from satquery.api.schemas.geoagent import GeoIntent, GeoTool
from satquery.api.schemas.viewer import StrictViewerModel, ViewerSceneIdentity

type ExecutionStatus = Literal[
    "submitted",
    "result_pending",
    "completed",
    "failed",
    "unavailable",
    "clarification_required",
    "unsupported",
    "submission_unknown",
]


class GeoAgentExecutionSummary(StrictViewerModel):
    intended_analysis: GeoIntent | None
    tool: GeoTool | None
    input_scenes: list[ViewerSceneIdentity] = Field(max_length=2)
    aoi_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    status: ExecutionStatus
    job_id: UUID | None = None
    result_id: UUID | None = None


class GeoAgentExecutionResponse(StrictViewerModel):
    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    conversation_id: UUID | None
    status: ExecutionStatus
    summary: GeoAgentExecutionSummary
    job_id: UUID | None = None
    result_id: UUID | None = None
    output: dict[str, Any] | None = None
    cancel_path: str | None = Field(
        default=None,
        pattern=r"^/api/v1/(inference/jobs|processing/change-jobs|optical-sar/jobs)/[0-9a-f-]{36}/cancel$",
    )
    error_code: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]*$", max_length=80)
    message: str = Field(min_length=1, max_length=1000)
    retry_same_request_id: bool = False

    @model_validator(mode="after")
    def consistent_execution(self) -> Self:
        if (
            self.summary.status != self.status
            or self.summary.job_id != self.job_id
            or self.summary.result_id != self.result_id
        ):
            raise ValueError("execution summary must match outcome identifiers")
        if self.status == "completed" and (self.result_id is None or self.output is None):
            raise ValueError("completed execution needs a real result ID and output")
        if self.status == "submitted" and (self.job_id is None or self.cancel_path is None):
            raise ValueError("submitted jobs need an ID and existing cancellation path")
        if self.status == "result_pending" and (self.job_id is None or self.output is None):
            raise ValueError("pending result retrieval needs a real job ID and status")
        if self.status == "submission_unknown" and not self.retry_same_request_id:
            raise ValueError("unknown submission must instruct an idempotent retry")
        if (
            self.status not in {"completed", "submitted", "result_pending", "failed"}
            and self.output is not None
        ):
            raise ValueError("non-executed outcomes cannot claim tool output")
        if self.cancel_path is not None and self.job_id is None:
            raise ValueError("cancellation requires an actual job ID")
        return self
