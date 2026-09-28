from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from satquery import __version__
from satquery.api.router import api_router
from satquery.core.config import Settings, load_settings
from satquery.core.errors import install_exception_handlers
from satquery.core.logging import configure_logging, get_logger
from satquery.core.middleware import RequestContextMiddleware
from satquery.db.geoagent_conversations import (
    ConversationRepository,
    PostgresConversationRepository,
)
from satquery.db.processing import (
    PostgresProcessingRepository,
    ProcessingPersistenceError,
    ProcessingPrincipal,
)
from satquery.db.session import Database, ReadinessDatabase
from satquery.inference import SingleImageInferenceService
from satquery.inference.grounding import ReferringGroundingService, TransformersGroundingDinoRuntime
from satquery.inference.jobs import InferenceJobService
from satquery.processing.jobs import PreparationJobService
from satquery.processing.nisar import NisarGcovIngestionService
from satquery.processing.optical_sar_jobs import OpticalSarJobService
from satquery.processing.sar import SarRasterService
from satquery.providers.catalog import CatalogueProvider, EarthSearchCatalogueProvider
from satquery.providers.catalog.inpe_sar import InpeSarProvider
from satquery.providers.catalog.nisar_cmr import NisarCmrProvider
from satquery.storage import AtomicArtifactStore
from satquery.tiles import ImageryTileService

