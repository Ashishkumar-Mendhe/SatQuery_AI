"""Unit tests for satellite provider interfaces, mock providers, and fallback registry."""

from __future__ import annotations

import asyncio

import httpx2
import pytest

from satquery.api.schemas.analysis import (
    AOIGeometry,
    DateRange,
    SensorType,
    WarningCode,
)
from satquery.api.schemas.providers import (
    DataOrigin,
    ProviderMode,
    ProviderStatus,
)
from satquery.providers.satellite.base import (
    InvalidProviderResponseError,
    ProviderAuthenticationError,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    SatelliteProviderError,
    SceneNotFoundError,
    SceneSearchRequest,
)
from satquery.providers.satellite.mock import (
    BENGALURU_FOOTPRINT,
    MockSatelliteProvider,
)
from satquery.providers.satellite.real_adapter import RealSatelliteProviderAdapter
from satquery.providers.satellite.registry import (
    DisabledSatelliteProvider,
    SatelliteProviderRegistry,
)

SAMPLE_STAC_FEATURE = {
    "type": "Feature",
    "id": "S2B_T43PGQ_20251223T051848_L2A",
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [76.8405, 12.5604],
                [77.8618, 12.5604],
                [77.8618, 13.5611],
                [76.8405, 13.5611],
                [76.8405, 12.5604],
            ]
        ],
    },
    "bbox": [76.8405, 12.5604, 77.8618, 13.5611],
    "properties": {
        "datetime": "2025-12-23T05:25:18.674Z",
        "platform": "Sentinel-2B",
        "constellation": "sentinel-2",
        "eo:cloud_cover": 4.3,
        "grid:code": "MGRS-43PGQ",
        "proj:epsg": 32643,
    },
    "assets": {
        "thumbnail": {
            "href": "https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/thumbnail.jpg"
        },
        "rendered_preview": {
            "href": "https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/preview.jpg"
        },
    },
}


@pytest.fixture
def sample_aoi() -> AOIGeometry:
    return BENGALURU_FOOTPRINT


def test_mock_satellite_provider_health_check() -> None:
    provider = MockSatelliteProvider()
    info = asyncio.run(provider.health_check())

    assert info.provider_id == "mock"
    assert info.mode == ProviderMode.MOCK
    assert info.status == ProviderStatus.READY
    assert info.configured is True
    assert info.healthy is True
    assert info.data_origin == DataOrigin.MOCK
    assert len(info.capabilities) > 0


def test_mock_satellite_provider_scene_search(sample_aoi: AOIGeometry) -> None:
    provider = MockSatelliteProvider()
    req = SceneSearchRequest(
        aoi=sample_aoi,
        date_range=DateRange(start_date="2025-01-01", end_date="2026-12-31"),
        max_cloud_cover=50.0,
        limit=10,
    )
    res = asyncio.run(provider.search_scenes(req))

    assert res.provider_id == "mock"
    assert res.data_origin == DataOrigin.MOCK
    assert res.returned_count > 0
    assert len(res.scenes) == res.returned_count
    assert res.execution.data_origin == DataOrigin.MOCK
    assert res.execution.fallback_used is False

    for scene in res.scenes:
        assert scene.id.startswith("mock-scene-")
        assert scene.cloud_cover is not None
        assert scene.cloud_cover <= 50.0


def test_mock_satellite_provider_cloud_filter(sample_aoi: AOIGeometry) -> None:
    provider = MockSatelliteProvider()
    req_high = SceneSearchRequest(aoi=sample_aoi, max_cloud_cover=90.0, limit=10)
    res_high = asyncio.run(provider.search_scenes(req_high))
    assert any(s.id == "mock-scene-cloudy-01" for s in res_high.scenes)

    req_low = SceneSearchRequest(aoi=sample_aoi, max_cloud_cover=10.0, limit=10)
    res_low = asyncio.run(provider.search_scenes(req_low))
    assert not any(s.id == "mock-scene-cloudy-01" for s in res_low.scenes)


def test_mock_satellite_provider_sensor_filter(sample_aoi: AOIGeometry) -> None:
    provider = MockSatelliteProvider()
    req_sar = SceneSearchRequest(
        aoi=sample_aoi,
        sensor_types=[SensorType.SAR],
        max_cloud_cover=100.0,
        limit=10,
    )
    res_sar = asyncio.run(provider.search_scenes(req_sar))
    assert len(res_sar.scenes) >= 1
    assert all(s.sensor_type == SensorType.SAR for s in res_sar.scenes)


def test_mock_satellite_provider_simulated_failures(sample_aoi: AOIGeometry) -> None:
    req = SceneSearchRequest(aoi=sample_aoi)

    p_timeout = MockSatelliteProvider(simulate_failure="timeout")
    with pytest.raises(ProviderTimeoutError):
        asyncio.run(p_timeout.search_scenes(req))

    p_unavail = MockSatelliteProvider(simulate_failure="unavailable")
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(p_unavail.search_scenes(req))

    p_invalid = MockSatelliteProvider(simulate_failure="invalid_response")
    with pytest.raises(InvalidProviderResponseError):
        asyncio.run(p_invalid.search_scenes(req))

    p_empty = MockSatelliteProvider(simulate_failure="empty")
    res_empty = asyncio.run(p_empty.search_scenes(req))
    assert res_empty.returned_count == 0
    assert len(res_empty.scenes) == 0


