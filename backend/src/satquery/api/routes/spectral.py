"""API endpoints for spectral index calculation and evidence extraction."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from satquery.api.dependencies import get_spectral_service
from satquery.api.schemas.spectral import (
    SPECTRAL_SCHEMA_VERSION,
    SpectralIndexRequest,
    SpectralIndexResult,
    SpectralIndicesResponse,
    TemporalSpectralRequest,
    TemporalSpectralResult,
)
from satquery.services.spectral_engine import SpectralCalculationError
from satquery.services.spectral_registry import (
    SpectralRegistry,
    SpectralRegistryError,
)
from satquery.services.spectral_service import SpectralService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Spectral Analysis"])


@router.get(
    "/indices",
    response_model=SpectralIndicesResponse,
    summary="List supported spectral indices",
    description=(
        "Returns all registered spectral indices with mathematical formulas, "
        "required band roles, and descriptions."
    ),
)
async def list_spectral_indices() -> SpectralIndicesResponse:
    """List all registered and supported spectral indices."""
    definitions = SpectralRegistry.get_all_index_definitions()
    return SpectralIndicesResponse(
        indices=definitions,
        total_count=len(definitions),
        version=SPECTRAL_SCHEMA_VERSION,
    )


@router.post(
    "/calculate",
    response_model=SpectralIndexResult,
    summary="Calculate spectral index on prepared raster",
    description=(
        "Calculates a spectral index over an AOI polygon, returning statistics, "
        "evidence items, and map overlay."
    ),
)
async def calculate_spectral_index(
    request: SpectralIndexRequest,
    service: Annotated[SpectralService, Depends(get_spectral_service)],
) -> SpectralIndexResult:
    """Execute single-scene spectral index calculation."""
    try:
        return service.calculate_single(request)
    except (SpectralCalculationError, SpectralRegistryError) as exc:
        logger.warning("Spectral calculation error: %s - %s", exc.code, exc.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": exc.message, "details": exc.details},
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected failure during spectral calculation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Failed to calculate spectral index."},
        ) from exc


@router.post(
    "/calculate-temporal",
    response_model=TemporalSpectralResult,
    summary="Calculate spectral index on temporal pair",
    description=(
        "Calculates a spectral index independently on Before and After prepared "
        "rasters for side-by-side comparison."
    ),
)
async def calculate_temporal_spectral_index(
    request: TemporalSpectralRequest,
    service: Annotated[SpectralService, Depends(get_spectral_service)],
) -> TemporalSpectralResult:
    """Execute bi-temporal spectral index calculation."""
    try:
        return service.calculate_temporal(request)
    except (SpectralCalculationError, SpectralRegistryError) as exc:
        logger.warning("Temporal spectral error: %s - %s", exc.code, exc.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": exc.message, "details": exc.details},
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected failure during temporal spectral calculation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Failed to calculate temporal spectral index.",
            },
        ) from exc


@router.get(
    "/results/{result_id}",
    response_model=SpectralIndexResult,
    summary="Retrieve spectral calculation result",
    description=(
        "Fetches cached spectral statistics, evidence items, and overlay metadata by result ID."
    ),
)
async def get_spectral_result(
    result_id: str,
    service: Annotated[SpectralService, Depends(get_spectral_service)],
) -> SpectralIndexResult:
    """Retrieve spectral index result by ID."""
    try:
        return service.get_result(result_id)
    except SpectralCalculationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message, "details": exc.details},
        ) from exc


@router.get(
    "/results/{result_id}/overlay",
    summary="Get spectral PNG overlay image",
    description="Streams colormapped RGBA PNG preview with transparency for map visualization.",
)
async def get_spectral_overlay_image(
    result_id: str,
    service: Annotated[SpectralService, Depends(get_spectral_service)],
) -> Response:
    """Stream colormapped PNG overlay directly."""
    try:
        result = service.get_result(result_id)
        if not result.preview_asset_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PREVIEW_NOT_FOUND",
                    "message": "No preview asset available for this result.",
                },
            )
        png_bytes, mime_type, _ = service.asset_store.get_asset_bytes(result.preview_asset_id)
        return Response(
            content=png_bytes,
            media_type=mime_type,
            headers={"Cache-Control": "public, max-age=1800"},
        )
    except SpectralCalculationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message, "details": exc.details},
        ) from exc
