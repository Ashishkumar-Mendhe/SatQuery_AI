"""API endpoints for multimodal optical and SAR evidence fusion."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from satquery.api.dependencies import get_fusion_service
from satquery.api.schemas.fusion import (
    FusionCapabilitiesResponse,
    FusionRequest,
    FusionResult,
)
from satquery.services.fusion_engine import FusionCalculationError
from satquery.services.fusion_service import FusionService
from satquery.services.sar_engine import SARCalculationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fusion", tags=["evidence-fusion"])


@router.get(
    "/capabilities",
    response_model=FusionCapabilitiesResponse,
    summary="List supported evidence fusion capabilities and rules",
    description=(
        "Returns registered multimodal fusion rules, supported SAR polarizations, "
        "and radiometric backscatter coefficients."
    ),
)
async def get_fusion_capabilities(
    service: Annotated[FusionService, Depends(get_fusion_service)],
) -> FusionCapabilitiesResponse:
    """List fusion capabilities and rules."""
    return service.get_capabilities()


@router.post(
    "/analyze",
    response_model=FusionResult,
    summary="Perform multimodal optical and SAR evidence fusion",
    description=(
        "Executes deterministic evidence fusion combining optical change detection and calibrated SAR "
        "backscatter differencing across co-registered spatial domains and validated observation windows."
    ),
)
async def analyze_multimodal_fusion(
    request: FusionRequest,
    service: Annotated[FusionService, Depends(get_fusion_service)],
) -> FusionResult:
    """Execute evidence-level optical and SAR fusion."""
    try:
        return service.calculate_fusion(request)
    except (FusionCalculationError, SARCalculationError) as exc:
        logger.warning("Fusion calculation error: %s - %s", exc.code, exc.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": exc.message, "details": exc.details},
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during evidence fusion: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Failed to execute multimodal evidence fusion.",
            },
        ) from exc


@router.get(
    "/results/{result_id}",
    response_model=FusionResult,
    summary="Retrieve multimodal fusion result",
    description=(
        "Fetches cached fusion result including joint observation metrics, coverage partitions, "
        "vectorized fused regions, and 4-role timeline."
    ),
)
async def get_fusion_result(
    result_id: str,
    service: Annotated[FusionService, Depends(get_fusion_service)],
) -> FusionResult:
    """Retrieve fusion result by ID."""
    result = service.get_result(result_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "FUSION_RESULT_NOT_FOUND",
                "message": f"Result '{result_id}' not found.",
            },
        )
    return result


@router.get(
    "/results/{result_id}/overlay",
    summary="Stream fusion map overlay PNG",
    description="Returns transparent 8-bit RGBA PNG preview of discrete 5-state joint classification mask.",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Transparent map preview PNG overlay.",
        }
    },
)
async def get_fusion_overlay(
    result_id: str,
    service: Annotated[FusionService, Depends(get_fusion_service)],
) -> Response:
    """Stream map preview PNG for a fusion result."""
    result = service.get_result(result_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "FUSION_RESULT_NOT_FOUND",
                "message": f"Result '{result_id}' not found.",
            },
        )
    if not result.classified_overlay:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "OVERLAY_NOT_FOUND",
                "message": "Overlay not generated for this result.",
            },
        )
    # Look for registered preview in asset store
    matching_assets = [k for k in service.asset_store._assets.keys() if "fusion-preview-" in k]
    if matching_assets:
        png_bytes, content_type, _ = service.asset_store.get_asset_bytes(matching_assets[-1])
        return Response(
            content=png_bytes,
            media_type=content_type or "image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "OVERLAY_NOT_FOUND", "message": "Overlay asset bytes not found."},
    )
