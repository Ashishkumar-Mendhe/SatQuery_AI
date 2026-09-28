from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
import rasterio
from conftest import make_settings
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from satquery.api.schemas.analysis import (
    AOIGeometry,
    ConfidenceBreakdown,
    EvidenceItem,
    EvidenceProvenance,
    EvidenceType,
    GeometryType,
)
from satquery.api.schemas.change import (
    ChangeDetectionDefinition,
    ChangeDetectionMethod,
    ChangeDetectionResult,
    ChangeDirectionality,
    ChangeMetrics,
    ChangePixelCounts,
    ChangeRegion,
    ChangeThresholdConfig,
    ThresholdStrategy,
)
from satquery.api.schemas.imagery import (
    ImageryFormat,
    ImageryProductType,
)
from satquery.api.schemas.preparation import RasterProvenance
from satquery.api.schemas.providers import DataOrigin
from satquery.api.schemas.query import (
    WorkspaceContextSnapshot,
)
from satquery.api.schemas.visual import (
    CoordinateStatus,
    ImageInputRole,
    ObservationSource,
    VisualOperation,
    VisualQueryRequest,
)
from satquery.providers.ai.mock import MockAIProvider
from satquery.services.asset_store import AssetStore
from satquery.services.visual_image_preparer import VisualImagePreparer
from satquery.services.visual_query_service import VisualQueryService


def create_synthetic_geotiff_bytes() -> bytes:
    """Create a small in-memory 3-band GeoTIFF."""
    arr = np.ones((3, 100, 100), dtype=np.uint8) * 128
    transform = from_origin(500000.0, 2400000.0, 10.0, 10.0)

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with rasterio.open(
            tmp_path,
            "w",
            driver="GTiff",
            height=100,
            width=100,
            count=3,
            dtype="uint8",
            crs="EPSG:32644",
            transform=transform,
        ) as dst:
            dst.write(arr)
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.fixture
def asset_store(tmp_path: Path) -> AssetStore:
    return AssetStore(storage_dir=tmp_path / "assets")


@pytest.fixture
def mock_change_result() -> ChangeDetectionResult:
    return ChangeDetectionResult(
        result_id="chg-1",
        pair_id="pair-1",
        method=ChangeDetectionMethod.NDVI_DIFFERENCE,
        definition=ChangeDetectionDefinition(
            method=ChangeDetectionMethod.NDVI_DIFFERENCE,
            display_name="NDVI Difference",
            formula="NDVI_after - NDVI_before",
            input_type="spectral_index",
            directionality=ChangeDirectionality.BIDIRECTIONAL,
            expected_range=(-2.0, 2.0),
            default_threshold_config=ChangeThresholdConfig(),
            description="Test NDVI difference",
            limitations="Vegetation canopy response only",
        ),
        before_scene_id="S2-A",
        after_scene_id="S2-B",
        before_asset_id="ast-prep-a",
        after_asset_id="ast-prep-b",
        difference_asset_id="ast-chg-1",
        metrics=ChangeMetrics(
            gain_area_km2=0.0,
            loss_area_km2=0.2,
            stable_area_km2=0.8,
            net_change_area_km2=-0.2,
            shared_valid_area_km2=1.0,
            positive_threshold_applied=0.15,
            negative_threshold_applied=-0.15,
            threshold_strategy=ThresholdStrategy.FIXED,
            pixel_counts=ChangePixelCounts(
                total_aoi_pixels=1000,
                shared_valid_pixels=1000,
                gain_pixels=0,
                loss_pixels=200,
                stable_pixels=800,
                uncertain_pixels=0,
                gain_percent=0.0,
                loss_percent=20.0,
                stable_percent=80.0,
                uncertain_percent=0.0,
            ),
        ),
        regions=[
            ChangeRegion(
                id="reg-1",
                category="spectral_loss",
                geometry=AOIGeometry(
                    type=GeometryType.POLYGON,
                    coordinates=[
                        [[77.0, 21.0], [78.0, 21.0], [78.0, 22.0], [77.0, 22.0], [77.0, 21.0]]
                    ],
                ),
                area_km2=0.2,
                pixel_count=200,
                mean_magnitude=-0.4,
                min_magnitude=-0.6,
                max_magnitude=-0.2,
                threshold_rule="Delta NDVI < -0.15",
                evidence_id="ev-1",
                confidence=0.85,
            )
        ],
        evidence=[
            EvidenceItem(
                id="ev-1",
                type=EvidenceType.CHANGE_MEASUREMENT,
                title="NDVI Vegetation Loss Cluster",
                description="Cluster of significant NDVI reduction",
                source_scene_ids=["S2-A", "S2-B"],
                observed_at=datetime(2026, 9, 15, tzinfo=UTC),
                confidence=0.85,
                provenance=EvidenceProvenance(
                    computation="ndvi_diff",
                    processed_at=datetime(2026, 9, 20, tzinfo=UTC),
                ),
            )
        ],
        confidence_breakdown=ConfidenceBreakdown(
            overall=0.85,
            data_quality=0.85,
            temporal_quality=0.90,
            spatial_quality=1.0,
            model_confidence=0.85,
            evidence_agreement=0.85,
            methodology="Standard multi-factor score",
        ),
        confidence=0.85,
        provenance=RasterProvenance(
            pipeline_version="1.0.0",
            source_asset_ids=["ast-prep-a", "ast-prep-b"],
            source_scene_ids=["S2-A", "S2-B"],
            operations=[],
            parameters={},
            software="SatQuery",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_milliseconds=100.0,
        ),
        created_at=datetime.now(UTC),
    )


