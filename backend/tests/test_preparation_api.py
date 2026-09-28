"""API integration tests for raster preparation endpoints."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from conftest import ReadyDatabase, make_settings
from fastapi import FastAPI
from starlette.testclient import TestClient
from test_raster_harmonizer import create_synthetic_geotiff, sample_aoi

from satquery.api.schemas.imagery import (
    ImageryFormat,
    ImageryProductType,
)
from satquery.api.schemas.providers import DataOrigin
from satquery.main import create_app
from satquery.services.asset_store import AssetStore


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = make_settings()
    settings.imagery_storage_dir = tmp_path
    app = create_app(settings=settings, database=ReadyDatabase())
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_prepare_raster_endpoint(client: TestClient) -> None:
    geotiff_bytes = create_synthetic_geotiff()

    app = cast(FastAPI, client.app)
    store: AssetStore = app.state.imagery_service.asset_store
    store.save_asset(
        asset_id="ast-src-api-1",
        scene_id="S2A_20250101",
        product_type=ImageryProductType.ANALYSIS_RASTER,
        format_type=ImageryFormat.GEOTIFF,
        content_type="image/tiff",
        width=100,
        height=100,
        resolution_meters=10.0,
        bbox=(77.58, 12.96, 77.62, 13.00),
        crs="EPSG:4326",
        data=geotiff_bytes,
        provider_id="earth-search",
        data_origin=DataOrigin.REAL,
    )

    aoi = sample_aoi()
    payload = {
        "source_asset_id": "ast-src-api-1",
        "scene_id": "S2A_20250101",
        "aoi": aoi.model_dump(),
        "target_crs": "EPSG:32643",
        "target_resolution_meters": 10.0,
    }

    response = client.post("/api/v1/processing/prepare-raster", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["asset_id"].startswith("ast-prep-")
    assert data["crs"] == "EPSG:32643"
    assert data["valid_data_percent"] > 0.0


def test_prepare_temporal_pair_endpoint(client: TestClient) -> None:
    bytes_b = create_synthetic_geotiff()
    bytes_a = create_synthetic_geotiff()

    app = cast(FastAPI, client.app)
    store: AssetStore = app.state.imagery_service.asset_store
    store.save_asset(
        asset_id="ast-b-api",
        scene_id="S2A_20250101",
        product_type=ImageryProductType.ANALYSIS_RASTER,
        format_type=ImageryFormat.GEOTIFF,
        content_type="image/tiff",
        width=100,
        height=100,
        resolution_meters=10.0,
        bbox=(77.58, 12.96, 77.62, 13.00),
        crs="EPSG:4326",
        data=bytes_b,
        provider_id="earth-search",
        data_origin=DataOrigin.REAL,
    )
    store.save_asset(
        asset_id="ast-a-api",
        scene_id="S2B_20250120",
        product_type=ImageryProductType.ANALYSIS_RASTER,
        format_type=ImageryFormat.GEOTIFF,
        content_type="image/tiff",
        width=100,
        height=100,
        resolution_meters=10.0,
        bbox=(77.58, 12.96, 77.62, 13.00),
        crs="EPSG:4326",
        data=bytes_a,
        provider_id="earth-search",
        data_origin=DataOrigin.REAL,
    )

    aoi = sample_aoi()
    payload = {
        "pair_id": "pair-api-1",
        "before_asset_id": "ast-b-api",
        "after_asset_id": "ast-a-api",
        "aoi": aoi.model_dump(),
        "target_crs": "EPSG:32643",
        "target_resolution_meters": 10.0,
    }

    response = client.post("/api/v1/processing/prepare-temporal-pair", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["common_crs"] == "EPSG:32643"
    assert data["ready_for_analysis"] is True
    assert data["before_asset"]["asset_id"].startswith("ast-prep-")
    assert data["after_asset"]["asset_id"].startswith("ast-prep-")


def test_prepare_raster_unknown_asset_returns_404(client: TestClient) -> None:
    aoi = sample_aoi()
    payload = {
        "source_asset_id": "ast-nonexistent",
        "scene_id": "S2A_20250101",
        "aoi": aoi.model_dump(),
    }
    response = client.post("/api/v1/processing/prepare-raster", json=payload)
    assert response.status_code == 404
