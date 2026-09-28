"""Tests for FusionService orchestration and end-to-end evidence fusion."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import make_settings
from rasterio.io import MemoryFile
from rasterio.transform import Affine

from satquery.api.schemas.analysis import (
    AOIGeometry,
    ConfidenceBreakdown,
    GeometryType,
)
from satquery.api.schemas.change import (
    ChangeDetectionDefinition,
    ChangeDetectionMethod,
    ChangeDetectionResult,
    ChangeDirectionality,
    ChangeMetrics,
    ChangePixelCounts,
    ChangeThresholdConfig,
)
from satquery.api.schemas.fusion import (
    FusionCapabilitiesResponse,
    FusionRequest,
    FusionResult,
    FusionRuleId,
    SARThresholdConfig,
)
from satquery.api.schemas.imagery import (
    ImageryFormat,
    ImageryProductType,
)
from satquery.api.schemas.preparation import RasterProvenance
from satquery.api.schemas.providers import DataOrigin
from satquery.services.asset_store import AssetStore
from satquery.services.change_service import ChangeService
from satquery.services.fusion_service import FusionService


def _create_sample_geotiff(
    data: np.ndarray[Any, Any],
    transform: list[float],
    crs: str = "EPSG:32631",
    nodata: float = -9999.0,
) -> bytes:
    with MemoryFile() as mem:
        with mem.open(
            driver="GTiff",
            height=data.shape[0],
            width=data.shape[1],
            count=1,
            dtype="float32",
            crs=crs,
            transform=Affine(*transform),
            nodata=nodata,
        ) as dst:
            dst.write(data.astype(np.float32), 1)
        return bytes(mem.getbuffer())


@pytest.fixture
def fusion_setup(tmp_path: Path) -> tuple[FusionService, AssetStore, ChangeService]:
    settings = make_settings()
    settings.imagery_storage_dir = tmp_path / "imagery"
    settings.imagery_asset_cache_ttl_seconds = 3600
    settings.max_imagery_file_size_bytes = 50_000_000
    store = AssetStore(storage_dir=settings.imagery_storage_dir)
    change_svc = ChangeService(settings=settings, asset_store=store)
    fusion_svc = FusionService(settings=settings, asset_store=store, change_service=change_svc)
    return fusion_svc, store, change_svc


def test_capabilities_returns_supported_rules(
    fusion_setup: tuple[FusionService, AssetStore, ChangeService],
) -> None:
    fusion_svc, _, _ = fusion_setup
    caps = fusion_svc.get_capabilities()
    assert isinstance(caps, FusionCapabilitiesResponse)
    assert len(caps.rules) > 0
    assert caps.rules[0].rule_id == FusionRuleId.CO_OBSERVED_RESPONSE_CHANGE


def test_calculate_fusion_end_to_end(
    fusion_setup: tuple[FusionService, AssetStore, ChangeService],
) -> None:
    """Test full multimodal fusion combining an optical change result with a prepared SAR pair."""
    fusion_svc, store, change_svc = fusion_setup
    now = datetime.now(UTC)

    # 1. Create optical difference raster in asset store
    transform = [10.0, 0.0, 500000.0, 0.0, -10.0, 5200000.0]
    opt_diff_arr = np.array([[0.25, 0.05], [-0.30, 0.0]], dtype=np.float32)
    opt_diff_bytes = _create_sample_geotiff(opt_diff_arr, transform)
    opt_diff_asset_id = "opt-diff-123"
    store.save_asset(
        asset_id=opt_diff_asset_id,
        scene_id="S2-Diff",
        product_type=ImageryProductType.ANALYSIS_RASTER,
        format_type=ImageryFormat.GEOTIFF,
        content_type="image/tiff",
        width=2,
        height=2,
        resolution_meters=10.0,
        bbox=(500000.0, 5199980.0, 500020.0, 5200000.0),
        crs="EPSG:32631",
        data=opt_diff_bytes,
        provider_id="test_provider",
        data_origin=DataOrigin.MOCK,
    )

    # 2. Register mock optical change result
    opt_result_id = "change-res-123"
    opt_result = ChangeDetectionResult(
        result_id=opt_result_id,
        pair_id="pair-123",
        method=ChangeDetectionMethod.NDVI_DIFFERENCE,
        definition=ChangeDetectionDefinition(
            method=ChangeDetectionMethod.NDVI_DIFFERENCE,
            display_name="NDVI Difference",
            formula="NDVI_after - NDVI_before",
            input_type="spectral_index",
            directionality=ChangeDirectionality.BIDIRECTIONAL,
            expected_range=(-2.0, 2.0),
            default_threshold_config=ChangeThresholdConfig(
                positive_threshold=0.15, negative_threshold=-0.15
            ),
            description="Normalized Difference Vegetation Index differencing",
            limitations="Sensitive to atmospheric conditions",
        ),
        before_scene_id="S2-Before",
        after_scene_id="S2-After",
        before_asset_id="opt-b-1",
        after_asset_id="opt-a-1",
        difference_asset_id=opt_diff_asset_id,
        metrics=ChangeMetrics(
            gain_area_km2=0.0001,
            loss_area_km2=0.0001,
            stable_area_km2=0.0002,
            net_change_area_km2=0.0,
            shared_valid_area_km2=0.0004,
            pixel_counts=ChangePixelCounts(
                total_aoi_pixels=4,
                shared_valid_pixels=4,
                gain_pixels=1,
                loss_pixels=1,
                stable_pixels=2,
                uncertain_pixels=0,
                gain_percent=25.0,
                loss_percent=25.0,
                stable_percent=50.0,
                uncertain_percent=0.0,
            ),
            positive_threshold_applied=0.15,
            negative_threshold_applied=-0.15,
            threshold_strategy=ChangeThresholdConfig().strategy,
        ),
        confidence_breakdown=ConfidenceBreakdown(
            overall=0.9,
            data_quality=0.9,
            temporal_quality=0.9,
            spatial_quality=0.9,
            model_confidence=0.9,
            evidence_agreement=0.9,
            methodology="normalized_difference_differencing",
        ),
        confidence=0.9,
        provenance=RasterProvenance(
            source_asset_ids=["opt-b-1", "opt-a-1"],
            source_scene_ids=["S2-Before", "S2-After"],
            started_at=now,
            completed_at=now,
            duration_milliseconds=10.0,
            data_origin=DataOrigin.MOCK,
        ),
        data_origin=DataOrigin.MOCK,
        created_at=now,
    )
    change_svc._results_cache[opt_result_id] = opt_result

    # 3. Create SAR before and after rasters in dB
    sar_b_arr = np.array([[-12.0, -14.0], [-10.0, -15.0]], dtype=np.float32)
    sar_a_arr = np.array(
        [[-9.0, -13.5], [-14.5, -15.0]], dtype=np.float32
    )  # delta = [+3.0, +0.5], [-4.5, 0.0]
    sar_b_bytes = _create_sample_geotiff(sar_b_arr, transform)
    sar_a_bytes = _create_sample_geotiff(sar_a_arr, transform)

    sar_b_id = "sar-b-1"
    sar_a_id = "sar-a-1"
    store.save_asset(
        asset_id=sar_b_id,
        scene_id="S1-SAR-Before",
        product_type=ImageryProductType.ANALYSIS_RASTER,
        format_type=ImageryFormat.GEOTIFF,
        content_type="image/tiff",
        width=2,
        height=2,
        resolution_meters=10.0,
        bbox=(500000.0, 5199980.0, 500020.0, 5200000.0),
        crs="EPSG:32631",
        data=sar_b_bytes,
        provider_id="test_provider",
        data_origin=DataOrigin.MOCK,
        processing_metadata={"unit": "decibels", "polarization": "VV", "coefficient": "sigma0"},
    )
    store.save_asset(
        asset_id=sar_a_id,
        scene_id="S1-SAR-After",
        product_type=ImageryProductType.ANALYSIS_RASTER,
        format_type=ImageryFormat.GEOTIFF,
        content_type="image/tiff",
        width=2,
        height=2,
        resolution_meters=10.0,
        bbox=(500000.0, 5199980.0, 500020.0, 5200000.0),
        crs="EPSG:32631",
        data=sar_a_bytes,
        provider_id="test_provider",
        data_origin=DataOrigin.MOCK,
        processing_metadata={"unit": "decibels", "polarization": "VV", "coefficient": "sigma0"},
    )

    # 4. Execute fusion
    req = FusionRequest(
        optical_change_result_id=opt_result_id,
        sar_before_asset_id=sar_b_id,
        sar_after_asset_id=sar_a_id,
        aoi=AOIGeometry(
            type=GeometryType.POLYGON,
            coordinates=[[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
        ),
        rule_id=FusionRuleId.CO_OBSERVED_RESPONSE_CHANGE,
        sar_threshold_config=SARThresholdConfig(
            increase_threshold_db=2.0, decrease_threshold_db=-2.0
        ),
    )

    result = fusion_svc.calculate_fusion(req)
    assert isinstance(result, FusionResult)
    assert result.interpretation_readiness is True
    assert result.coverage.joint_percent_of_aoi == 100.0
    assert result.joint_metrics.joint_area_km2 > 0.0
    # (0,0): opt = +0.25 (gain), sar = +3.0 (increase) -> BOTH_DETECT_CHANGE
    # (1,0): opt = -0.30 (loss), sar = -4.5 (decrease) -> BOTH_DETECT_CHANGE
    # (0,1): opt = +0.05 (stable), sar = +0.5 (stable) -> NEITHER_ABOVE_THRESHOLD
    # (1,1): opt = 0.0 (stable), sar = 0.0 (stable) -> NEITHER_ABOVE_THRESHOLD
    assert result.joint_metrics.pixel_counts.both_detect_change_pixels == 2
    assert result.joint_metrics.pixel_counts.neither_above_threshold_pixels == 2
    assert result.joint_metrics.both_detect_change_percent == 50.0
    assert result.joint_metrics.neither_above_threshold_percent == 50.0
    assert len(result.observations) == 4
    assert result.sar_evidence is not None
