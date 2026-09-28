"""Data-integrity tests for Recovery R4: Imagery Identity, AOI-specific Crops, and Cache Keys."""

from __future__ import annotations

import pytest

from satquery.api.schemas.analysis import AOIGeometry, GeometryType
from satquery.api.schemas.imagery import (
    ImageryFormat,
    ImageryProductType,
    ImageryRequest,
    VisualizationPreset,
)
from satquery.core.config import Settings
from satquery.services.asset_store import AssetStore
from satquery.services.imagery_service import ImageryService


def test_different_aois_produce_distinct_cache_keys_and_assets() -> None:
    """Verify two different AOIs within the same Sentinel scene have distinct cache keys."""
    store = AssetStore(storage_dir="tmp/test_r4_assets", default_ttl_seconds=300)
    settings = Settings()
    service = ImageryService(settings=settings, asset_store=store)

    aoi_a = AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=[
            [[77.50, 12.90], [77.55, 12.90], [77.55, 12.95], [77.50, 12.95], [77.50, 12.90]]
        ],
        bbox=(77.50, 12.90, 77.55, 12.95),
    )
    aoi_b = AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=[
            [[77.60, 13.00], [77.65, 13.00], [77.65, 13.05], [77.60, 13.05], [77.60, 13.00]]
        ],
        bbox=(77.60, 13.00, 77.65, 13.05),
    )

    scene_id = "S2B_T43PGQ_20260512T052201_L2A"

    # Request imagery for AOI A
    req_a = ImageryRequest(
        scene_id=scene_id,
        aoi=aoi_a,
        product_type=ImageryProductType.MAP_PREVIEW,
        visualization_preset=VisualizationPreset.TRUE_COLOR,
        output_format=ImageryFormat.PNG,
    )
    asset_a = service.request_imagery(req_a, provider_mode="mock")

    # Request imagery for AOI B
    req_b = ImageryRequest(
        scene_id=scene_id,
        aoi=aoi_b,
        product_type=ImageryProductType.MAP_PREVIEW,
        visualization_preset=VisualizationPreset.TRUE_COLOR,
        output_format=ImageryFormat.PNG,
    )
    asset_b = service.request_imagery(req_b, provider_mode="mock")

    # The two assets must be distinct
    assert asset_a.asset_id != asset_b.asset_id
    assert asset_a.bbox != asset_b.bbox
    assert asset_a.bbox == (77.50, 12.90, 77.55, 12.95)
    assert asset_b.bbox == (77.60, 13.00, 77.65, 13.05)


def test_cache_hit_on_identical_request_and_miss_on_changed_aoi() -> None:
    """Verify cache returns identical asset for identical request and misses when AOI changes."""
    store = AssetStore(storage_dir="tmp/test_r4_assets", default_ttl_seconds=300)
    settings = Settings()
    service = ImageryService(settings=settings, asset_store=store)

    aoi = AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=[
            [[77.50, 12.90], [77.55, 12.90], [77.55, 12.95], [77.50, 12.95], [77.50, 12.90]]
        ],
        bbox=(77.50, 12.90, 77.55, 12.95),
    )

    req = ImageryRequest(
        scene_id="S2B_T43PGQ_20260512T052201_L2A",
        aoi=aoi,
        product_type=ImageryProductType.MAP_PREVIEW,
        visualization_preset=VisualizationPreset.TRUE_COLOR,
        output_format=ImageryFormat.PNG,
    )

    first_asset = service.request_imagery(req, provider_mode="mock")
    second_asset = service.request_imagery(req, provider_mode="mock")

    # Second request hits cache and returns identical asset ID
    assert first_asset.asset_id == second_asset.asset_id

    # Modify AOI slightly -> Cache miss
    aoi_modified = AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=[
            [[77.51, 12.91], [77.56, 12.91], [77.56, 12.96], [77.51, 12.96], [77.51, 12.91]]
        ],
        bbox=(77.51, 12.91, 77.56, 12.96),
    )
    req_modified = ImageryRequest(
        scene_id="S2B_T43PGQ_20260512T052201_L2A",
        aoi=aoi_modified,
        product_type=ImageryProductType.MAP_PREVIEW,
        visualization_preset=VisualizationPreset.TRUE_COLOR,
        output_format=ImageryFormat.PNG,
    )
    third_asset = service.request_imagery(req_modified, provider_mode="mock")
    assert third_asset.asset_id != first_asset.asset_id