def test_real_satellite_provider_adapter_unconfigured() -> None:
    adapter = RealSatelliteProviderAdapter(
        provider_id="sentinel_hub",
        client_id=None,
        client_secret=None,
    )
    assert adapter.is_configured() is False
    info = asyncio.run(adapter.health_check())
    assert info.status == ProviderStatus.NOT_CONFIGURED
    assert info.configured is False

    req = SceneSearchRequest(aoi=BENGALURU_FOOTPRINT)
    with pytest.raises(ProviderNotConfiguredError):
        asyncio.run(adapter.search_scenes(req))


def test_real_satellite_provider_adapter_search_success(sample_aoi: AOIGeometry) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/search"
        payload = {
            "type": "FeatureCollection",
            "features": [SAMPLE_STAC_FEATURE],
            "context": {"matched": 1, "returned": 1},
            "links": [
                {
                    "rel": "next",
                    "href": "https://earth-search.aws.element84.com/v1/search?token=tok123",
                }
            ],
        }
        return httpx2.Response(200, json=payload)

    transport = httpx2.MockTransport(handler)
    client = httpx2.AsyncClient(transport=transport)
    adapter = RealSatelliteProviderAdapter(client=client)

    req = SceneSearchRequest(
        aoi=sample_aoi,
        date_range=DateRange(start_date="2025-01-01", end_date="2025-12-31"),
        max_cloud_cover=20.0,
        limit=10,
    )
    res = asyncio.run(adapter.search_scenes(req))

    assert res.data_origin == DataOrigin.REAL
    assert res.returned_count == 1
    assert len(res.scenes) == 1
    scene = res.scenes[0]
    assert scene.id == "S2B_T43PGQ_20251223T051848_L2A"
    assert scene.provider == "earth-search"
    assert scene.platform == "Sentinel-2B"
    assert scene.cloud_cover == 4.3
    assert scene.thumbnail_url is not None
    assert "e84-earth-search" in scene.thumbnail_url
    assert res.next_cursor is not None


def test_real_satellite_provider_adapter_rate_limit(sample_aoi: AOIGeometry) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(429, text="Rate limit exceeded")

    transport = httpx2.MockTransport(handler)
    client = httpx2.AsyncClient(transport=transport)
    adapter = RealSatelliteProviderAdapter(client=client, max_retries=0)

    req = SceneSearchRequest(aoi=sample_aoi)
    with pytest.raises(ProviderRateLimitError):
        asyncio.run(adapter.search_scenes(req))


def test_real_satellite_provider_adapter_auth_error(sample_aoi: AOIGeometry) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(401, text="Unauthorized")

    transport = httpx2.MockTransport(handler)
    client = httpx2.AsyncClient(transport=transport)
    adapter = RealSatelliteProviderAdapter(client=client, max_retries=0)

    req = SceneSearchRequest(aoi=sample_aoi)
    with pytest.raises(ProviderAuthenticationError):
        asyncio.run(adapter.search_scenes(req))


def test_real_satellite_provider_adapter_unsupported_collection(sample_aoi: AOIGeometry) -> None:
    adapter = RealSatelliteProviderAdapter()
    req = SceneSearchRequest(aoi=sample_aoi, collections=["unsupported-collection-xyz"])
    with pytest.raises(SatelliteProviderError) as exc_info:
        asyncio.run(adapter.search_scenes(req))
    assert exc_info.value.code == "UNSUPPORTED_COLLECTION"


def test_real_satellite_provider_adapter_get_scene() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if "items/S2B_T43PGQ_20251223T051848_L2A" in str(request.url):
            return httpx2.Response(200, json=SAMPLE_STAC_FEATURE)
        return httpx2.Response(404, text="Not Found")

    transport = httpx2.MockTransport(handler)
    client = httpx2.AsyncClient(transport=transport)
    adapter = RealSatelliteProviderAdapter(client=client)

    scene = asyncio.run(adapter.get_scene("S2B_T43PGQ_20251223T051848_L2A"))
    assert scene.id == "S2B_T43PGQ_20251223T051848_L2A"

    with pytest.raises(SceneNotFoundError):
        asyncio.run(adapter.get_scene("non-existent-scene"))


def test_satellite_registry_fallback_behavior(sample_aoi: AOIGeometry) -> None:
    failing_primary = MockSatelliteProvider(simulate_failure="unavailable")
    registry = SatelliteProviderRegistry(
        primary_provider=failing_primary,
        mock_provider=MockSatelliteProvider(),
        allow_fallback=True,
    )

    req = SceneSearchRequest(aoi=sample_aoi)
    res = asyncio.run(registry.search_scenes(req))

    assert res.data_origin == DataOrigin.FALLBACK
    assert res.execution.fallback_used is True
    assert "unavailable" in (res.execution.fallback_reason or "")
    assert len(res.warnings) >= 1
    assert any(w.code == WarningCode.MOCK_DATA_USED for w in res.warnings)


def test_satellite_registry_no_fallback_when_disabled(sample_aoi: AOIGeometry) -> None:
    failing_primary = MockSatelliteProvider(simulate_failure="unavailable")
    registry = SatelliteProviderRegistry(
        primary_provider=failing_primary,
        mock_provider=MockSatelliteProvider(),
        allow_fallback=False,
    )

    req = SceneSearchRequest(aoi=sample_aoi)
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(registry.search_scenes(req))


def test_disabled_satellite_provider(sample_aoi: AOIGeometry) -> None:
    disabled = DisabledSatelliteProvider()
    info = asyncio.run(disabled.health_check())
    assert info.status == ProviderStatus.DISABLED

    req = SceneSearchRequest(aoi=sample_aoi)
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(disabled.search_scenes(req))
