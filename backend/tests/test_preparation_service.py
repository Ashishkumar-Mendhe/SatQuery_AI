"""Unit tests for PreparationService."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import make_settings
from test_raster_harmonizer import create_synthetic_geotiff, sample_aoi

from satquery.api.schemas.imagery import (
    ImageryFormat,
    ImageryProductType,
)
from satquery.api.schemas.preparation import (
    RasterPreparationRequest,
    TemporalRasterPreparationRequest,
)
from satquery.api.schemas.providers import DataOrigin
from satquery.services.asset_store import AssetStore
from satquery.services.preparation_service import PreparationService


@pytest.fixture
def temp_service(tmp_path: Path) -> PreparationService:
    settings = make_settings()
    settings.imagery_storage_dir = tmp_path
    settings.imagery_asset_cache_ttl_seconds = 3600
    store = AssetStore(storage_dir=tmp_path, default_ttl_seconds=3600)
    return PreparationService(settings=settings, asset_store=store)


def test_prepare_single_raster_service(temp_service: PreparationService) -> None:
    geotiff_bytes = create_synthetic_geotiff()
    temp_service.asset_store.save_asset(
        asset_id="ast-source-1",
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

    req = RasterPreparationRequest(
        source_asset_id="ast-source-1",
        scene_id="S2A_20250101",
        aoi=sample_aoi(),
        target_crs="EPSG:32643",
        target_resolution_meters=10.0,
    )

    prep_asset = temp_service.prepare_single_raster(req)
    assert prep_asset.asset_id.startswith("ast-prep-")
    assert prep_asset.crs == "EPSG:32643"
    assert prep_asset.valid_data_percent > 0
    assert temp_service.asset_store.asset_exists(prep_asset.asset_id)


def test_prepare_temporal_pair_service(temp_service: PreparationService) -> None:
    bytes_b = create_synthetic_geotiff()
    bytes_a = create_synthetic_geotiff()

    temp_service.asset_store.save_asset(
        asset_id="ast-b-1",
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
    temp_service.asset_store.save_asset(
        asset_id="ast-a-1",
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

    req = TemporalRasterPreparationRequest(
        pair_id="pair-123",
        before_asset_id="ast-b-1",
        after_asset_id="ast-a-1",
        aoi=sample_aoi(),
        target_crs="EPSG:32643",
        target_resolution_meters=10.0,
    )

    pair = temp_service.prepare_temporal_pair(req)
    assert pair.common_crs == "EPSG:32643"
    assert pair.before_asset.asset_id.startswith("ast-prep-")
    assert pair.after_asset.asset_id.startswith("ast-prep-")
    assert pair.ready_for_analysis is True
