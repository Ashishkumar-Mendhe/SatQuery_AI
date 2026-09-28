"""Integration tests for Phase 3A imagery endpoints."""

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


def test_request_imagery_endpoint() -> None:
    settings = make_settings()
    settings.satellite_provider_mode = "mock"
    app = create_app(settings=settings, database=ReadyDatabase())

    with TestClient(app, raise_server_exceptions=False) as client:
        payload = {
            "scene_id": "mock-scene-optical-01",
            "aoi": SAMPLE_AOI,
            "product_type": "map_preview",
            "visualization_preset": "true_color",
            "output_format": "png",
            "width": 256,
            "height": 256,
        }
        res = client.post("/api/v1/imagery/request", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "asset_id" in data
        assert data["product_type"] == "map_preview"
        assert data["format"] == "png"
        assert data["content_type"] == "image/png"
        assert data["width"] == 256
        assert data["height"] == 256
        assert data["data_origin"] == "mock"

        asset_id = data["asset_id"]

        # Fetch the asset bytes
        asset_res = client.get(f"/api/v1/imagery/assets/{asset_id}")
        assert asset_res.status_code == 200
        assert asset_res.headers["content-type"] == "image/png"
        assert len(asset_res.content) > 0

        # Fetch the asset metadata
        meta_res = client.get(f"/api/v1/imagery/assets/{asset_id}/metadata")
        assert meta_res.status_code == 200
        meta_data = meta_res.json()
        assert meta_data["scene_id"] == "mock-scene-optical-01"
        assert meta_data["width"] == 256


def test_temporal_imagery_endpoint() -> None:
    settings = make_settings()
    settings.satellite_provider_mode = "mock"
    app = create_app(settings=settings, database=ReadyDatabase())

    with TestClient(app, raise_server_exceptions=False) as client:
        payload = {
            "before_scene_id": "mock-scene-optical-02-before",
            "after_scene_id": "mock-scene-optical-03-after",
            "aoi": SAMPLE_AOI,
            "product_type": "map_preview",
            "before_preset": "true_color",
            "after_preset": "vegetation",
            "output_format": "png",
            "width": 256,
            "height": 256,
        }
        res = client.post("/api/v1/imagery/temporal-request", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "request_id" in data
        assert "before_asset" in data
        assert "after_asset" in data
        assert data["before_asset"]["visualization_preset"] == "true_color"
        assert data["after_asset"]["visualization_preset"] == "vegetation"
        assert data["alignment_status"] in ["aligned", "approximately_aligned"]
