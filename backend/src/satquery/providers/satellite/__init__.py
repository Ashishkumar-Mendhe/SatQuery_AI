"""Satellite imagery provider interfaces, mock provider, and registry."""

from satquery.providers.satellite.base import (
    InvalidProviderResponseError,
    ProviderAuthenticationError,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    SatelliteProvider,
    SatelliteProviderError,
    SceneNotFoundError,
    SceneSearchRequest,
    SceneSearchResponse,
    UnsupportedProviderCapabilityError,
)
from satquery.providers.satellite.mock import MockSatelliteProvider
from satquery.providers.satellite.real_adapter import RealSatelliteProviderAdapter
from satquery.providers.satellite.registry import (
    DisabledSatelliteProvider,
    SatelliteProviderRegistry,
)

__all__ = [
    "DisabledSatelliteProvider",
    "InvalidProviderResponseError",
    "MockSatelliteProvider",
    "ProviderAuthenticationError",
    "ProviderNotConfiguredError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "RealSatelliteProviderAdapter",
    "SatelliteProvider",
    "SatelliteProviderError",
    "SatelliteProviderRegistry",
    "SceneNotFoundError",
    "SceneSearchRequest",
    "SceneSearchResponse",
    "UnsupportedProviderCapabilityError",
]
