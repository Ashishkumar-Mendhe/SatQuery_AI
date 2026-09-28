"""Integration tests for /scenes/temporal-search and /scenes/validate-pair endpoints."""

from __future__ import annotations

from conftest import ReadyDatabase, make_settings
from fastapi.testclient import TestClient

from satquery.main import create_app

SAMPLE_AOI = {
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
    "bbox": [77.45, 12.85, 77.75, 13.15],
}


def test_temporal_search_endpoint_mock_mode() -> None:
    settings = make_settings()
    settings.satellite_provider_mode = "mock"
    app = create_app(settings=settings, database=ReadyDatabase())

    with TestClient(app, raise_server_exceptions=False) as client:
        payload = {
            "aoi": SAMPLE_AOI,
            "before_window": {
                "start_date": "2025-12-01",
                "end_date": "2025-12-20",
                "label": "before",
            },
            "after_window": {
                "start_date": "2025-12-21",
                "end_date": "2025-12-31",
                "label": "after",
            },
            "max_cloud_cover": 25.0,
            "limit_per_window": 10,
        }
        res = client.post("/api/v1/scenes/temporal-search", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "search_id" in data
        assert data["provider_id"] == "mock"
        assert data["data_origin"] == "mock"
        assert "before_scenes" in data
        assert "after_scenes" in data
        assert len(data["before_scenes"]) > 0
        assert len(data["after_scenes"]) > 0


def test_temporal_search_endpoint_validation_error() -> None:
    settings = make_settings()
    settings.satellite_provider_mode = "mock"
    app = create_app(settings=settings, database=ReadyDatabase())

    with TestClient(app, raise_server_exceptions=False) as client:
        # Reversed before window (start > end)
        payload = {
            "aoi": SAMPLE_AOI,
            "before_window": {
                "start_date": "2024-06-01",
                "end_date": "2024-01-01",
            },
            "after_window": {
                "start_date": "2024-07-01",
                "end_date": "2024-12-31",
            },
        }
        res = client.post("/api/v1/scenes/temporal-search", json=payload)
        assert res.status_code == 422


def test_validate_pair_endpoint() -> None:
    settings = make_settings()
    settings.satellite_provider_mode = "mock"
    app = create_app(settings=settings, database=ReadyDatabase())

    with TestClient(app, raise_server_exceptions=False) as client:
        scene_a = {
            "id": "S2A_20250101",
            "provider": "earth-search",
            "collection": "sentinel-2-c1-l2a",
            "acquisition_time": "2025-01-01T05:20:00Z",
            "sensor_type": "multispectral",
            "platform": "Sentinel-2A",
            "cloud_cover": 2.0,
            "bbox": [77.40, 12.80, 77.80, 13.20],
            "available_bands": ["B02", "B03", "B04", "B08"],
            "resolution_meters": 10.0,
            "metadata": {"data_origin": "real"},
        }
        scene_b = {
            "id": "S2B_20250120",
            "provider": "earth-search",
            "collection": "sentinel-2-c1-l2a",
            "acquisition_time": "2025-01-20T05:20:00Z",
            "sensor_type": "multispectral",
            "platform": "Sentinel-2B",
            "cloud_cover": 3.5,
            "bbox": [77.40, 12.80, 77.80, 13.20],
            "available_bands": ["B02", "B03", "B04", "B08"],
            "resolution_meters": 10.0,
            "metadata": {"data_origin": "real"},
        }

        payload = {
            "aoi": SAMPLE_AOI,
            "before_scene": scene_a,
            "after_scene": scene_b,
            "analysis_mode": "change_detection",
        }
        res = client.post("/api/v1/scenes/validate-pair", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is True
        assert data["status"] == "compatible"
        assert data["temporal_gap_days"] == 19.0
        assert data["compatibility_score"] >= 0.85
        assert len(data["factors"]) == 5
        assert data["normalized_selection"]["before_scene_id"] == "S2A_20250101"
        assert data["normalized_selection"]["after_scene_id"] == "S2B_20250120"
