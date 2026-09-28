"""Tests for SpectralService orchestration, AssetStore persistence, and temporal workflows."""

from pathlib import Path

import numpy as np
import pytest
import rasterio
from conftest import make_settings
from rasterio.transform import from_bounds

from satquery.api.schemas.analysis import AOIGeometry
from satquery.api.schemas.imagery import (
    ImageryFormat,
    ImageryProductType,
    RasterMetadata,
)
from satquery.api.schemas.providers import DataOrigin
from satquery.api.schemas.spectral import (
    SpectralIndexName,
    SpectralIndexRequest,
    TemporalSpectralRequest,
)
from satquery.core.config import Settings
from satquery.services.asset_store import AssetStore
from satquery.services.spectral_service import SpectralService


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
def prepared_geotiff_asset(mock_asset_store: AssetStore) -> str:
    """Create a synthetic 6-band prepared analysis raster in AssetStore."""
    asset_id = "ast-prep-test12345"
    width, height = 32, 32
    bbox = (77.5, 12.9, 77.6, 13.0)
    transform = from_bounds(bbox[0], bbox[1], bbox[2], bbox[3], width, height)

    # 6 bands: B02 (blue), B03 (green), B04 (red), B08 (nir), B11 (swir1), B12 (swir2)
    band_names = ["B02", "B03", "B04", "B08", "B11", "B12"]
    data = np.zeros((6, height, width), dtype=np.float32)

    data[0] = 0.15  # Blue
    data[1] = 0.25  # Green
    data[2] = 0.20  # Red
    data[3] = 0.70  # NIR (high vegetation response)
    data[4] = 0.30  # SWIR1
    data[5] = 0.20  # SWIR2

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
        scene_id="mock-scene-1",
        provider="mock",
        collection="sentinel-2-l2a",
        transform=list(transform)[:6],
    )

    mock_asset_store.save_asset(
        asset_id=asset_id,
        scene_id="mock-scene-1",
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

    return asset_id


def test_calculate_single_ndvi(
    test_settings: Settings,
    mock_asset_store: AssetStore,
    prepared_geotiff_asset: str,
) -> None:
    """Verify single-scene NDVI calculation, derived asset generation, and evidence."""
    service = SpectralService(settings=test_settings, asset_store=mock_asset_store)

    aoi = AOIGeometry(
        type="Polygon",
        coordinates=[[[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]]],
        area_km2=120.0,
        bbox=[77.5, 12.9, 77.6, 13.0],
    )

    req = SpectralIndexRequest(
        prepared_asset_id=prepared_geotiff_asset,
        scene_id="mock-scene-1",
        aoi=aoi,
        index_name=SpectralIndexName.NDVI,
    )

    result = service.calculate_single(req)

    assert result.index_name == SpectralIndexName.NDVI
    assert result.scene_id == "mock-scene-1"
    assert result.output_asset_id.startswith("ast-spec-")
    assert result.preview_asset_id is not None
    assert result.preview_asset_id.startswith("ast-specprv-")

    # Verify statistics: NIR=0.70, Red=0.20 -> (0.7 - 0.2) / (0.7 + 0.2) = 0.5 / 0.9 = ~0.5556
    assert result.statistics.valid_pixel_count == 32 * 32
    assert result.statistics.mean is not None
    assert np.isclose(result.statistics.mean, 0.5556, atol=1e-3)
    assert result.statistics.valid_data_percent == 100.0

    # Verify evidence item
    assert len(result.evidence) == 1
    evd = result.evidence[0]
    assert evd.index_name == SpectralIndexName.NDVI
    assert evd.result_asset_id == result.output_asset_id
    assert evd.confidence >= 0.80

    # Verify overlay feature
    assert result.overlay is not None
    assert result.overlay.raster_url == f"/api/v1/imagery/assets/{result.preview_asset_id}"

    # Verify derived assets are persisted in AssetStore
    geotiff_record = mock_asset_store.get_asset(result.output_asset_id)
    assert geotiff_record.asset.product_type == ImageryProductType.ANALYSIS_RASTER
    assert geotiff_record.asset.format == ImageryFormat.GEOTIFF

    preview_record = mock_asset_store.get_asset(result.preview_asset_id)
    assert preview_record.asset.product_type == ImageryProductType.MAP_PREVIEW
    assert preview_record.asset.format == ImageryFormat.PNG


def test_calculate_temporal_spectral_pair(
    test_settings: Settings,
    mock_asset_store: AssetStore,
    prepared_geotiff_asset: str,
) -> None:
    """Verify bi-temporal spectral calculation computes side-by-side independent results."""
    service = SpectralService(settings=test_settings, asset_store=mock_asset_store)

    aoi = AOIGeometry(
        type="Polygon",
        coordinates=[[[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]]],
        area_km2=120.0,
        bbox=[77.5, 12.9, 77.6, 13.0],
    )

    req = TemporalSpectralRequest(
        prepared_pair_id="prep-pair-1",
        before_prepared_asset_id=prepared_geotiff_asset,
        after_prepared_asset_id=prepared_geotiff_asset,
        aoi=aoi,
        index_name=SpectralIndexName.NDWI,
    )

    temporal_result = service.calculate_temporal(req)

    assert temporal_result.pair_id == "prep-pair-1"
    assert temporal_result.index_name == SpectralIndexName.NDWI
    assert temporal_result.before_result.index_name == SpectralIndexName.NDWI
    assert temporal_result.after_result.index_name == SpectralIndexName.NDWI
    assert temporal_result.shared_valid_percent == 100.0
    assert len(temporal_result.comparability_warnings) == 0
