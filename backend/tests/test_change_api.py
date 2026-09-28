"""Integration tests for Change Detection API endpoints."""

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
        width, height = 16, 16
        bbox = (77.5, 12.9, 77.6, 13.0)
        transform = from_bounds(bbox[0], bbox[1], bbox[2], bbox[3], width, height)
        band_names = ["B02", "B03", "B04", "B08", "B11", "B12"]

        # Before data: uniform 0.4
        b_data = np.ones((6, height, width), dtype=np.float32) * 0.4
        b_data[3] = 0.8  # NIR -> NDVI = (0.8 - 0.4) / 1.2 = 0.3333

        # After data: center 8x8 drops NIR to 0.2
        a_data = b_data.copy()
        a_data[3, 4:12, 4:12] = 0.2  # NIR -> NDVI = (0.2 - 0.4) / 0.6 = -0.3333

        with rasterio.io.MemoryFile() as mem_b, rasterio.io.MemoryFile() as mem_a:
            with mem_b.open(
                driver="GTiff",
                height=height,
                width=width,
                count=6,
                dtype="float32",
                crs="EPSG:4326",
                transform=transform,
                nodata=-9999.0,
            ) as dst_b:
                dst_b.write(b_data)
                for i, name in enumerate(band_names):
                    dst_b.set_band_description(i + 1, name)
            b_bytes = bytes(mem_b.getbuffer())

            with mem_a.open(
                driver="GTiff",
                height=height,
                width=width,
                count=6,
                dtype="float32",
                crs="EPSG:4326",
                transform=transform,
                nodata=-9999.0,
            ) as dst_a:
                dst_a.write(a_data)
                for i, name in enumerate(band_names):
                    dst_a.set_band_description(i + 1, name)
            a_bytes = bytes(mem_a.getbuffer())

        metadata_b = RasterMetadata(
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
            scene_id="scene-api-b",
            provider="mock",
            collection="sentinel-2-l2a",
            transform=list(transform)[:6],
        )
        metadata_a = RasterMetadata(
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
            scene_id="scene-api-a",
            provider="mock",
            collection="sentinel-2-l2a",
            transform=list(transform)[:6],
        )

        app_instance = cast(FastAPI, c.app)
        app_instance.state.imagery_service.asset_store.save_asset(
            asset_id="ast-prep-b-api",
            scene_id="scene-api-b",
            product_type=ImageryProductType.ANALYSIS_RASTER,
            format_type=ImageryFormat.GEOTIFF,
            content_type="image/tiff",
            width=width,
            height=height,
            resolution_meters=10.0,
            bbox=bbox,
            crs="EPSG:4326",
            data=b_bytes,
            data_origin=DataOrigin.REAL,
            provider_id="mock",
            bands=band_names,
            raster_metadata=metadata_b,
        )
        app_instance.state.imagery_service.asset_store.save_asset(
            asset_id="ast-prep-a-api",
            scene_id="scene-api-a",
            product_type=ImageryProductType.ANALYSIS_RASTER,
            format_type=ImageryFormat.GEOTIFF,
            content_type="image/tiff",
            width=width,
            height=height,
            resolution_meters=10.0,
            bbox=bbox,
            crs="EPSG:4326",
            data=a_bytes,
            data_origin=DataOrigin.REAL,
            provider_id="mock",
            bands=band_names,
            raster_metadata=metadata_a,
        )

        yield c


def test_list_change_methods_endpoint(client: TestClient) -> None:
    """Verify GET /api/v1/change/methods returns list of supported change methods."""
    response = client.get("/api/v1/change/methods")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] == 5
    methods = [m["method"] for m in payload["methods"]]
    assert "ndvi_difference" in methods
    assert "ndwi_difference" in methods
    assert "ndbi_difference" in methods


def test_calculate_change_endpoint(client: TestClient) -> None:
    """Verify POST /api/v1/change/calculate returns complete change detection result."""
    req_body = {
        "prepared_pair_id": "pair-api-test",
        "before_prepared_asset_id": "ast-prep-b-api",
        "after_prepared_asset_id": "ast-prep-a-api",
        "aoi": {
            "type": "Polygon",
            "coordinates": [[[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]]],
            "area_km2": 120.0,
            "bbox": [77.5, 12.9, 77.6, 13.0],
        },
        "method": "ndvi_difference",
        "generate_overlay": True,
        "generate_evidence": True,
        "generate_regions": True,
    }
    response = client.post("/api/v1/change/calculate", json=req_body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["method"] == "ndvi_difference"
    assert payload["difference_asset_id"].startswith("ast-chg-")
    assert payload["metrics"]["pixel_counts"]["loss_pixels"] == 64  # 8x8 loss
    assert payload["overlay"] is not None
    assert payload["classified_overlay"] is not None

    result_id = payload["result_id"]

    # Test GET /api/v1/change/results/{result_id}
    res_response = client.get(f"/api/v1/change/results/{result_id}")
    assert res_response.status_code == 200
    assert res_response.json()["result_id"] == result_id

    # Test GET /api/v1/change/results/{result_id}/overlay (continuous)
    ovl_response = client.get(f"/api/v1/change/results/{result_id}/overlay")
    assert ovl_response.status_code == 200
    assert ovl_response.headers["content-type"] == "image/png"
    assert ovl_response.content.startswith(b"\x89PNG\r\n\x1a\n")

    # Test GET /api/v1/change/results/{result_id}/overlay?classified=true
    cls_response = client.get(f"/api/v1/change/results/{result_id}/overlay?classified=true")
    assert cls_response.status_code == 200
    assert cls_response.headers["content-type"] == "image/png"
    assert cls_response.content.startswith(b"\x89PNG\r\n\x1a\n")
