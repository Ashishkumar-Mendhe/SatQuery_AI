"""Owner-scoped 10D reference resolution over durable selection/result context."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from satquery.agent.execution import GeoAgentServices, execute_message
from satquery.api.schemas.change import ChangeAnalysisApiResult
from satquery.api.schemas.geoagent import GeoAgentMessageRequest, SelectedGeoScene
from satquery.api.schemas.geoagent_conversation import (
    ConversationSelection,
    ConversationState,
    ConversationToolReference,
    ConversationTurnRequest,
    ConversationTurnResponse,
    VerifiedAnalysisReference,
    verified_reference,
)
from satquery.db.geoagent_conversations import ConversationRepository
from satquery.db.processing import ProcessingPrincipal


@dataclass(frozen=True, slots=True)
class ResolvedTurn:
    message: str | None
    scenes: list[SelectedGeoScene]
    missing: str | None = None
    explanation: str | None = None
    show_change: bool = False


def _same_selection(left: ConversationSelection, right: ConversationSelection) -> bool:
    return left.model_dump(mode="json") == right.model_dump(mode="json")


def _update_selection(state: ConversationState, selection: ConversationSelection) -> None:
    if _same_selection(state.selection, selection):
        return
    if state.selection.aoi != selection.aoi:
        state.earlier_optical_scenes = []
    else:
        known = {scene.source.model_dump_json(): scene for scene in state.earlier_optical_scenes}
        for scene in state.selection.scenes:
            if scene.modality == "optical" and scene.acquired_at is not None:
                known[scene.source.model_dump_json()] = scene
        selected = {scene.source.model_dump_json() for scene in selection.scenes}
        state.earlier_optical_scenes = [
            scene for key, scene in known.items() if key not in selected
        ][-8:]
    state.selection = selection
    state.selection_revision += 1
    state.last_verified = None
    state.tool_references = []
    state.last_intent = None


async def _refresh_latest_result(
    state: ConversationState, principal: ProcessingPrincipal, services: GeoAgentServices
) -> None:
    """Promote only a committed owner-authorized job result, never a queued reference."""
    if not state.tool_references:
        return
    reference = state.tool_references[-1]
    if reference.status not in {"submitted", "result_pending"} or reference.job_id is None:
        return
    result_id: UUID | None = None
    job_state: str | None = None
    try:
        async with asyncio.timeout(10.0):
            if reference.tool in {"inference_vqa", "inference_caption", "inference_grounding"}:
                if services.inference is None:
                    return
                inference_status = await services.inference.status(principal, reference.job_id)
                job_state = inference_status.state
                if inference_status.state == "succeeded":
                    result_id = next(
                        (
                            artifact.artifact_id
                            for artifact in inference_status.artifacts
                            if artifact.kind == "inference_evidence"
                        ),
                        None,
                    )
            elif reference.tool == "optical_change":
                if services.processing is None:
                    return
                change_status = await services.processing.change_status(principal, reference.job_id)
                job_state = change_status.state
                if change_status.state == "succeeded":
                    change_result = ChangeAnalysisApiResult.model_validate(
                        await services.processing.change_result(principal, reference.job_id)
                    )
                    result_id = change_result.classification_artifact_id
            elif reference.tool == "optical_sar_observation":
                if services.optical_sar is None:
                    return
                sar_status = await services.optical_sar.status(principal, reference.job_id)
                job_state = sar_status.state
                if sar_status.state == "succeeded":
                    sar_result = await services.optical_sar.result(principal, reference.job_id)
                    result_id = sar_result.evidence_artifact_id
            else:
                return
    except (TimeoutError, ValueError, RuntimeError):
        return  # Preserve unknown/pending state; no fabricated completion.
    if job_state in {"failed", "cancelled"}:
        reference.status = "failed"
        return
    if job_state == "succeeded" and result_id is None:
        reference.status = "result_pending"
        return
    if result_id is None or reference.aoi_sha256 is None:
        return
    if reference.tool not in {
        "inference_vqa",
        "inference_caption",
        "inference_grounding",
        "optical_change",
        "optical_sar_observation",
    }:
        return
    state.last_verified = VerifiedAnalysisReference(
        tool=reference.tool,
        job_id=reference.job_id,
        result_id=result_id,
        aoi_sha256=reference.aoi_sha256,
        source_scenes=reference.source_scenes,
        verified_at=datetime.now(UTC),
    )
    reference.status = "completed"
    reference.result_id = result_id


def resolve_turn(state: ConversationState, message: str) -> ResolvedTurn:
    """Resolve only named, unique references; never substitute an invented input."""
    normalized = message.strip().lower()
    scenes = state.selection.scenes
    if re.search(r"\bshow\b.*\b(that|the)\b.*\bchange\b.*\bmap\b", normalized):
        reference = state.last_verified
        if reference is None or reference.tool != "optical_change":
            return ResolvedTurn(None, scenes, "change_result", "Which verified change result?")
        return ResolvedTurn(None, scenes, show_change=True)
    if re.search(r"\bcompare\b.*\b(earlier|previous)\s+image\b", normalized):
        optical = [scene for scene in scenes if scene.modality == "optical"]
        if len(optical) == 2 and all(scene.acquired_at for scene in optical):
            ordered = sorted(
                optical, key=lambda scene: scene.acquired_at or datetime.min.replace(tzinfo=UTC)
            )
            if ordered[0].acquired_at != ordered[1].acquired_at:
                return ResolvedTurn("What changed between these images?", ordered)
        if len(optical) == 1 and optical[0].acquired_at is not None:
            candidates = [
                scene
                for scene in state.earlier_optical_scenes
                if scene.acquired_at is not None and scene.acquired_at < optical[0].acquired_at
            ]
            if len(candidates) == 1:
                return ResolvedTurn(
                    "What changed between these images?", [candidates[0], optical[0]]
                )
        return ResolvedTurn(
            None,
            scenes,
            "earlier_scene",
            "Select or identify one earlier dated optical image to compare.",
        )
    if re.search(r"\bwhat about this area\b", normalized):
        if state.selection.aoi is None:
            return ResolvedTurn(None, scenes, "aoi", "Select the area you mean first.")
        if state.last_intent == "before_after_change":
            return ResolvedTurn("What changed in this area?", scenes)
        if state.last_intent == "optical_sar_observation":
            return ResolvedTurn("Summarize optical and SAR observations.", scenes)
        if state.last_intent == "image_caption":
            return ResolvedTurn("Describe this image.", scenes)
        if state.last_intent == "single_image_question":
            return ResolvedTurn("What is visible in this image?", scenes)
        return ResolvedTurn(None, scenes, "intent", "What would you like to inspect in this area?")
    if re.search(r"\b(this|that|it|earlier|previous)\b", normalized) and not re.search(
        r"\b(this area|this image|that image)\b", normalized
    ):
        return ResolvedTurn(
            None, scenes, "intent", "Please name the scene, feature, or result you mean."
        )
    return ResolvedTurn(message, scenes)


def _turn_response(
    state: ConversationState,
    request: ConversationTurnRequest,
    status: str,
    message: str,
    *,
    missing: str | None = None,
    execution: object | None = None,
    show_change: bool = False,
) -> ConversationTurnResponse:
    from satquery.api.schemas.geoagent_execution import GeoAgentExecutionResponse

    return ConversationTurnResponse.model_validate(
        {
            "conversation_id": state.conversation_id,
            "request_id": request.request_id,
            "status": status,
            "message": message,
            "selection_revision": state.selection_revision,
            "selection": state.selection,
            "missing_reference": missing,
            "resolved_result": state.last_verified if show_change else None,
            "execution": execution if isinstance(execution, GeoAgentExecutionResponse) else None,
        }
    )


class ConversationConflictError(RuntimeError):
    pass


async def execute_conversation_turn(
    conversation_id: UUID,
    turn: ConversationTurnRequest,
    principal: ProcessingPrincipal,
    repository: ConversationRepository,
    services: GeoAgentServices,
) -> ConversationTurnResponse:
    stored = await repository.get(principal, conversation_id)
    state = (
        stored.state.model_copy(deep=True)
        if stored
        else ConversationState(conversation_id=conversation_id)
    )
    if state.selection_revision != turn.expected_selection_revision:
        raise ConversationConflictError(
            "Conversation selection changed; reload the current selection before retrying."
        )
    if turn.selection is None or _same_selection(state.selection, turn.selection):
        await _refresh_latest_result(state, principal, services)
    if turn.selection is not None:
        _update_selection(state, turn.selection)
    resolved = resolve_turn(state, turn.message)
    if not await repository.save(principal, state, stored.version if stored else 0):
        raise ConversationConflictError("Conversation changed; retry with the current selection.")
    reserved_revision = state.selection_revision
    if resolved.missing is not None:
        return _turn_response(
            state,
            turn,
            "clarification_required",
            resolved.explanation or "Please clarify.",
            missing=resolved.missing,
        )
    if resolved.show_change:
        return _turn_response(
            state,
            turn,
            "unavailable",
            "The verified change result is identified, but map control is not connected yet.",
            show_change=True,
        )
    assert resolved.message is not None
    effective = GeoAgentMessageRequest(
        request_id=turn.request_id,
        conversation_id=conversation_id,
        message=resolved.message,
        selected_aoi=state.selection.aoi,
        selected_scenes=resolved.scenes,
    )
    outcome = await execute_message(effective, principal, services)
    latest = await repository.get(principal, conversation_id)
    if (
        latest is None
        or latest.state.selection_revision != reserved_revision
        or not _same_selection(latest.state.selection, state.selection)
    ):
        return _turn_response(
            state,
            turn,
            "stale",
            "The selection changed while this request ran; its result was not attached.",
        )
    updated = latest.state.model_copy(deep=True)
    if outcome.summary.intended_analysis is not None and outcome.status in {
        "submitted",
        "result_pending",
        "completed",
    }:
        updated.last_intent = outcome.summary.intended_analysis
    if outcome.summary.tool is not None:
        updated.tool_references = [
            reference
            for reference in updated.tool_references
            if reference.request_id != turn.request_id
        ]
        if outcome.status in {"submitted", "result_pending", "completed", "failed", "unavailable"}:
            updated.tool_references.append(
                ConversationToolReference(
                    request_id=turn.request_id,
                    tool=outcome.summary.tool,
                    job_id=outcome.job_id,
                    result_id=outcome.result_id,
                    status=outcome.status,
                    aoi_sha256=outcome.summary.aoi_sha256,
                    source_scenes=outcome.summary.input_scenes,
                )
            )
            updated.tool_references = updated.tool_references[-8:]
    verified = verified_reference(outcome)
    if verified is not None:
        updated.last_verified = verified
    if not await repository.save(principal, updated, latest.version):
        return _turn_response(
            state,
            turn,
            "stale",
            "Conversation changed; the result was not attached.",
        )
    return _turn_response(updated, turn, "executed", outcome.message, execution=outcome)
