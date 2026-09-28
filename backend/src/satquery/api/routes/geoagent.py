"""Protected GeoAgent execution and owner-scoped conversation routes."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from satquery.agent.conversation import ConversationConflictError, execute_conversation_turn
from satquery.agent.execution import GeoAgentServices, execute_message
from satquery.api.dependencies import get_processing_principal
from satquery.api.schemas.geoagent import GeoAgentMessageRequest
from satquery.api.schemas.geoagent_conversation import (
    ConversationState,
    ConversationTurnRequest,
    ConversationTurnResponse,
)
from satquery.api.schemas.geoagent_execution import GeoAgentExecutionResponse
from satquery.core.errors import ApiError
from satquery.db.geoagent_conversations import ConversationPersistenceError, ConversationRepository
from satquery.db.processing import ProcessingPrincipal
from satquery.inference.jobs import InferenceJobService
from satquery.processing.jobs import PreparationJobService
from satquery.processing.optical_sar_jobs import OpticalSarJobService
from satquery.providers.catalog import CatalogueProvider
from satquery.tiles import ImageryTileService

router = APIRouter()
Principal = Annotated[ProcessingPrincipal, Depends(get_processing_principal)]


def _conversation_repository(request: Request) -> ConversationRepository:
    repository = cast(
        ConversationRepository | None,
        getattr(request.app.state, "geoagent_conversation_repository", None),
    )
    if repository is None:
        raise ApiError(
            status_code=503,
            code="CAPABILITY_UNAVAILABLE",
            message="Durable conversation storage is unavailable.",
            retryable=True,
        )
    return repository


@router.post("/execute", response_model=GeoAgentExecutionResponse)
async def execute_geoagent_message(
    message: GeoAgentMessageRequest,
    request: Request,
    principal: Principal,
) -> GeoAgentExecutionResponse:
    services = GeoAgentServices(
        inference=cast(InferenceJobService | None, request.app.state.inference_job_service),
        processing=cast(PreparationJobService | None, request.app.state.processing_job_service),
        optical_sar=cast(OpticalSarJobService | None, request.app.state.optical_sar_job_service),
        imagery=cast(ImageryTileService | None, request.app.state.imagery_tile_service),
        catalogue=cast(CatalogueProvider | None, request.app.state.catalogue_provider),
        public_imagery_scope=f"public:{request.app.state.settings.catalogue_provider}",
    )
    return await execute_message(message, principal, services)


@router.post("/conversations/{conversation_id}/turns", response_model=ConversationTurnResponse)
async def execute_geoagent_conversation_turn(
    conversation_id: UUID,
    turn: ConversationTurnRequest,
    request: Request,
    principal: Principal,
) -> ConversationTurnResponse:
    repository = _conversation_repository(request)
    services = GeoAgentServices(
        inference=cast(InferenceJobService | None, request.app.state.inference_job_service),
        processing=cast(PreparationJobService | None, request.app.state.processing_job_service),
        optical_sar=cast(OpticalSarJobService | None, request.app.state.optical_sar_job_service),
        imagery=cast(ImageryTileService | None, request.app.state.imagery_tile_service),
        catalogue=cast(CatalogueProvider | None, request.app.state.catalogue_provider),
        public_imagery_scope=f"public:{request.app.state.settings.catalogue_provider}",
    )
    try:
        return await execute_conversation_turn(
            conversation_id, turn, principal, repository, services
        )
    except ConversationConflictError as exc:
        raise ApiError(
            status_code=409, code="CONVERSATION_CHANGED", message=str(exc), retryable=True
        ) from exc
    except ConversationPersistenceError as exc:
        raise ApiError(
            status_code=503,
            code="DEPENDENCY_UNAVAILABLE",
            message="Durable conversation storage is unavailable.",
            retryable=True,
        ) from exc


@router.get("/conversations/{conversation_id}", response_model=ConversationState)
async def get_geoagent_conversation(
    conversation_id: UUID, request: Request, principal: Principal
) -> ConversationState:
    try:
        stored = await _conversation_repository(request).get(principal, conversation_id)
    except ConversationPersistenceError as exc:
        raise ApiError(
            status_code=503,
            code="DEPENDENCY_UNAVAILABLE",
            message="Durable conversation storage is unavailable.",
            retryable=True,
        ) from exc
    if stored is None:
        raise ApiError(
            status_code=404,
            code="CONVERSATION_NOT_FOUND",
            message="Conversation not found.",
        )
    return stored.state


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_geoagent_conversation(
    conversation_id: UUID, request: Request, principal: Principal
) -> Response:
    try:
        deleted = await _conversation_repository(request).delete(principal, conversation_id)
    except ConversationPersistenceError as exc:
        raise ApiError(
            status_code=503,
            code="DEPENDENCY_UNAVAILABLE",
            message="Durable conversation storage is unavailable.",
            retryable=True,
        ) from exc
    if not deleted:
        raise ApiError(
            status_code=404,
            code="CONVERSATION_NOT_FOUND",
            message="Conversation not found.",
        )
    return Response(status_code=204)
