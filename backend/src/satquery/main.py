from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from satquery import __version__
from satquery.api.router import api_router
from satquery.core.config import Settings, load_settings
from satquery.core.errors import install_exception_handlers
from satquery.core.logging import configure_logging, get_logger
from satquery.core.middleware import RequestContextMiddleware
from satquery.db.session import Database, ReadinessDatabase
from satquery.providers.ai.registry import AIProviderRegistry
from satquery.providers.catalog import CatalogueProvider, EarthSearchCatalogueProvider
from satquery.providers.satellite.registry import SatelliteProviderRegistry
from satquery.services.change_service import ChangeService
from satquery.services.claim_validator import ClaimValidator
from satquery.services.evidence_retriever import EvidenceRetriever
from satquery.services.fusion_service import FusionService
from satquery.services.imagery_service import ImageryService
from satquery.services.preparation_service import PreparationService
from satquery.services.query_router import QueryRouter
from satquery.services.query_service import QueryService
from satquery.services.report_service import ReportService
from satquery.services.spectral_service import SpectralService
from satquery.services.sufficiency_checker import SufficiencyChecker
from satquery.services.visual_query_service import VisualQueryService
from satquery.tiles import ImageryTileService

logger = get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    database: ReadinessDatabase | None = None,
    catalogue_provider: CatalogueProvider | None = None,
    imagery_tile_service: ImageryTileService | None = None,
    satellite_provider_registry: SatelliteProviderRegistry | None = None,
    ai_provider_registry: AIProviderRegistry | None = None,
    imagery_service: ImageryService | None = None,
    preparation_service: PreparationService | None = None,
    spectral_service: SpectralService | None = None,
    change_service: ChangeService | None = None,
    fusion_service: FusionService | None = None,
    query_service: QueryService | None = None,
    visual_query_service: VisualQueryService | None = None,
    report_service: ReportService | None = None,
) -> FastAPI:
    resolved_settings = settings or load_settings()
    configure_logging(resolved_settings.log_level)
    resolved_database = database or Database.from_settings(resolved_settings)
    owns_database = database is None
    resolved_catalogue_provider = catalogue_provider or EarthSearchCatalogueProvider.from_settings(
        resolved_settings
    )
    owns_catalogue_provider = catalogue_provider is None
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
    resolved_imagery_service = imagery_service or ImageryService(resolved_settings)
    resolved_preparation_service = preparation_service or PreparationService(
        resolved_settings, asset_store=resolved_imagery_service.asset_store
    )
    resolved_spectral_service = spectral_service or SpectralService(
        resolved_settings, asset_store=resolved_imagery_service.asset_store
    )
    resolved_change_service = change_service or ChangeService(
        resolved_settings, asset_store=resolved_imagery_service.asset_store
    )
    resolved_fusion_service = fusion_service or FusionService(
        resolved_settings,
        asset_store=resolved_imagery_service.asset_store,
        change_service=resolved_change_service,
    )
    resolved_satellite_registry = (
        satellite_provider_registry or SatelliteProviderRegistry.from_settings(resolved_settings)
    )
    owns_satellite_registry = satellite_provider_registry is None
    resolved_ai_registry = ai_provider_registry or AIProviderRegistry.from_settings(
        resolved_settings
    )
    owns_ai_registry = ai_provider_registry is None
    resolved_query_service = query_service or QueryService(
        router=QueryRouter(),
        retriever=EvidenceRetriever(
            spectral_service=resolved_spectral_service,
            change_service=resolved_change_service,
            fusion_service=resolved_fusion_service,
        ),
        checker=SufficiencyChecker(),
        validator=ClaimValidator(),
        ai_registry=resolved_ai_registry,
    )
    resolved_visual_query_service = visual_query_service or VisualQueryService(
        settings=resolved_settings,
        asset_store=resolved_imagery_service.asset_store,
        ai_provider=resolved_ai_registry.get_active_provider(),
        evidence_retriever=resolved_query_service.retriever,
        change_service=resolved_change_service,
        spectral_service=resolved_spectral_service,
        fusion_service=resolved_fusion_service,
    )
    resolved_report_service = report_service or ReportService(
        settings=resolved_settings,
        asset_store=resolved_imagery_service.asset_store,
        change_service=resolved_change_service,
        spectral_service=resolved_spectral_service,
        fusion_service=resolved_fusion_service,
        query_service=resolved_query_service,
        visual_query_service=resolved_visual_query_service,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        app.state.database = resolved_database
        app.state.catalogue_provider = resolved_catalogue_provider
        app.state.imagery_tile_service = resolved_tile_service
        app.state.imagery_service = resolved_imagery_service
        app.state.preparation_service = resolved_preparation_service
        app.state.spectral_service = resolved_spectral_service
        app.state.change_service = resolved_change_service
        app.state.fusion_service = resolved_fusion_service
        app.state.query_service = resolved_query_service
        app.state.visual_query_service = resolved_visual_query_service
        app.state.report_service = resolved_report_service
        app.state.satellite_provider_registry = resolved_satellite_registry
        app.state.ai_provider_registry = resolved_ai_registry

        logger.info(
            "application_started",
            extra={"event": "application_started", "environment": resolved_settings.environment},
        )
        try:
            if hasattr(resolved_database, "init_schema"):
                try:
                    await resolved_database.init_schema()
                except Exception as exc:
                    logger.warning("database_schema_init_failed", extra={"error": str(exc)})
            yield
        finally:
            if owns_ai_registry:
                await resolved_ai_registry.aclose()
            if owns_satellite_registry:
                await resolved_satellite_registry.aclose()
            if owns_tile_service:
                await resolved_tile_service.aclose()
            if owns_database:
                await resolved_database.dispose()
            if owns_catalogue_provider:
                await resolved_catalogue_provider.aclose()
            logger.info("application_stopped", extra={"event": "application_stopped"})

    app = FastAPI(
        title="SatQuery AI API",
        summary="Phase 0C application, provider interfaces and health foundation",
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
        allow_headers=["Accept", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    install_exception_handlers(app)
    app.include_router(api_router, prefix=resolved_settings.api_prefix)
    return app


app = create_app()
