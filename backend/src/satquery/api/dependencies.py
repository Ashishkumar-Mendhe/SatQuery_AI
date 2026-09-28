from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import Request

from satquery.core.errors import ApiError
from satquery.db.processing import ProcessingPrincipal
from satquery.db.session import ReadinessDatabase
from satquery.inference.jobs import InferenceJobService
from satquery.processing.jobs import PreparationJobService
from satquery.processing.nisar import NisarGcovIngestionService
from satquery.processing.optical_sar_jobs import OpticalSarJobService
from satquery.processing.sar import SarRasterService
from satquery.providers.catalog import CatalogueProvider
from satquery.providers.catalog.inpe_sar import InpeSarProvider
from satquery.providers.catalog.nisar_cmr import NisarCmrProvider
from satquery.tiles import ImageryTileService


def get_database(request: Request) -> ReadinessDatabase:
    return cast(ReadinessDatabase, request.app.state.database)


def get_catalogue_provider(request: Request) -> CatalogueProvider:
    return cast(CatalogueProvider, request.app.state.catalogue_provider)


def get_imagery_tile_service(request: Request) -> ImageryTileService:
    return cast(ImageryTileService, request.app.state.imagery_tile_service)


def get_sar_provider(request: Request) -> InpeSarProvider:
    return cast(InpeSarProvider, request.app.state.sar_provider)


def get_sar_raster_service(request: Request) -> SarRasterService:
    return cast(SarRasterService, request.app.state.sar_raster_service)


def get_nisar_provider(request: Request) -> NisarCmrProvider:
    return cast(NisarCmrProvider, request.app.state.nisar_provider)


def get_nisar_ingestion_service(request: Request) -> NisarGcovIngestionService:
    return cast(NisarGcovIngestionService, request.app.state.nisar_ingestion_service)


def get_processing_job_service(request: Request) -> PreparationJobService:
    service = getattr(request.app.state, "processing_job_service", None)
    if service is None:
        raise ApiError(
            status_code=503,
            code="CAPABILITY_UNAVAILABLE",
            message="Durable preparation processing is unavailable.",
            retryable=True,
        )
    return cast(PreparationJobService, service)


def get_optical_sar_job_service(request: Request) -> OpticalSarJobService:
    service = getattr(request.app.state, "optical_sar_job_service", None)
    if service is None:
        raise ApiError(
            status_code=503,
            code="CAPABILITY_UNAVAILABLE",
            message="Durable optical/SAR processing is unavailable.",
            retryable=True,
        )
    return cast(OpticalSarJobService, service)


def get_inference_job_service(request: Request) -> InferenceJobService:
    service = getattr(request.app.state, "inference_job_service", None)
    if service is None:
        raise ApiError(
            status_code=503,
            code="CAPABILITY_UNAVAILABLE",
            message="Durable inference processing is unavailable.",
            retryable=True,
        )
    return cast(InferenceJobService, service)


async def get_processing_principal(request: Request) -> ProcessingPrincipal:
    resolver = getattr(request.app.state, "processing_principal_resolver", None)
    if resolver is None:
        raise ApiError(
            status_code=503,
            code="CAPABILITY_UNAVAILABLE",
            message="Protected processing requires a configured identity provider.",
            retryable=False,
        )
    typed = cast(Callable[[Request], Awaitable[ProcessingPrincipal]], resolver)
    return await typed(request)
