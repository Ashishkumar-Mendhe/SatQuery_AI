"""Provider status and readiness inspection API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from satquery.api.dependencies import get_ai_provider, get_satellite_provider
from satquery.api.schemas.providers import (
    ProvidersStatusResponse,
    ProviderStatus,
)
from satquery.core.config import Settings
from satquery.providers.ai.registry import AIProviderRegistry
from satquery.providers.satellite.registry import SatelliteProviderRegistry

router = APIRouter()

SatelliteRegistryDependency = Annotated[SatelliteProviderRegistry, Depends(get_satellite_provider)]
AIRegistryDependency = Annotated[AIProviderRegistry, Depends(get_ai_provider)]


@router.get("/status", response_model=ProvidersStatusResponse)
async def get_providers_status(
    request: Request,
    satellite_registry: SatelliteRegistryDependency,
    ai_registry: AIRegistryDependency,
) -> ProvidersStatusResponse:
    """Return public readiness and capabilities for all configured satellite and AI providers."""
    settings: Settings = request.app.state.settings

    satellite_info = await satellite_registry.health_check()
    ai_info = await ai_registry.health_check()

    overall_readiness = satellite_info.status in {
        ProviderStatus.READY,
        ProviderStatus.DEGRADED,
    } and ai_info.status in {ProviderStatus.READY, ProviderStatus.DEGRADED}

    return ProvidersStatusResponse(
        environment=settings.environment,
        contract_version=settings.contract_version,
        satellite_provider=satellite_info,
        ai_provider=ai_info,
        processing_mode=settings.processing_mode,
        mock_fallback_enabled=settings.allow_mock_fallback,
        overall_readiness=overall_readiness,
        timestamp=datetime.now(UTC),
    )
