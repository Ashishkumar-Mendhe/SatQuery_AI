from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends

from satquery.api.dependencies import get_nisar_ingestion_service, get_nisar_provider
from satquery.api.schemas.nisar import (
    NisarDiscoveryRequest,
    NisarDiscoveryResponse,
    NisarIngestionRequest,
    NisarIngestionResponse,
)
from satquery.core.errors import ApiError
from satquery.processing.nisar import NisarGcovIngestionService
from satquery.providers.catalog.base import CatalogueProviderError
from satquery.providers.catalog.nisar_cmr import NisarCmrProvider

router = APIRouter()
NisarProviderDependency = Annotated[NisarCmrProvider, Depends(get_nisar_provider)]
NisarIngestionDependency = Annotated[
    NisarGcovIngestionService, Depends(get_nisar_ingestion_service)
]


def _raise_provider(error: CatalogueProviderError) -> NoReturn:
    status_code = (
        503 if error.retryable else (404 if error.code == "NISAR_SOURCE_NOT_FOUND" else 422)
    )
    raise ApiError(
        status_code=status_code, code=error.code, message=str(error), retryable=error.retryable
    ) from error


@router.post("/search", response_model=NisarDiscoveryResponse)
async def search_nisar(
    request: NisarDiscoveryRequest, provider: NisarProviderDependency
) -> NisarDiscoveryResponse:
    try:
        return await provider.search(request)
    except CatalogueProviderError as error:
        _raise_provider(error)


@router.post("/ingestions", response_model=NisarIngestionResponse)
async def ingest_nisar(
    request: NisarIngestionRequest, service: NisarIngestionDependency
) -> NisarIngestionResponse:
    try:
        return await service.ingest(request)
    except CatalogueProviderError as error:
        _raise_provider(error)
