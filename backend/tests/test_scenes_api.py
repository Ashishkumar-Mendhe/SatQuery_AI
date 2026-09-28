"""Integration tests for the /api/v1/scenes/search endpoint."""

from __future__ import annotations

import httpx2
from conftest import ReadyDatabase, make_settings
from fastapi.testclient import TestClient

from satquery.main import create_app
from satquery.providers.satellite.mock import (
    MockSatelliteProvider,
)
from satquery.providers.satellite.real_adapter import RealSatelliteProviderAdapter
from satquery.providers.satellite.registry import SatelliteProviderRegistry

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
        "eo:cloud_cover": 4.3,
    },
    "assets": {
        "thumbnail": {
            "href": "https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/thumbnail.jpg"
        },
    },
}


def test_scenes_search_mock_mode() -> None:
    settings = make_settings()
    settings.satellite_provider_mode = "mock"
    app = create_app(settings=settings, database=ReadyDatabase())

    with TestClient(app, raise_server_exceptions=False) as client:
        payload = {
            "aoi": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [77.45, 12.85],
                        [77.75, 12.85],
                        [77.75, 13.15],
                        [77.45, 13.15],
                        [77.45, 12.85],
                    ]
                ],
            },
            "max_cloud_cover": 20.0,
            "limit": 10,
        }
        res = client.post("/api/v1/scenes/search", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["data_origin"] == "mock"
        assert data["provider_id"] == "mock"
        assert data["returned_count"] > 0
        assert len(data["scenes"]) == data["returned_count"]
        assert all(s["id"].startswith("mock-scene-") for s in data["scenes"])


def test_scenes_search_real_mode_with_mock_transport() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        payload = {
            "type": "FeatureCollection",
            "features": [SAMPLE_STAC_FEATURE],
            "context": {"matched": 1, "returned": 1},
        }
        return httpx2.Response(200, json=payload)

    mock_client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    real_adapter = RealSatelliteProviderAdapter(client=mock_client)
    registry = SatelliteProviderRegistry(
        primary_provider=real_adapter,
        mock_provider=MockSatelliteProvider(),
        allow_fallback=True,
    )

    settings = make_settings()
    app = create_app(
        settings=settings,
        database=ReadyDatabase(),
        satellite_provider_registry=registry,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        payload = {
            "aoi": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [77.45, 12.85],
                        [77.75, 12.85],
                        [77.75, 13.15],
                        [77.45, 13.15],
                        [77.45, 12.85],
                    ]
                ],
            },
            "date_range": {"start_date": "2025-01-01", "end_date": "2025-12-31"},
            "max_cloud_cover": 20.0,
            "limit": 10,
        }
        res = client.post("/api/v1/scenes/search", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["data_origin"] == "real"
        assert data["provider_id"] == "earth-search"
        assert data["returned_count"] == 1
        assert data["scenes"][0]["id"] == "S2B_T43PGQ_20251223T051848_L2A"


def test_scenes_search_fallback_on_real_provider_failure() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(503, text="Service Unavailable")

    mock_client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    real_adapter = RealSatelliteProviderAdapter(client=mock_client, max_retries=0)
    registry = SatelliteProviderRegistry(
        primary_provider=real_adapter,
        mock_provider=MockSatelliteProvider(),
        allow_fallback=True,
    )

    settings = make_settings()
    app = create_app(
        settings=settings,
        database=ReadyDatabase(),
        satellite_provider_registry=registry,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        payload = {
            "aoi": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [77.45, 12.85],
                        [77.75, 12.85],
                        [77.75, 13.15],
                        [77.45, 13.15],
                        [77.45, 12.85],
                    ]
                ],
            },
            "max_cloud_cover": 20.0,
            "limit": 10,
        }
        res = client.post("/api/v1/scenes/search", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["data_origin"] == "fallback"
        assert data["execution"]["fallback_used"] is True
        assert any(w["code"] == "MOCK_DATA_USED" for w in data["warnings"])


def test_scenes_search_validation_error() -> None:
    settings = make_settings()
    app = create_app(settings=settings, database=ReadyDatabase())

    with TestClient(app, raise_server_exceptions=False) as client:
        # Invalid unclosed polygon
        payload = {
            "aoi": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [77.45, 12.85],
                        [77.75, 12.85],
                        [77.75, 13.15],
                        [77.45, 13.15],  # Not closed!
                    ]
                ],
            }
        }
        res = client.post("/api/v1/scenes/search", json=payload)
        assert res.status_code == 422
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_FAILED"
