"""API endpoints for pixel-level change detection and change evidence generation."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from satquery.api.dependencies import get_change_service
from satquery.api.schemas.change import (
    CHANGE_SCHEMA_VERSION,
    ChangeDetectionRequest,
    ChangeDetectionResult,
    ChangeMethodsResponse,
)
from satquery.services.change_engine import ChangeCalculationError
from satquery.services.change_registry import ChangeRegistry, ChangeRegistryError
from satquery.services.change_service import ChangeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/change", tags=["change-detection"])


@router.get(
    "/methods",
    response_model=ChangeMethodsResponse,
    summary="List supported change detection methods",
    description=(
        "Returns all registered pixel-level change detection methods with "
        "formulas, directionality, and threshold options."
    ),
)
async def list_change_methods() -> ChangeMethodsResponse:
    """List all registered change detection methods."""
    methods = ChangeRegistry.get_all_method_definitions()
    return ChangeMethodsResponse(
        methods=methods,
        total_count=len(methods),
        version=CHANGE_SCHEMA_VERSION,
    )


@router.post(
    "/calculate",
    response_model=ChangeDetectionResult,
    summary="Calculate pixel-level change on temporal pair",
    description=(
        "Executes pixel-by-pixel change detection across a co-registered temporal pair, "
        "returning classified areas, metrics, candidate change regions, and map overlays."
    ),
)
async def calculate_change(
    request: ChangeDetectionRequest,
    service: Annotated[ChangeService, Depends(get_change_service)],
) -> ChangeDetectionResult:
    """Calculate pixel-level change on a prepared temporal pair."""
    try:
        return service.calculate_change(request)
    except (ChangeCalculationError, ChangeRegistryError) as exc:
        logger.warning("Change calculation error: %s - %s", exc.code, exc.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": exc.message, "details": exc.details},
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected failure during change calculation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Failed to calculate change detection."},
        ) from exc


@router.get(
    "/results/{result_id}",
    response_model=ChangeDetectionResult,
    summary="Retrieve change detection result",
    description=(
        "Fetches cached change metrics, vectorized regions, and overlay metadata by result ID."
    ),
)
async def get_change_result(
    result_id: str,
    service: Annotated[ChangeService, Depends(get_change_service)],
) -> ChangeDetectionResult:
    """Retrieve change detection result by ID."""
    try:
        return service.get_result(result_id)
    except ChangeCalculationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message, "details": exc.details},
        ) from exc


@router.get(
    "/results/{result_id}/overlay",
    summary="Stream change detection map overlay PNG",
    description=(
        "Returns transparent 8-bit RGBA PNG preview of continuous difference or discrete mask."
    ),
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Transparent map preview PNG overlay.",
        }
    },
)
async def get_change_overlay(
    result_id: str,
    service: Annotated[ChangeService, Depends(get_change_service)],
    classified: bool = Query(
        default=False, description="Return discrete classified mask instead of continuous"
    ),
) -> Response:
    """Stream map preview PNG for a change detection result."""
    try:
        result = service.get_result(result_id)
        asset_id = result.classified_preview_asset_id if classified else result.preview_asset_id
        if not asset_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "OVERLAY_NOT_FOUND",
                    "message": "Overlay asset not generated for this result.",
                },
            )
        png_bytes, content_type, _ = service.asset_store.get_asset_bytes(asset_id)
        return Response(
            content=png_bytes,
            media_type=content_type or "image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except ChangeCalculationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message, "details": exc.details},
        ) from exc
