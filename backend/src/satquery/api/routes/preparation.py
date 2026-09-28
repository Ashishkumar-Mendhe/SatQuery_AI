"""API routes for raster harmonization, reprojection, and analysis preparation."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from satquery.api.dependencies import get_preparation_service
from satquery.api.schemas.preparation import (
    PreparedRasterAsset,
    PreparedTemporalPair,
    RasterPreparationRequest,
    TemporalRasterPreparationRequest,
)
from satquery.services.asset_store import AssetNotFoundError
from satquery.services.preparation_service import PreparationService
from satquery.services.raster_harmonizer import HarmonizationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/processing", tags=["Raster Processing & Preparation"])
PreparationServiceDependency = Annotated[PreparationService, Depends(get_preparation_service)]


@router.post(
    "/prepare-raster",
    response_model=PreparedRasterAsset,
    status_code=status.HTTP_200_OK,
    summary="Harmonise, reproject, and clip a single analysis raster",
)
async def prepare_single_raster(
    request: RasterPreparationRequest,
    service: PreparationServiceDependency,
) -> PreparedRasterAsset:
    """Reproject an analysis raster to metric CRS, clip to AOI, and mask invalid pixels."""
    try:
        return service.prepare_single_raster(request)
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except HarmonizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": exc.message, "details": exc.details},
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in prepare_single_raster: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "RASTER_PREPARATION_FAILED",
                "message": "An internal error occurred while preparing the raster.",
            },
        ) from exc


@router.post(
    "/prepare-temporal-pair",
    response_model=PreparedTemporalPair,
    status_code=status.HTTP_200_OK,
    summary="Harmonise, reproject, and grid-align a multitemporal raster pair",
)
async def prepare_temporal_pair(
    request: TemporalRasterPreparationRequest,
    service: PreparationServiceDependency,
) -> PreparedTemporalPair:
    """Align two temporal analysis rasters onto an identical metric analysis grid."""
    try:
        return service.prepare_temporal_pair(request)
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except HarmonizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": exc.message, "details": exc.details},
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in prepare_temporal_pair: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "TEMPORAL_PREPARATION_FAILED",
                "message": "An internal error occurred while harmonizing the temporal pair.",
            },
        ) from exc
