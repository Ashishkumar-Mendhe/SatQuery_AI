"""Unit tests for the AssetStore disk cache and lifecycle manager."""

from __future__ import annotations

import tempfile
import time
from collections.abc import Generator

import pytest

from satquery.api.schemas.imagery import ImageryFormat, ImageryProductType
from satquery.services.asset_store import (
    AssetExpiredError,
    AssetNotFoundError,
    AssetStore,
)


@pytest.fixture
def temp_store() -> Generator[AssetStore]:
    with tempfile.TemporaryDirectory() as temp_dir:
        yield AssetStore(storage_dir=temp_dir, default_ttl_seconds=2)


def test_save_and_retrieve_asset(temp_store: AssetStore) -> None:
    sample_data = b"\x89PNG\r\n\x1a\nFakePNGContent"
    asset = temp_store.save_asset(
        scene_id="S2A_TEST_01",
        product_type=ImageryProductType.MAP_PREVIEW,
        format_type=ImageryFormat.PNG,
        content_type="image/png",
        width=256,
        height=256,
        resolution_meters=10.0,
        bbox=(77.45, 12.85, 77.75, 13.15),
        crs="EPSG:3857",
        data=sample_data,
        provider_id="mock",
    )
    assert asset.asset_id.startswith("img-")
    assert asset.size_bytes == len(sample_data)

    data, content_type, retrieved_asset = temp_store.get_asset_bytes(asset.asset_id)
    assert data == sample_data
    assert content_type == "image/png"
    assert retrieved_asset.asset_id == asset.asset_id


def test_asset_cache_key_hit(temp_store: AssetStore) -> None:
    cache_key = temp_store.generate_cache_key(
        provider_id="mock",
        scene_id="S2A_01",
        aoi_fingerprint="77.45,12.85,77.75,13.15",
        product_type="map_preview",
        preset="true_color",
        format_type="png",
        width=256,
        height=256,
        resolution_meters=10.0,
    )
    sample_data = b"\x89PNG\r\n\x1a\nCachedContent"
    asset = temp_store.save_asset(
        scene_id="S2A_01",
        product_type=ImageryProductType.MAP_PREVIEW,
        format_type=ImageryFormat.PNG,
        content_type="image/png",
        width=256,
        height=256,
        resolution_meters=10.0,
        bbox=(77.45, 12.85, 77.75, 13.15),
        crs="EPSG:3857",
        data=sample_data,
        provider_id="mock",
        cache_key=cache_key,
    )

    cached_record = temp_store.get_by_cache_key(cache_key)
    assert cached_record is not None
    assert cached_record.asset.asset_id == asset.asset_id


def test_asset_not_found(temp_store: AssetStore) -> None:
    with pytest.raises(AssetNotFoundError):
        temp_store.get_asset("non-existent-asset-id")


def test_asset_expiration(temp_store: AssetStore) -> None:
    sample_data = b"\x89PNG\r\n\x1a\nExpiringContent"
    asset = temp_store.save_asset(
        scene_id="S2A_EXP",
        product_type=ImageryProductType.MAP_PREVIEW,
        format_type=ImageryFormat.PNG,
        content_type="image/png",
        width=256,
        height=256,
        resolution_meters=10.0,
        bbox=(77.45, 12.85, 77.75, 13.15),
        crs="EPSG:3857",
        data=sample_data,
        provider_id="mock",
        ttl_seconds=1,
    )
    time.sleep(1.1)
    with pytest.raises(AssetExpiredError):
        temp_store.get_asset(asset.asset_id)
