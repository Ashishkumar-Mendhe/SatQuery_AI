"""Small allow-listed Phase 10C executor over existing authorized service methods."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError, model_validator

from satquery.agent.routing import route_message
from satquery.api.schemas.catalog import CatalogGeometry
from satquery.api.schemas.change import ChangeAnalysisApiResult
from satquery.api.schemas.geoagent import (
    GeoAgentMessageRequest,
    GeoAgentMessageResponse,
    GeoTool,
)
from satquery.api.schemas.geoagent_execution import (
    GeoAgentExecutionResponse,
    GeoAgentExecutionSummary,
)
from satquery.api.schemas.optical_sar import OpticalSarAnalysisRequest
from satquery.api.schemas.processing import PreparationRequest
from satquery.api.schemas.viewer import StrictViewerModel, TileMetadataRequest, ViewerSceneIdentity
from satquery.api.schemas.vqa import InferenceSubmissionRequest
from satquery.db.processing import (
    IdempotencyConflictError,
    ProcessingPersistenceError,
    ProcessingPrincipal,
)
from satquery.inference.jobs import InferenceJobError, InferenceJobService
from satquery.processing.jobs import PreparationJobError, PreparationJobService
from satquery.processing.optical_sar_jobs import OpticalSarJobError, OpticalSarJobService
from satquery.providers.catalog import CatalogueProvider, CatalogueProviderError
from satquery.tiles import ImageryTileService, TileServiceError

OPTICAL_SAR_SUMMARY_QUESTION = "Summarize the separate optical and SAR observations."


class MapActionInput(StrictViewerModel):
    action: Literal["draw_aoi", "zoom_to_aoi", "clear_aoi"]
    aoi: CatalogGeometry | None = None

    @model_validator(mode="after")
    def require_existing_aoi(self) -> MapActionInput:
        if self.action != "draw_aoi" and self.aoi is None:
            raise ValueError("zoom/clear requires a selected AOI")
        return self


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: GeoTool
    input_schema: type[BaseModel]
    scene_count: int
    requires_aoi: bool
    submit_timeout_seconds: float
    cancellable: bool


TOOL_REGISTRY: dict[GeoTool, ToolSpec] = {
    "imagery_tiles": ToolSpec("imagery_tiles", TileMetadataRequest, 1, False, 12.0, False),
    "inference_vqa": ToolSpec("inference_vqa", InferenceSubmissionRequest, 1, True, 15.0, True),
    "inference_caption": ToolSpec(
        "inference_caption", InferenceSubmissionRequest, 1, True, 15.0, True
    ),
    "inference_grounding": ToolSpec(
        "inference_grounding", InferenceSubmissionRequest, 1, True, 15.0, True
    ),
    "optical_change": ToolSpec("optical_change", PreparationRequest, 2, True, 20.0, True),
    "optical_sar_observation": ToolSpec(
        "optical_sar_observation", OpticalSarAnalysisRequest, 2, True, 20.0, True
    ),
    "map_aoi_control": ToolSpec("map_aoi_control", MapActionInput, 0, False, 2.0, False),
}


@dataclass(frozen=True, slots=True)
class GeoAgentServices:
    inference: InferenceJobService | None = None
    processing: PreparationJobService | None = None
    optical_sar: OpticalSarJobService | None = None
    imagery: ImageryTileService | None = None
    catalogue: CatalogueProvider | None = None
    public_imagery_scope: str = "public:earth-search"


def _outcome(
    request: GeoAgentMessageRequest,
    plan: GeoAgentMessageResponse,
    status: Literal[
        "submitted",
        "result_pending",
        "completed",
        "failed",
        "unavailable",
        "clarification_required",
        "unsupported",
        "submission_unknown",
    ],
    message: str,
    *,
    job_id: UUID | None = None,
    result_id: UUID | None = None,
    output: dict[str, Any] | None = None,
    cancel_path: str | None = None,
    error_code: str | None = None,
    retry_same_request_id: bool = False,
) -> GeoAgentExecutionResponse:
    aoi_digest = None
    if request.selected_aoi is not None:
        canonical_aoi = request.selected_aoi.model_dump(mode="json")
        aoi_digest = hashlib.sha256(
            json.dumps(canonical_aoi, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    summary = GeoAgentExecutionSummary(
        intended_analysis=plan.intended_analysis,
        tool=plan.proposed_tool,
        input_scenes=plan.ordered_source_scenes,
        aoi_sha256=aoi_digest,
        status=status,
        job_id=job_id,
        result_id=result_id,
    )
    return GeoAgentExecutionResponse(
        request_id=request.request_id,
        conversation_id=request.conversation_id,
        status=status,
        summary=summary,
        job_id=job_id,
        result_id=result_id,
        output=output,
        cancel_path=cancel_path,
        error_code=error_code,
        message=message,
        retry_same_request_id=retry_same_request_id,
    )


def _input(plan: GeoAgentMessageResponse, request: GeoAgentMessageRequest) -> BaseModel:
    tool = plan.proposed_tool
    if tool is None:
        raise ValueError("no tool was selected")
    spec = TOOL_REGISTRY[tool]
    if len(plan.ordered_source_scenes) != spec.scene_count:
        raise ValueError("selected scene count does not match the tool")
    if spec.requires_aoi and request.selected_aoi is None:
        raise ValueError("selected AOI is required")
    sources = plan.ordered_source_scenes
    if tool == "imagery_tiles":
        return TileMetadataRequest(scene=sources[0])
    if tool in {"inference_vqa", "inference_caption", "inference_grounding"}:
        operation = {
            "inference_vqa": "visual_question_answering",
            "inference_caption": "image_captioning",
            "inference_grounding": "referring_grounding",
        }[tool]
        return InferenceSubmissionRequest.model_validate(
            {
                "request_id": request.request_id,
                "operation": operation,
                "scene": sources[0].model_dump(mode="json"),
                "aoi": request.selected_aoi.model_dump(mode="json")
                if request.selected_aoi
                else None,
                "text": request.message if tool != "inference_caption" else None,
            }
        )
    if tool == "optical_change":
        return PreparationRequest.model_validate(
            {
                "scenes": [source.model_dump(mode="json") for source in sources],
                "aoi": request.selected_aoi.model_dump(mode="json")
                if request.selected_aoi
                else None,
                "required_bands": [
                    {"role": role, "common_name": role} for role in ("red", "green", "blue")
                ],
                "intended_task": "optical_pair",
                "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
                "options": {
                    "grid_policy": "common_utm",
                    "target_resolution_metres": 10.0,
                    "continuous_resampling": "bilinear",
                    "max_output_pixels": 100_000,
                },
            }
        )
    if tool == "optical_sar_observation":
        sar = next(scene for scene in request.selected_scenes if scene.modality == "sar")
        return OpticalSarAnalysisRequest.model_validate(
            {
                "request_id": request.request_id,
                "optical_scene": sources[0].model_dump(mode="json"),
                "sar_scene": sources[1].model_dump(mode="json"),
                "aoi": request.selected_aoi.model_dump(mode="json")
                if request.selected_aoi
                else None,
                "polarization": sar.polarization,
                "target_resolution_metres": 20.0,
                "question": OPTICAL_SAR_SUMMARY_QUESTION,
            }
        )
    if tool == "map_aoi_control":
        return MapActionInput.model_validate(
            {
                "action": plan.map_action,
                "aoi": request.selected_aoi.model_dump(mode="json")
                if request.selected_aoi
                else None,
            }
        )
    raise ValueError("tool is not in the allow-list")


async def _real_change_order(
    catalogue: CatalogueProvider | None, sources: list[ViewerSceneIdentity], deadline_seconds: float
) -> bool | None:
    if catalogue is None:
        return None
    first, second = sources
    async with asyncio.timeout(deadline_seconds):
        before = await catalogue.item(first.collection, first.item)
        after = await catalogue.item(second.collection, second.item)
    if (
        before.provider.id != first.provider
        or before.provider_asset_id != first.item
        or after.provider.id != second.provider
        or after.provider_asset_id != second.item
    ):
        return False
    return before.acquisition.start < after.acquisition.start


async def execute_message(
    request: GeoAgentMessageRequest,
    principal: ProcessingPrincipal,
    services: GeoAgentServices,
) -> GeoAgentExecutionResponse:
    """Route server-side, validate tool arguments, then call one trusted service once."""

    plan = route_message(request)
    if plan.status != "plan_ready":
        return _outcome(request, plan, plan.status, plan.answer)
    tool = plan.proposed_tool
    assert tool is not None
    spec = TOOL_REGISTRY[tool]
    if tool == "map_aoi_control":
        return _outcome(
            request,
            plan,
            "unavailable",
            "Map control is not connected to the backend executor.",
            error_code="TOOL_UNAVAILABLE",
        )
    try:
        payload = _input(plan, request)
    except (ValidationError, ValueError):
        return _outcome(
            request,
            plan,
            "unsupported",
            "The requested tool input is invalid or exceeds its bounded contract.",
            error_code="INVALID_TOOL_INPUT",
        )
    key = f"geoagent.{tool.replace('_', '-')}.{request.request_id}"
    try:
        if tool == "imagery_tiles":
            if services.imagery is None:
                return _outcome(
                    request,
                    plan,
                    "unavailable",
                    "Imagery tile service is unavailable.",
                    error_code="TOOL_UNAVAILABLE",
                )
            async with asyncio.timeout(spec.submit_timeout_seconds):
                metadata = await services.imagery.metadata(
                    cast(TileMetadataRequest, payload), access_scope=services.public_imagery_scope
                )
            if metadata.access.state != "available":
                return _outcome(
                    request,
                    plan,
                    "unavailable",
                    metadata.access.reason or "Imagery access is unavailable.",
                    error_code="IMAGERY_UNAVAILABLE",
                )
            return _outcome(
                request,
                plan,
                "completed",
                "Trusted imagery tile metadata is available; display pixels are not "
                "analytical input.",
                result_id=metadata.tile_set_id,
                output=metadata.model_dump(mode="json"),
            )
        if tool in {"inference_vqa", "inference_caption", "inference_grounding"}:
            if services.inference is None:
                return _outcome(
                    request,
                    plan,
                    "unavailable",
                    "Protected inference jobs are unavailable.",
                    error_code="TOOL_UNAVAILABLE",
                )
            async with asyncio.timeout(spec.submit_timeout_seconds):
                record = await services.inference.submit(
                    principal, cast(InferenceSubmissionRequest, payload), idempotency_key=key
                )
                inference_status = await services.inference.status(principal, record.job_id)
            return _job_outcome(
                request,
                plan,
                inference_status.state,
                inference_status.job_id,
                inference_status.model_dump(mode="json"),
                inference_status.safe_error_message,
                inference_status.error_code,
                "/api/v1/inference/jobs",
                next(
                    (
                        artifact.artifact_id
                        for artifact in inference_status.artifacts
                        if artifact.kind == "inference_evidence"
                    ),
                    None,
                )
                if inference_status.state == "succeeded"
                else None,
            )
        if tool == "optical_change":
            if services.processing is None or services.catalogue is None:
                return _outcome(
                    request,
                    plan,
                    "unavailable",
                    "Protected change jobs or trusted catalogue access are unavailable.",
                    error_code="TOOL_UNAVAILABLE",
                )
            ordered = await _real_change_order(
                services.catalogue, plan.ordered_source_scenes, spec.submit_timeout_seconds
            )
            if ordered is not True:
                return _outcome(
                    request,
                    plan,
                    "unsupported",
                    "Trusted acquisition dates do not establish the selected before/after order.",
                    error_code="DATE_ORDER_UNVERIFIED",
                )
            async with asyncio.timeout(spec.submit_timeout_seconds):
                record = await services.processing.submit_change(
                    principal, cast(PreparationRequest, payload), idempotency_key=key
                )
                change_status = await services.processing.change_status(principal, record.job_id)
            result_id: UUID | None = None
            output = change_status.model_dump(mode="json")
            if change_status.state == "succeeded":
                try:
                    async with asyncio.timeout(spec.submit_timeout_seconds):
                        actual = ChangeAnalysisApiResult.model_validate(
                            await services.processing.change_result(principal, change_status.job_id)
                        )
                except TimeoutError:
                    return _outcome(
                        request,
                        plan,
                        "result_pending",
                        "The job succeeded, but its committed result could not be retrieved yet.",
                        job_id=change_status.job_id,
                        output=output,
                        error_code="RESULT_READ_TIMEOUT",
                    )
                result_id = actual.classification_artifact_id
                output = actual.model_dump(mode="json")
            return _job_outcome(
                request,
                plan,
                change_status.state,
                change_status.job_id,
                output,
                change_status.safe_error_message,
                change_status.error_code,
                "/api/v1/processing/change-jobs",
                result_id,
            )
        if tool == "optical_sar_observation":
            if services.optical_sar is None:
                return _outcome(
                    request,
                    plan,
                    "unavailable",
                    "Protected optical/SAR jobs are unavailable.",
                    error_code="TOOL_UNAVAILABLE",
                )
            async with asyncio.timeout(spec.submit_timeout_seconds):
                record = await services.optical_sar.submit(
                    principal, cast(OpticalSarAnalysisRequest, payload), idempotency_key=key
                )
                sar_status = await services.optical_sar.status(principal, record.job_id)
            result_id = None
            output = sar_status.model_dump(mode="json")
            if sar_status.state == "succeeded":
                try:
                    async with asyncio.timeout(spec.submit_timeout_seconds):
                        actual_sar = await services.optical_sar.result(principal, sar_status.job_id)
                except TimeoutError:
                    return _outcome(
                        request,
                        plan,
                        "result_pending",
                        "The job succeeded, but its committed result could not be retrieved yet.",
                        job_id=sar_status.job_id,
                        output=output,
                        error_code="RESULT_READ_TIMEOUT",
                    )
                result_id = actual_sar.evidence_artifact_id
                output = actual_sar.model_dump(mode="json")
            return _job_outcome(
                request,
                plan,
                sar_status.state,
                sar_status.job_id,
                output,
                sar_status.safe_error_message,
                sar_status.error_code,
                "/api/v1/optical-sar/jobs",
                result_id,
            )
    except TimeoutError:
        return _outcome(
            request,
            plan,
            "submission_unknown",
            "Tool submission or status timed out; retry with the same request ID to "
            "avoid duplication.",
            error_code="TOOL_TIMEOUT",
            retry_same_request_id=True,
        )
    except (InferenceJobError, PreparationJobError, OpticalSarJobError, TileServiceError) as exc:
        return _outcome(
            request,
            plan,
            "failed",
            "The selected tool rejected or could not process this request.",
            error_code=exc.code.upper(),
        )
    except (CatalogueProviderError, ProcessingPersistenceError):
        return _outcome(
            request,
            plan,
            "unavailable",
            "A trusted provider or durable job dependency is unavailable.",
            error_code="DEPENDENCY_UNAVAILABLE",
        )
    except IdempotencyConflictError:
        return _outcome(
            request,
            plan,
            "failed",
            "This request ID was previously used with different inputs.",
            error_code="IDEMPOTENCY_CONFLICT",
        )
    except Exception:
        return _outcome(
            request,
            plan,
            "failed",
            "The selected tool failed safely; no analysis result is claimed.",
            error_code="TOOL_FAILED",
        )
    return _outcome(
        request,
        plan,
        "unsupported",
        "No executor exists for this tool.",
        error_code="TOOL_UNSUPPORTED",
    )


def _job_outcome(
    request: GeoAgentMessageRequest,
    plan: GeoAgentMessageResponse,
    state: str,
    job_id: UUID,
    output: dict[str, Any],
    safe_error: str | None,
    error_code: str | None,
    path: str,
    result_id: UUID | None,
) -> GeoAgentExecutionResponse:
    if state == "succeeded":
        if result_id is None:
            return _outcome(
                request,
                plan,
                "failed",
                "The job reports success but a committed result ID is unavailable.",
                job_id=job_id,
                error_code="RESULT_UNAVAILABLE",
            )
        return _outcome(
            request,
            plan,
            "completed",
            "The existing job returned a committed result; inspect its source-bound output.",
            job_id=job_id,
            result_id=result_id,
            output=output,
        )
    if state in {"failed", "cancelled"}:
        return _outcome(
            request,
            plan,
            "failed",
            safe_error or f"The job ended as {state}.",
            job_id=job_id,
            output=output,
            error_code=(error_code or "JOB_FAILED").upper()
            if state == "failed"
            else "JOB_CANCELLED",
        )
    return _outcome(
        request,
        plan,
        "submitted",
        f"The existing job is {state}; no analysis result is available yet.",
        job_id=job_id,
        output=output,
        cancel_path=f"{path}/{job_id}/cancel",
    )