@pytest.mark.anyio
async def test_visual_image_manifest_fields_and_aoi_isolation() -> None:
    """Verify ImageManifest populates all Section 3 fields and differentiates distinct AOIs."""
    from satquery.api.schemas.visual import ImageInputRole
    from satquery.services.visual_image_preparer import VisualImagePreparer

    store = AssetStore(storage_dir="tmp/test_r4_assets", default_ttl_seconds=300)
    preparer = VisualImagePreparer(store)

    scene_id = "S2B_T43PGQ_20260512T052201_L2A"
    aoi_a_fingerprint = "vfp-7750-1290-7755-1295"
    aoi_b_fingerprint = "vfp-7760-1300-7765-1305"

    manifest_a, bytes_a = preparer.prepare_manifest_for_asset(
        asset_id=scene_id,
        role=ImageInputRole.SINGLE,
        aoi_fingerprint=aoi_a_fingerprint,
    )

    manifest_b, bytes_b = preparer.prepare_manifest_for_asset(
        asset_id=scene_id,
        role=ImageInputRole.SINGLE,
        aoi_fingerprint=aoi_b_fingerprint,
    )

    # Required Section 3 identity manifest fields
    assert manifest_a.provider is not None
    assert manifest_a.collection is not None
    assert manifest_a.platform == "Sentinel-2"
    assert manifest_a.sensor == "MSI"
    assert manifest_a.media_type == "image/png"
    assert manifest_a.preview_type == "aoi_crop"
    assert manifest_a.content_hash.startswith("sha256:")
    assert manifest_a.submitted_width > 0
    assert manifest_a.submitted_height > 0

    # Distinct AOIs must produce distinct content hashes and payloads
    assert manifest_a.aoi_fingerprint != manifest_b.aoi_fingerprint
    assert manifest_a.content_hash != manifest_b.content_hash
    assert bytes_a != bytes_b


@pytest.mark.anyio
async def test_visual_query_answer_grounded_in_aoi_coordinates() -> None:
    """Verify VisualQueryService returns a grounded answer with observations and evidence references."""
    from satquery.api.schemas.query import WorkspaceContextSnapshot
    from satquery.api.schemas.visual import VisualOperation, VisualQueryRequest
    from satquery.providers.ai.mock import MockAIProvider
    from satquery.services.visual_query_service import VisualQueryService

    store = AssetStore(storage_dir="tmp/test_r4_assets", default_ttl_seconds=300)
    settings = Settings()
    ai_provider = MockAIProvider()
    service = VisualQueryService(settings=settings, asset_store=store, ai_provider=ai_provider)

    aoi = AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=[
            [[77.58, 12.96], [77.62, 12.96], [77.62, 13.00], [77.58, 13.00], [77.58, 12.96]]
        ],
        bbox=(77.58, 12.96, 77.62, 13.00),
    )

    snapshot = WorkspaceContextSnapshot(
        snapshot_id="vsnap-test-01",
        fingerprint="fp-test-aoi-a",
        aoi_geometry=aoi,
        location_label="Bangalore Central",
        scene_ids=["S2A_MSIL2A_20260901T052000"],
    )

    req = VisualQueryRequest(
        question="Describe visible land-cover patterns within the selected area.",
        workspace_id="ws-test",
        context_snapshot=snapshot,
        selected_image_asset_ids=["S2A_MSIL2A_20260901T052000"],
        operation=VisualOperation.DESCRIBE,
    )

    resp = await service.ask_visual_query(req)

    assert resp.answer_id.startswith("vans-")
    assert len(resp.answer) > 20
    assert "S2A_MSIL2A_20260901T052000" in resp.answer or "selected AOI" in resp.answer
    assert len(resp.observations) > 0
    assert len(resp.manifests) == 1
    assert resp.manifests[0].source_scene_id == "S2A_MSIL2A_20260901T052000"
    assert len(resp.grounded_regions) > 0
    # Grounded region WGS84 bounding box must be within reasonable geographic range
    grounded = resp.grounded_regions[0]
    assert grounded.bbox_wgs84 is not None
    min_lon, min_lat, max_lon, max_lat = grounded.bbox_wgs84
    assert min_lon < max_lon
    assert min_lat < max_lat
