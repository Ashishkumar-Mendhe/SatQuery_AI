"""Unit tests for Phase 3B raster preparation and harmonization schemas."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from satquery.api.schemas.analysis import AOIGeometry
from satquery.api.schemas.imagery import ImageryFormat
from satquery.api.schemas.preparation import (
    PreparedRasterAsset,
    RasterPreparationRequest,
    RasterProvenance,
    ResamplingMethod,
    TargetGridStrategy,
    TemporalRasterPreparationRequest,
)
from satquery.api.schemas.providers import DataOrigin


def sample_aoi() -> AOIGeometry:
    return AOIGeometry(
        type="Polygon",
        coordinates=[
            [
                [77.58, 12.96],
                [77.62, 12.96],
                [77.62, 13.00],
                [77.58, 13.00],
                [77.58, 12.96],
            ]
        ],
        bbox=(77.58, 12.96, 77.62, 13.00),
    )


def test_raster_preparation_request_validation() -> None:
    req = RasterPreparationRequest(
        source_asset_id="ast-12345",
        scene_id="S2A_20250101",
        aoi=sample_aoi(),
        target_crs="EPSG:32643",
        target_resolution_meters=10.0,
        resampling_method=ResamplingMethod.BILINEAR,
        clip_to_aoi=True,
        output_format=ImageryFormat.GEOTIFF,
    )
    assert req.source_asset_id == "ast-12345"
    assert req.target_crs == "EPSG:32643"
    assert req.output_format == ImageryFormat.GEOTIFF


def test_raster_preparation_request_rejects_png_format() -> None:
    with pytest.raises(ValidationError, match="geotiff or cog"):
        RasterPreparationRequest(
            source_asset_id="ast-12345",
            scene_id="S2A_20250101",
            aoi=sample_aoi(),
            output_format=ImageryFormat.PNG,
        )


def test_temporal_raster_preparation_request_validation() -> None:
    req = TemporalRasterPreparationRequest(
        pair_id="pair-123",
        before_asset_id="ast-before-1",
        after_asset_id="ast-after-2",
        aoi=sample_aoi(),
        strategy=TargetGridStrategy.COMMON_INTERSECTION,
        target_crs="EPSG:32643",
    )
    assert req.pair_id == "pair-123"
    assert req.strategy == TargetGridStrategy.COMMON_INTERSECTION


def test_temporal_raster_preparation_request_rejects_same_asset() -> None:
    with pytest.raises(ValidationError, match="distinct"):
        TemporalRasterPreparationRequest(
            pair_id="pair-123",
            before_asset_id="ast-same",
            after_asset_id="ast-same",
            aoi=sample_aoi(),
        )


def test_prepared_raster_asset_model() -> None:
    now = datetime.now(UTC)
    prov = RasterProvenance(
        source_asset_ids=["ast-src"],
        source_scene_ids=["S2A_20250101"],
        operations=["reproject", "clip"],
        parameters={"target_crs": "EPSG:32643"},
        started_at=now,
        completed_at=now,
        duration_milliseconds=120.5,
        data_origin=DataOrigin.REAL,
    )

    asset = PreparedRasterAsset(
        asset_id="ast-prep-123",
        source_asset_ids=["ast-src"],
        scene_ids=["S2A_20250101"],
        role="single",
        format=ImageryFormat.GEOTIFF,
        crs="EPSG:32643",
        bbox=(77.58, 12.96, 77.62, 13.00),
        width=512,
        height=512,
        pixel_size_x=10.0,
        pixel_size_y=10.0,
        transform=[10.0, 0.0, 500000.0, 0.0, -10.0, 1400000.0],
        band_count=3,
        band_names=["B04", "B03", "B02"],
        data_type="float32",
        no_data_values=[-9999.0, -9999.0, -9999.0],
        valid_pixel_count=200000,
        invalid_pixel_count=62144,
        valid_data_percent=76.29,
        resolution_meters=10.0,
        resampling_method=ResamplingMethod.BILINEAR,
        clip_applied=True,
        mask_applied=True,
        created_at=now,
        data_origin=DataOrigin.REAL,
        provenance=prov,
    )
    assert asset.asset_id == "ast-prep-123"
    assert asset.valid_data_percent == 76.29
    assert asset.provenance.duration_milliseconds == 120.5
