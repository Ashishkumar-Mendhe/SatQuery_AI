from typing import cast

from fastapi import Request

from satquery.core.config import Settings
from satquery.db.session import ReadinessDatabase
from satquery.providers.ai.registry import AIProviderRegistry
from satquery.providers.catalog import CatalogueProvider
from satquery.providers.satellite.registry import SatelliteProviderRegistry
from satquery.services.change_service import ChangeService
from satquery.services.fusion_service import FusionService
from satquery.services.imagery_service import ImageryService
from satquery.services.preparation_service import PreparationService
from satquery.services.query_service import QueryService
from satquery.services.report_service import ReportService
from satquery.services.spectral_service import SpectralService
from satquery.services.visual_query_service import VisualQueryService
from satquery.tiles import ImageryTileService


def get_app_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_database(request: Request) -> ReadinessDatabase:
    return cast(ReadinessDatabase, request.app.state.database)


def get_catalogue_provider(request: Request) -> CatalogueProvider:
    return cast(CatalogueProvider, request.app.state.catalogue_provider)


def get_imagery_tile_service(request: Request) -> ImageryTileService:
    return cast(ImageryTileService, request.app.state.imagery_tile_service)


def get_imagery_service(request: Request) -> ImageryService:
    return cast(ImageryService, request.app.state.imagery_service)


def get_preparation_service(request: Request) -> PreparationService:
    return cast(PreparationService, request.app.state.preparation_service)


def get_spectral_service(request: Request) -> SpectralService:
    return cast(SpectralService, request.app.state.spectral_service)


def get_change_service(request: Request) -> ChangeService:
    return cast(ChangeService, request.app.state.change_service)


def get_fusion_service(request: Request) -> FusionService:
    return cast(FusionService, request.app.state.fusion_service)


def get_query_service(request: Request) -> QueryService:
    return cast(QueryService, request.app.state.query_service)


def get_visual_query_service(request: Request) -> VisualQueryService:
    return cast(VisualQueryService, request.app.state.visual_query_service)


def get_report_service(request: Request) -> ReportService:
    return cast(ReportService, request.app.state.report_service)


def get_satellite_provider(request: Request) -> SatelliteProviderRegistry:
    return cast(SatelliteProviderRegistry, request.app.state.satellite_provider_registry)


def get_ai_provider(request: Request) -> AIProviderRegistry:
    return cast(AIProviderRegistry, request.app.state.ai_provider_registry)
