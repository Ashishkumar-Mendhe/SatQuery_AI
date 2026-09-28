"""FastAPI routes for Phase 5A natural language query answering and evidence explanations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from satquery.api.dependencies import get_query_service, get_visual_query_service
from satquery.api.schemas.query import (
    QueryAnswer,
    QueryCapabilitiesResponse,
    QueryRequest,
)
from satquery.api.schemas.visual import (
    ImageManifest,
    VisualCapabilitiesResponse,
    VisualQueryRequest,
    VisualQueryResponse,
)
from satquery.services.query_service import QueryService
from satquery.services.visual_query_service import (
    VisualQueryService,
    VisualQueryServiceError,
)

router = APIRouter(prefix="/query", tags=["Query & Natural Language Assistant"])


@router.get(
    "/capabilities",
    response_model=QueryCapabilitiesResponse,
    summary="Get Query Assistant Capabilities",
    description="Lists supported query intents, generation modes, and example questions.",
)
async def get_capabilities(
    query_service: Annotated[QueryService, Depends(get_query_service)],
) -> QueryCapabilitiesResponse:
    return query_service.get_capabilities()


@router.post(
    "/ask",
    response_model=QueryAnswer,
    summary="Ask Natural Language Question",
    description="Routes intent, retrieves active evidence, evaluates sufficiency, generates grounded answer, and returns verifiable claims and map references.",
)
async def ask_query(
    request: QueryRequest,
    query_service: Annotated[QueryService, Depends(get_query_service)],
) -> QueryAnswer:
    try:
        return await query_service.answer_query(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query answering failed: {exc}",
        ) from exc


@router.get(
    "/visual/capabilities",
    response_model=VisualCapabilitiesResponse,
    summary="Get Visual Query Capabilities",
    description="Lists supported visual operations, multi-image comparison support, and bounding box capabilities.",
)
async def get_visual_capabilities(
    visual_service: Annotated[VisualQueryService, Depends(get_visual_query_service)],
) -> VisualCapabilitiesResponse:
    return visual_service.get_capabilities()


@router.post(
    "/visual",
    response_model=VisualQueryResponse,
    summary="Ask Visual Question on Image(s)",
    description="Submits image pixels to vision-capable AI, creates immutable manifests, validates bounding boxes, applies inverse spatial transform to WGS84, and associates with computed evidence.",
)
async def ask_visual_query(
    request: VisualQueryRequest,
    visual_service: Annotated[VisualQueryService, Depends(get_visual_query_service)],
) -> VisualQueryResponse:
    try:
        return await visual_service.ask_visual_query(request)
    except VisualQueryServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=f"Visual query error ({exc.code}): {exc.message}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Visual query execution failed: {exc}",
        ) from exc


@router.get(
    "/manifests/{manifest_id}",
    response_model=ImageManifest,
    summary="Get Immutable Image Manifest",
    description="Retrieves the immutable manifest record of image bytes and georeferencing sent to the model.",
)
async def get_image_manifest(
    manifest_id: str,
    visual_service: Annotated[VisualQueryService, Depends(get_visual_query_service)],
) -> ImageManifest:
    manifest = visual_service.get_manifest(manifest_id)
    if not manifest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image manifest '{manifest_id}' not found.",
        )
    return manifest
