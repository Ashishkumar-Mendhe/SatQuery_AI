"""FastAPI routes for normalized satellite scene discovery, temporal pairing, and metadata."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status

from satquery.api.dependencies import get_satellite_provider
from satquery.api.schemas.analysis import (
    AnalysisWarning,
    DateRange,
    SatelliteScene,
    WarningCode,
    WarningSeverity,
)
from satquery.api.schemas.providers import (
    DataOrigin,
    ProviderExecutionMetadata,
    ProviderMode,
)
from satquery.api.schemas.temporal import (
    TemporalPairValidationRequest,
    TemporalPairValidationResult,
    TemporalSceneCandidates,
    TemporalSearchRequest,
)
from satquery.core.errors import ApiError
from satquery.core.logging import get_logger
from satquery.providers.satellite.base import (
    SatelliteProviderError,
    SceneSearchRequest,
    SceneSearchResponse,
)
from satquery.providers.satellite.registry import SatelliteProviderRegistry
from satquery.services.temporal_pairing import (
    recommend_best_temporal_pair,
    validate_temporal_pair,
)

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/search",
    response_model=SceneSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search satellite scene catalogue",
    description=(
        "Executes a normalized satellite scene catalogue search across configured "
        "real STAC providers or offline mock providers with transparent fallback."
    ),
)
async def search_scenes(
    request: SceneSearchRequest,
    registry: Annotated[SatelliteProviderRegistry, Depends(get_satellite_provider)],
) -> SceneSearchResponse:
    """Dispatches satellite scene discovery query through the active provider registry."""
    try:
        return await registry.search_scenes(request)
    except SatelliteProviderError as exc:
        raise ApiError(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
            details=exc.details,
        ) from exc


@router.post(
    "/temporal-search",
    response_model=TemporalSceneCandidates,
    status_code=status.HTTP_200_OK,
    summary="Search candidate scenes for bi-temporal windows",
    description=(
        "Executes dual catalogue searches across separate 'before' and 'after' date windows "
        "for the same AOI, computes deterministic pair recommendations, and returns candidate "
        "lists."
    ),
)
async def search_temporal_candidates(
    request: TemporalSearchRequest,
    registry: Annotated[SatelliteProviderRegistry, Depends(get_satellite_provider)],
) -> TemporalSceneCandidates:
    """Performs before and after scene discovery and ranks candidate scene pairs."""
    search_id = f"temporal-search-{uuid.uuid4().hex[:12]}"
    now_utc = datetime.now(UTC)

    before_query = SceneSearchRequest(
        aoi=request.aoi,
        date_range=DateRange(
            start_date=request.before_window.start_date,
            end_date=request.before_window.end_date,
        ),
        collections=request.collections,
        sensor_types=request.sensor_types,
        max_cloud_cover=request.max_cloud_cover,
        limit=request.limit_per_window,
        sort_order=request.sort_order,
        required_bands=request.required_bands,
        include_preview=request.include_preview,
    )

    after_query = SceneSearchRequest(
        aoi=request.aoi,
        date_range=DateRange(
            start_date=request.after_window.start_date,
            end_date=request.after_window.end_date,
        ),
        collections=request.collections,
        sensor_types=request.sensor_types,
        max_cloud_cover=request.max_cloud_cover,
        limit=request.limit_per_window,
        sort_order=request.sort_order,
        required_bands=request.required_bands,
        include_preview=request.include_preview,
    )

    # Execute searches concurrently
    results = await asyncio.gather(
        registry.search_scenes(before_query),
        registry.search_scenes(after_query),
        return_exceptions=True,
    )

    before_res, after_res = results
    warnings: list[AnalysisWarning] = []
    before_scenes: list[SatelliteScene] = []
    after_scenes: list[SatelliteScene] = []
    provider_id = "earth-search"
    data_origin = DataOrigin.REAL
    total_duration_ms = 0.0

    # Handle before window result
    if isinstance(before_res, Exception):
        if isinstance(before_res, SatelliteProviderError):
            warnings.append(
                AnalysisWarning(
                    code=WarningCode.INSUFFICIENT_EVIDENCE,
                    severity=WarningSeverity.HIGH,
                    title="Before Period Provider Error",
                    message=f"Before window search provider error: {before_res.message}",
                )
            )
        else:
            logger.error("Unexpected error in before window search", exc_info=before_res)
            warnings.append(
                AnalysisWarning(
                    code=WarningCode.INSUFFICIENT_EVIDENCE,
                    severity=WarningSeverity.HIGH,
                    title="Before Period Search Failure",
                    message="Failed to discover candidates for the before window.",
                )
            )
    elif isinstance(before_res, SceneSearchResponse):
        before_scenes = before_res.scenes
        provider_id = before_res.provider_id
        data_origin = before_res.data_origin
        if before_res.execution.duration_milliseconds:
            total_duration_ms += float(before_res.execution.duration_milliseconds)
        warnings.extend(before_res.warnings)

    # Handle after window result
    if isinstance(after_res, Exception):
        if isinstance(after_res, SatelliteProviderError):
            warnings.append(
                AnalysisWarning(
                    code=WarningCode.INSUFFICIENT_EVIDENCE,
                    severity=WarningSeverity.HIGH,
                    title="After Period Provider Error",
                    message=f"After window search provider error: {after_res.message}",
                )
            )
        else:
            logger.error("Unexpected error in after window search", exc_info=after_res)
            warnings.append(
                AnalysisWarning(
                    code=WarningCode.INSUFFICIENT_EVIDENCE,
                    severity=WarningSeverity.HIGH,
                    title="After Period Search Failure",
                    message="Failed to discover candidates for the after window.",
                )
            )
    elif isinstance(after_res, SceneSearchResponse):
        after_scenes = after_res.scenes
        provider_id = after_res.provider_id
        if after_res.data_origin != data_origin and before_scenes:
            data_origin = DataOrigin.FALLBACK
        elif not before_scenes:
            data_origin = after_res.data_origin
        if after_res.execution.duration_milliseconds:
            total_duration_ms += float(after_res.execution.duration_milliseconds)
        warnings.extend(after_res.warnings)

    # If both searches completely failed with exceptions
    if isinstance(before_res, Exception) and isinstance(after_res, Exception):
        if isinstance(before_res, SatelliteProviderError):
            raise ApiError(
                status_code=before_res.status_code,
                code=before_res.code,
                message=f"Temporal candidate search failed: {before_res.message}",
                retryable=before_res.retryable,
                details=before_res.details,
            )
        raise ApiError(
            status_code=500,
            code="TEMPORAL_SEARCH_FAILED",
            message="Both before and after catalogue searches failed.",
            retryable=True,
        )

    # Empty candidate warnings
    if not before_scenes:
        warnings.append(
            AnalysisWarning(
                code=WarningCode.INSUFFICIENT_EVIDENCE,
                severity=WarningSeverity.MEDIUM,
                title="No Before Candidates",
                message="No satellite scenes were found matching the before date window.",
            )
        )
    if not after_scenes:
        warnings.append(
            AnalysisWarning(
                code=WarningCode.INSUFFICIENT_EVIDENCE,
                severity=WarningSeverity.MEDIUM,
                title="No After Candidates",
                message="No satellite scenes were found matching the after date window.",
            )
        )

    # Compute deterministic recommended pair
    recommended = recommend_best_temporal_pair(
        aoi=request.aoi,
        before_scenes=before_scenes,
        after_scenes=after_scenes,
        preferences=request.pairing_preferences,
    )

    execution = ProviderExecutionMetadata(
        provider_id=provider_id,
        provider_mode=(
            ProviderMode.MOCK
            if data_origin == DataOrigin.MOCK
            else (
                ProviderMode.FALLBACK if data_origin == DataOrigin.FALLBACK else ProviderMode.REAL
            )
        )
        if hasattr(ProviderMode, "FALLBACK")
        else (
            ProviderMode.MOCK
            if data_origin in (DataOrigin.MOCK, DataOrigin.FALLBACK)
            else ProviderMode.REAL
        ),
        data_origin=data_origin,
        requested_at=now_utc,
        completed_at=datetime.now(UTC),
        duration_milliseconds=int(total_duration_ms),
        attempt_count=1,
        fallback_used=(data_origin == DataOrigin.FALLBACK),
        cached=False,
    )

    return TemporalSceneCandidates(
        search_id=search_id,
        before_scenes=before_scenes,
        after_scenes=after_scenes,
        provider_id=provider_id,
        execution=execution,
        warnings=warnings,
        data_origin=data_origin,
        generated_at=now_utc,
        recommended_pair=recommended,
    )


@router.post(
    "/validate-pair",
    response_model=TemporalPairValidationResult,
    status_code=status.HTTP_200_OK,
    summary="Validate compatibility between a before and after scene",
    description=(
        "Performs authoritative backend compatibility verification between two satellite scenes, "
        "evaluating spatial coverage over the AOI, sensor/platform compatibility, cloud cover, "
        "spectral band availability, temporal gap, and origin consistency."
    ),
)
async def validate_pair(
    request: TemporalPairValidationRequest,
) -> TemporalPairValidationResult:
    """Authoritatively validates temporal scene pair compatibility."""
    return validate_temporal_pair(
        aoi=request.aoi,
        before_scene=request.before_scene,
        after_scene=request.after_scene,
        analysis_mode=request.analysis_mode,
        pairing_preferences=request.pairing_preferences,
    )
