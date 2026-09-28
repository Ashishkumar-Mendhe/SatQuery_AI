"""Integration tests for spectral analysis API endpoints."""

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import numpy as np
import pytest
import rasterio
from conftest import ReadyDatabase, make_settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rasterio.transform import from_bounds

from satquery.api.schemas.imagery import (
    ImageryFormat,
    ImageryProductType,
    RasterMetadata,
)
from satquery.api.schemas.providers import DataOrigin
from satquery.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = make_settings()
    settings.imagery_storage_dir = tmp_path / "imagery_cache"
    settings.imagery_asset_cache_ttl_seconds = 3600
    app = create_app(settings=settings, database=ReadyDatabase())

    with TestClient(app, raise_server_exceptions=False) as c:
        # Seed a synthetic prepared analysis raster into the running app's asset_store
        width, height = 16, 16
        bbox = (77.5, 12.9, 77.6, 13.0)
        transform = from_bounds(bbox[0], bbox[1], bbox[2], bbox[3], width, height)
        band_names = ["B02", "B03", "B04", "B08", "B11", "B12"]
        data = np.ones((6, height, width), dtype=np.float32) * 0.4
        data[3] = 0.8  # NIR

        with rasterio.io.MemoryFile() as memfile:
            with memfile.open(
                driver="GTiff",
                height=height,
                width=width,
                count=6,
                dtype="float32",
                crs="EPSG:4326",
                transform=transform,
                nodata=-9999.0,
            ) as dst:
                dst.write(data)
                for i, name in enumerate(band_names):
                    dst.set_band_description(i + 1, name)
            geotiff_bytes = bytes(memfile.getbuffer())

        metadata = RasterMetadata(
            crs="EPSG:4326",
            bbox=bbox,
            width=width,
            height=height,
            pixel_size_x=abs(transform[0]),
            pixel_size_y=abs(transform[4]),
            band_count=6,
            band_names=band_names,
            data_type="float32",
            no_data_values=[-9999.0] * 6,
            scene_id="scene-api-test",
            provider="mock",
            collection="sentinel-2-l2a",
            transform=list(transform)[:6],
        )

        app_instance = cast(FastAPI, c.app)
        app_instance.state.imagery_service.asset_store.save_asset(
            asset_id="ast-prep-api-test",
            scene_id="scene-api-test",
            product_type=ImageryProductType.ANALYSIS_RASTER,
            format_type=ImageryFormat.GEOTIFF,
            content_type="image/tiff",
            width=width,
            height=height,
            resolution_meters=10.0,
            bbox=bbox,
            crs="EPSG:4326",
            data=geotiff_bytes,
            data_origin=DataOrigin.REAL,
            provider_id="mock",
            bands=band_names,
            raster_metadata=metadata,
        )

        yield c


def test_list_spectral_indices_endpoint(client: TestClient) -> None:
    """Verify GET /api/v1/spectral/indices returns list of supported indices."""
    response = client.get("/api/v1/spectral/indices")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] == 6
    index_names = [item["name"] for item in payload["indices"]]
    assert "ndvi" in index_names
    assert "ndwi" in index_names
    assert "ndbi" in index_names


def test_calculate_spectral_index_endpoint(client: TestClient) -> None:
    """Verify POST /api/v1/spectral/calculate returns full result envelope."""
    req_body = {
        "prepared_asset_id": "ast-prep-api-test",
        "scene_id": "scene-api-test",
        "aoi": {
            "type": "Polygon",
            "coordinates": [[[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]]],
            "area_km2": 120.0,
            "bbox": [77.5, 12.9, 77.6, 13.0],
        },
        "index_name": "ndvi",
        "generate_overlay": True,
        "generate_evidence": True,
    }
    response = client.post("/api/v1/spectral/calculate", json=req_body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["index_name"] == "ndvi"
    assert payload["output_asset_id"].startswith("ast-spec-")
    assert payload["statistics"]["valid_pixel_count"] == 16 * 16
    assert len(payload["evidence"]) == 1
    assert payload["overlay"] is not None

    result_id = payload["result_id"]

    # Test GET /api/v1/spectral/results/{result_id}
    res_response = client.get(f"/api/v1/spectral/results/{result_id}")
    assert res_response.status_code == 200
    assert res_response.json()["result_id"] == result_id

    # Test GET /api/v1/spectral/results/{result_id}/overlay
    ovl_response = client.get(f"/api/v1/spectral/results/{result_id}/overlay")
    assert ovl_response.status_code == 200
    assert ovl_response.headers["content-type"] == "image/png"
    assert ovl_response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_calculate_temporal_spectral_index_endpoint(client: TestClient) -> None:
    """Verify POST /api/v1/spectral/calculate-temporal returns before and after results."""
    req_body = {
        "prepared_pair_id": "prep-pair-api-test",
        "before_prepared_asset_id": "ast-prep-api-test",
        "after_prepared_asset_id": "ast-prep-api-test",
        "aoi": {
            "type": "Polygon",
            "coordinates": [[[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]]],
            "area_km2": 120.0,
            "bbox": [77.5, 12.9, 77.6, 13.0],
        },
        "index_name": "ndwi",
        "generate_overlays": True,
        "generate_evidence": True,
    }
    response = client.post("/api/v1/spectral/calculate-temporal", json=req_body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["index_name"] == "ndwi"
    assert payload["before_result"]["index_name"] == "ndwi"
    assert payload["after_result"]["index_name"] == "ndwi"
    assert payload["shared_valid_percent"] == 100.0
