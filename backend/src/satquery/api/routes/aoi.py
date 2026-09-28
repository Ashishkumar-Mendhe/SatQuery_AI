"""FastAPI routes for Area of Interest (AOI) validation and normalization."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from satquery.api.dependencies import get_app_settings
from satquery.api.schemas.aoi import AoiValidationRequest, AoiValidationResponse
from satquery.core.config import Settings
from satquery.services.aoi_validator import validate_aoi_geometry

router = APIRouter()


@router.post(
    "/validate",
    response_model=AoiValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate an Area of Interest geometry",
    description=(
        "Authoritatively validates an AOI polygon, calculates geodesic area on WGS84, "
        "checks ring closure and self-intersection, and returns normalized GeoJSON."
    ),
)
async def validate_aoi(
    request: AoiValidationRequest,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AoiValidationResponse:
    """Validate and normalize an incoming Area of Interest geometry."""
    return validate_aoi_geometry(
        geometry=request.geometry,
        max_area_km2=settings.max_aoi_square_km,
    )
