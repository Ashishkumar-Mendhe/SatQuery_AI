"""Tests for ChangeService orchestration, asset store integration, and metrics."""

from pathlib import Path

import numpy as np
import pytest
import rasterio
from conftest import make_settings
from rasterio.transform import from_bounds

from satquery.api.schemas.analysis import AOIGeometry
from satquery.api.schemas.change import (
    ChangeDetectionMethod,
    ChangeDetectionRequest,
    ChangeThresholdConfig,
    ThresholdStrategy,
)
from satquery.api.schemas.imagery import (
    ImageryFormat,
    ImageryProductType,
    RasterMetadata,
)
from satquery.api.schemas.providers import DataOrigin
from satquery.core.config import Settings
from satquery.services.asset_store import AssetStore
from satquery.services.change_service import ChangeService


@pytest.fixture
def mock_asset_store(tmp_path: Path) -> AssetStore:
    return AssetStore(storage_dir=str(tmp_path / "imagery_cache"))


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    settings = make_settings()
    settings.imagery_storage_dir = tmp_path / "imagery_cache"
    settings.imagery_asset_cache_ttl_seconds = 3600
    return settings


@pytest.fixture
def prepared_temporal_pair_assets(mock_asset_store: AssetStore) -> tuple[str, str]:
    """Create a synthetic co-registered before/after prepared pair in AssetStore."""
    width, height = 32, 32
    bbox = (77.5, 12.9, 77.6, 13.0)
    transform = from_bounds(bbox[0], bbox[1], bbox[2], bbox[3], width, height)
    band_names = ["B02", "B03", "B04", "B08", "B11", "B12"]

    # Before raster: high vegetation (NIR=0.70, Red=0.20 -> NDVI = 0.5556)
    b_data = np.zeros((6, height, width), dtype=np.float32)
    b_data[0] = 0.15  # Blue
    b_data[1] = 0.25  # Green
    b_data[2] = 0.20  # Red
    b_data[3] = 0.70  # NIR
    b_data[4] = 0.30  # SWIR1
    b_data[5] = 0.20  # SWIR2

    # After raster: lower vegetation in center (NIR=0.30, Red=0.30 -> NDVI = 0.00)
    a_data = b_data.copy()
    a_data[2, 8:24, 8:24] = 0.30  # Red
    a_data[3, 8:24, 8:24] = 0.30  # NIR -> NDVI drops to 0.00 (Loss of ~ -0.5556)

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
        scene_id="scene-before-1",
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
        scene_id="scene-after-1",
        provider="mock",
        collection="sentinel-2-l2a",
        transform=list(transform)[:6],
    )

    before_id = "ast-prep-b-test"
    after_id = "ast-prep-a-test"

    mock_asset_store.save_asset(
        asset_id=before_id,
        scene_id="scene-before-1",
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
    mock_asset_store.save_asset(
        asset_id=after_id,
        scene_id="scene-after-1",
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

    return before_id, after_id


def test_calculate_change_ndvi_difference(
    test_settings: Settings,
    mock_asset_store: AssetStore,
    prepared_temporal_pair_assets: tuple[str, str],
) -> None:
    """Verify change detection calculation, metric accounting, and asset persistence."""
    before_id, after_id = prepared_temporal_pair_assets
    service = ChangeService(settings=test_settings, asset_store=mock_asset_store)

    aoi = AOIGeometry(
        type="Polygon",
        coordinates=[[[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]]],
        area_km2=120.0,
        bbox=[77.5, 12.9, 77.6, 13.0],
    )

    req = ChangeDetectionRequest(
        prepared_pair_id="prep-pair-test",
        before_prepared_asset_id=before_id,
        after_prepared_asset_id=after_id,
        aoi=aoi,
        method=ChangeDetectionMethod.NDVI_DIFFERENCE,
        threshold_config=ChangeThresholdConfig(
            strategy=ThresholdStrategy.FIXED,
            positive_threshold=0.15,
            negative_threshold=-0.15,
            min_cluster_size_pixels=5,
        ),
        generate_overlay=True,
        generate_evidence=True,
        generate_regions=True,
    )

    result = service.calculate_change(req)

    assert result.method == ChangeDetectionMethod.NDVI_DIFFERENCE
    assert result.difference_asset_id.startswith("ast-chg-")
    assert result.preview_asset_id is not None
    assert result.preview_asset_id.startswith("ast-chgprv-")
    assert result.classified_preview_asset_id is not None
    assert result.classified_preview_asset_id.startswith("ast-chgcls-")

    # Metrics verification: 16x16 = 256 loss pixels out of 32x32 = 1024 total pixels (25.0%)
    assert result.metrics.pixel_counts.loss_pixels == 256
    assert result.metrics.pixel_counts.gain_pixels == 0
    assert result.metrics.pixel_counts.stable_pixels == 768
    assert np.isclose(result.metrics.pixel_counts.loss_percent, 25.0, atol=1e-2)

    # Regions verification
    assert len(result.regions) >= 1
    loss_reg = [r for r in result.regions if r.category == "spectral_loss"]
    assert len(loss_reg) == 1
    assert loss_reg[0].pixel_count == 256

    # Evidence items
    assert len(result.evidence) == 1
    assert result.confidence >= 0.85

    # Overlays
    assert result.overlay is not None
    assert result.classified_overlay is not None

    # Retrieve from cache
    cached = service.get_result(result.result_id)
    assert cached.result_id == result.result_id