def test_visual_image_preparer_geotiff(asset_store: AssetStore) -> None:
    tif_bytes = create_synthetic_geotiff_bytes()
    asset = asset_store.save_asset(
        scene_id="scene-test-1",
        product_type=ImageryProductType.MAP_PREVIEW,
        format_type=ImageryFormat.GEOTIFF,
        content_type="image/tiff",
        width=100,
        height=100,
        resolution_meters=10.0,
        bbox=(500000.0, 2399000.0, 501000.0, 2400000.0),
        crs="EPSG:32644",
        data=tif_bytes,
        provider_id="sentinel-hub",
        data_origin=DataOrigin.MOCK,
    )

    preparer = VisualImagePreparer(asset_store)
    manifest, png_bytes = preparer.prepare_manifest_for_asset(
        asset_id=asset.asset_id,
        role=ImageInputRole.SINGLE,
        aoi_fingerprint="test-fp",
    )

    assert manifest.source_asset_id == asset.asset_id
    assert manifest.source_scene_id == "scene-test-1"
    assert manifest.role == ImageInputRole.SINGLE
    assert manifest.submitted_width == 100
    assert manifest.submitted_height == 100
    assert manifest.crs == "EPSG:32644"
    assert manifest.affine_transform is not None
    assert manifest.content_hash.startswith("sha256:")
    assert len(png_bytes) > 0


