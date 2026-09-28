from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Response

from satquery.api.dependencies import get_sar_provider, get_sar_raster_service
from satquery.api.schemas.sar import (
    SarDiscoveryRequest,
    SarDiscoveryResponse,
    SarPreparationRequest,
    SarPreparationResponse,
)
from satquery.core.errors import ApiError
from satquery.processing.sar import SarProcessingError, SarRasterService
from satquery.providers.catalog.base import CatalogueProviderError
from satquery.providers.catalog.inpe_sar import InpeSarProvider

router = APIRouter()
SarProviderDependency = Annotated[InpeSarProvider, Depends(get_sar_provider)]
SarRasterDependency = Annotated[SarRasterService, Depends(get_sar_raster_service)]


def _raise_provider(error: CatalogueProviderError) -> NoReturn:
    status_code = 503 if error.retryable else (404 if error.code == "SAR_SOURCE_NOT_FOUND" else 422)
    raise ApiError(
        status_code=status_code, code=error.code, message=str(error), retryable=error.retryable
    ) from error


@router.post("/search", response_model=SarDiscoveryResponse)
async def search_sar(
    request: SarDiscoveryRequest, provider: SarProviderDependency
) -> SarDiscoveryResponse:
    try:
        return await provider.search(request)
    except CatalogueProviderError as error:
        _raise_provider(error)


@router.post("/preparations", response_model=SarPreparationResponse)
async def prepare_sar(
    request: SarPreparationRequest, service: SarRasterDependency
) -> SarPreparationResponse:
    try:
        return await service.prepare(request)
    except CatalogueProviderError as error:
        _raise_provider(error)
    except SarProcessingError as error:
        raise ApiError(
            status_code=error.status_code, code=error.code, message=str(error), retryable=False
        ) from error


@router.get("/preparations/{preparation_id}/preview.png", response_class=Response)
async def sar_preview(
    preparation_id: Annotated[UUID, Path()], service: SarRasterDependency
) -> Response:
    try:
        body = service.preview(preparation_id)
    except SarProcessingError as error:
        raise ApiError(
            status_code=error.status_code, code=error.code, message=str(error), retryable=False
        ) from error
    return Response(
        content=body, media_type="image/png", headers={"Cache-Control": "private, max-age=60"}
    )