logger = get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    database: ReadinessDatabase | None = None,
    catalogue_provider: CatalogueProvider | None = None,
    imagery_tile_service: ImageryTileService | None = None,
    processing_job_service: PreparationJobService | None = None,
    single_image_inference_service: SingleImageInferenceService | None = None,
    inference_job_service: InferenceJobService | None = None,
    processing_principal_resolver: Callable[[Request], Awaitable[ProcessingPrincipal]]
    | None = None,
    sar_provider: InpeSarProvider | None = None,
    sar_raster_service: SarRasterService | None = None,
    optical_sar_job_service: OpticalSarJobService | None = None,
    nisar_provider: NisarCmrProvider | None = None,
    nisar_ingestion_service: NisarGcovIngestionService | None = None,
    geoagent_conversation_repository: ConversationRepository | None = None,
) -> FastAPI:
    resolved_settings = settings or load_settings()
    configure_logging(resolved_settings.log_level)
    resolved_database = database or Database.from_settings(resolved_settings)
    owns_database = database is None
    resolved_conversation_repository = geoagent_conversation_repository
    if resolved_conversation_repository is None and isinstance(resolved_database, Database):
        resolved_conversation_repository = PostgresConversationRepository(resolved_database)
    resolved_catalogue_provider = catalogue_provider or EarthSearchCatalogueProvider.from_settings(
        resolved_settings
    )
    owns_catalogue_provider = catalogue_provider is None
    resolved_sar_provider = sar_provider or InpeSarProvider()
    owns_sar_provider = sar_provider is None
    resolved_sar_raster_service = sar_raster_service or SarRasterService(
        resolved_sar_provider, api_prefix=resolved_settings.api_prefix
    )
    resolved_nisar_provider = nisar_provider or NisarCmrProvider()
    owns_nisar_provider = nisar_provider is None
    resolved_nisar_ingestion_service = nisar_ingestion_service or NisarGcovIngestionService(
        resolved_nisar_provider,
        resolved_settings.nisar_product_cache_root,
        max_pixels=min(resolved_settings.processing_max_pixels, 1_000_000),
    )
    resolved_tile_service = imagery_tile_service or ImageryTileService(
        resolved_catalogue_provider,
        api_prefix=resolved_settings.api_prefix,
        max_zoom=resolved_settings.imagery_tile_max_zoom,
        request_timeout_seconds=resolved_settings.imagery_tile_request_timeout_seconds,
        max_concurrency=resolved_settings.imagery_tile_max_concurrency,
        tile_set_ttl_seconds=resolved_settings.imagery_tile_set_ttl_seconds,
        tile_set_cache_max_entries=resolved_settings.imagery_tile_set_cache_max_entries,
        tile_byte_cache_max_bytes=resolved_settings.imagery_tile_byte_cache_max_bytes,
    )
    owns_tile_service = imagery_tile_service is None
    resolved_processing_service = processing_job_service
    if resolved_processing_service is None and isinstance(resolved_database, Database):
        resolved_processing_service = PreparationJobService(
            PostgresProcessingRepository(resolved_database),
            resolved_catalogue_provider,
            AtomicArtifactStore(
                resolved_settings.processing_artifact_root,
                max_job_bytes=resolved_settings.processing_max_artifact_bytes,
            ),
            max_concurrency=resolved_settings.processing_max_concurrency,
            timeout_seconds=resolved_settings.processing_timeout_seconds,
            max_pixels=resolved_settings.processing_max_pixels,
            max_memory_bytes=resolved_settings.processing_max_memory_bytes,
        )
    resolved_inference_service = single_image_inference_service
    owns_inference_service = single_image_inference_service is None
    if resolved_inference_service is None:
        resolved_inference_service = SingleImageInferenceService.from_settings(resolved_settings)
    resolved_inference_job_service = inference_job_service
    if resolved_inference_job_service is None and isinstance(resolved_database, Database):
        resolved_inference_job_service = InferenceJobService(
            PostgresProcessingRepository(resolved_database),
            resolved_catalogue_provider,
            AtomicArtifactStore(
                resolved_settings.processing_artifact_root,
                max_job_bytes=resolved_settings.processing_max_artifact_bytes,
            ),
            answer_service=resolved_inference_service,
            grounding_service=ReferringGroundingService(
                TransformersGroundingDinoRuntime(), max_concurrency=1
            ),
            max_concurrency=resolved_settings.processing_max_concurrency,
            timeout_seconds=max(300.0, resolved_settings.processing_timeout_seconds),
            max_pixels=resolved_settings.processing_max_pixels,
        )
    resolved_optical_sar_job_service = optical_sar_job_service
    if resolved_optical_sar_job_service is None and isinstance(resolved_database, Database):
        resolved_optical_sar_job_service = OpticalSarJobService(
            PostgresProcessingRepository(resolved_database),
            resolved_catalogue_provider,
            resolved_sar_provider,
            resolved_sar_raster_service,
            AtomicArtifactStore(
                resolved_settings.processing_artifact_root,
                max_job_bytes=resolved_settings.processing_max_artifact_bytes,
            ),
            timeout_seconds=resolved_settings.processing_timeout_seconds,
            max_concurrency=resolved_settings.processing_max_concurrency,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        app.state.database = resolved_database
        app.state.geoagent_conversation_repository = resolved_conversation_repository
        app.state.catalogue_provider = resolved_catalogue_provider
        app.state.imagery_tile_service = resolved_tile_service
        app.state.processing_job_service = resolved_processing_service
        app.state.single_image_inference_service = resolved_inference_service
        app.state.inference_job_service = resolved_inference_job_service
        app.state.processing_principal_resolver = processing_principal_resolver
        app.state.sar_provider = resolved_sar_provider
        app.state.sar_raster_service = resolved_sar_raster_service
        app.state.optical_sar_job_service = resolved_optical_sar_job_service
        app.state.nisar_provider = resolved_nisar_provider
        app.state.nisar_ingestion_service = resolved_nisar_ingestion_service
        logger.info(
            "application_started",
            extra={"event": "application_started", "environment": resolved_settings.environment},
        )
        try:
            if resolved_processing_service is not None:
                try:
                    await resolved_processing_service.start()
                except ProcessingPersistenceError:
                    app.state.processing_job_service = None
                    logger.warning(
                        "processing_service_unavailable",
                        extra={"event": "processing_service_unavailable"},
                    )
            if resolved_inference_job_service is not None:
                try:
                    await resolved_inference_job_service.start()
                except ProcessingPersistenceError:
                    app.state.inference_job_service = None
                    logger.warning(
                        "inference_job_service_unavailable",
                        extra={"event": "inference_job_service_unavailable"},
                    )
            if resolved_optical_sar_job_service is not None:
                try:
                    await resolved_optical_sar_job_service.start()
                except ProcessingPersistenceError:
                    app.state.optical_sar_job_service = None
                    logger.warning(
                        "optical_sar_job_service_unavailable",
                        extra={"event": "optical_sar_job_service_unavailable"},
                    )
            yield
        finally:
            if resolved_processing_service is not None:
                await resolved_processing_service.stop()
            if resolved_inference_job_service is not None:
                await resolved_inference_job_service.stop()
            if resolved_optical_sar_job_service is not None:
                await resolved_optical_sar_job_service.stop()
            if owns_inference_service and resolved_inference_service is not None:
                await resolved_inference_service.aclose()
            if owns_tile_service:
                await resolved_tile_service.aclose()
            if owns_database:
                await resolved_database.dispose()
            if owns_catalogue_provider:
                await resolved_catalogue_provider.aclose()
            if owns_sar_provider:
                await resolved_sar_provider.aclose()
            if owns_nisar_provider:
                await resolved_nisar_provider.aclose()
            logger.info("application_stopped", extra={"event": "application_stopped"})

    app = FastAPI(
        title="SatQuery AI API",
        summary="SatQuery catalogue, imagery, and bounded preparation API",
        version=__version__,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["X-Checksum-SHA256", "X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    install_exception_handlers(app)
    app.include_router(api_router, prefix=resolved_settings.api_prefix)
    return app