@pytest.mark.anyio
async def test_visual_query_service_single_image(
    asset_store: AssetStore, mock_change_result: ChangeDetectionResult
) -> None:
    tif_bytes = create_synthetic_geotiff_bytes()
    asset = asset_store.save_asset(
        scene_id="scene-test-1",
        product_type=ImageryProductType.MAP_PREVIEW,
        format_type=ImageryFormat.GEOTIFF,
        content_type="image/tiff",
        width=100,
        height=100,
        resolution_meters=10.0,
        bbox=(500000.0, 2399000.0, 501000.0, 2400000.0),
        crs="EPSG:32644",
        data=tif_bytes,
        provider_id="sentinel-hub",
        data_origin=DataOrigin.MOCK,
    )

    mock_provider = MockAIProvider(model_id="mock-vlm-1")
    service = VisualQueryService(
        settings=make_settings(),
        asset_store=asset_store,
        ai_provider=mock_provider,
    )

    snapshot = WorkspaceContextSnapshot(
        snapshot_id="snap-1",
        fingerprint="fp-test",
        aoi_geometry=AOIGeometry(
            type=GeometryType.POLYGON,
            coordinates=[[[77.0, 21.0], [78.0, 21.0], [78.0, 22.0], [77.0, 22.0], [77.0, 21.0]]],
        ),
    )

    request = VisualQueryRequest(
        question="Highlight the prominent region in the image",
        context_snapshot=snapshot,
        selected_image_asset_ids=[asset.asset_id],
        operation=VisualOperation.LOCATE,
    )

    resp = await service.ask_visual_query(request)

    assert resp.answer_id.startswith("vans-")
    assert len(resp.observations) >= 1
    assert len(resp.grounded_regions) >= 1
    assert resp.manifests[0].source_asset_id == asset.asset_id
    assert resp.observations[0].observation_source == ObservationSource.MODEL_PREDICTION
    assert resp.observations[0].coordinate_status in (
        CoordinateStatus.VALID,
        CoordinateStatus.PARTIAL_CLAMPED,
    )


@pytest.mark.anyio
async def test_visual_query_service_bitemporal_compare(
    asset_store: AssetStore, mock_change_result: ChangeDetectionResult
) -> None:
    tif_bytes = create_synthetic_geotiff_bytes()
    asset1 = asset_store.save_asset(
        scene_id="scene-before",
        product_type=ImageryProductType.MAP_PREVIEW,
        format_type=ImageryFormat.GEOTIFF,
        content_type="image/tiff",
        width=100,
        height=100,
        resolution_meters=10.0,
        bbox=(500000.0, 2399000.0, 501000.0, 2400000.0),
        crs="EPSG:32644",
        data=tif_bytes,
        provider_id="sentinel-hub",
        data_origin=DataOrigin.MOCK,
    )
    asset2 = asset_store.save_asset(
        scene_id="scene-after",
        product_type=ImageryProductType.MAP_PREVIEW,
        format_type=ImageryFormat.GEOTIFF,
        content_type="image/tiff",
        width=100,
        height=100,
        resolution_meters=10.0,
        bbox=(500000.0, 2399000.0, 501000.0, 2400000.0),
        crs="EPSG:32644",
        data=tif_bytes,
        provider_id="sentinel-hub",
        data_origin=DataOrigin.MOCK,
    )

    mock_provider = MockAIProvider(model_id="mock-vlm-1")
    service = VisualQueryService(
        settings=make_settings(),
        asset_store=asset_store,
        ai_provider=mock_provider,
    )

    snapshot = WorkspaceContextSnapshot(
        snapshot_id="snap-1",
        fingerprint="fp-test",
        aoi_geometry=AOIGeometry(
            type=GeometryType.POLYGON,
            coordinates=[[[77.0, 21.0], [78.0, 21.0], [78.0, 22.0], [77.0, 22.0], [77.0, 21.0]]],
        ),
    )

    request = VisualQueryRequest(
        question="What visual differences are apparent between these dates?",
        context_snapshot=snapshot,
        selected_image_asset_ids=[asset1.asset_id, asset2.asset_id],
        operation=VisualOperation.COMPARE,
    )

    resp = await service.ask_visual_query(request)

    assert len(resp.manifests) == 2
    assert resp.manifests[0].role == ImageInputRole.BEFORE
    assert resp.manifests[1].role == ImageInputRole.AFTER
    assert "visual difference" in resp.answer.lower() or "candidate" in resp.answer.lower()


def test_visual_api_endpoints(ready_client: TestClient) -> None:
    # 1. Capabilities
    cap_resp = ready_client.get("/api/v1/query/visual/capabilities")
    assert cap_resp.status_code == 200
    cap_json = cap_resp.json()
    assert cap_json["supports_bounding_boxes"] is True
    assert cap_json["max_images_per_query"] == 2
    assert "describe" in cap_json["supported_operations"]
