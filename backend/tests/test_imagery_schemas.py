"""Unit tests for Phase 3A imagery Pydantic v2 schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from satquery.api.schemas.analysis import AOIGeometry, GeometryType
from satquery.api.schemas.imagery import (
    ImageryFormat,
    ImageryProductType,
    ImageryRequest,
    RasterMetadata,
    TemporalImageryRequest,
    VisualizationPreset,
)

SAMPLE_AOI = AOIGeometry(
    type=GeometryType.POLYGON,
    coordinates=[
        [
            [77.45, 12.85],
            [77.75, 12.85],
            [77.75, 13.15],
            [77.45, 13.15],
            [77.45, 12.85],
        ]
    ],
    bbox=(77.45, 12.85, 77.75, 13.15),
)


def test_imagery_request_valid_preview() -> None:
    req = ImageryRequest(
        scene_id="S2A_20250101",
        aoi=SAMPLE_AOI,
        product_type=ImageryProductType.MAP_PREVIEW,
        visualization_preset=VisualizationPreset.TRUE_COLOR,
        output_format=ImageryFormat.PNG,
    )
    assert req.scene_id == "S2A_20250101"
    assert req.product_type == ImageryProductType.MAP_PREVIEW
    assert req.visualization_preset == VisualizationPreset.TRUE_COLOR
    assert req.output_format == ImageryFormat.PNG


def test_imagery_request_analysis_raster_requires_geotiff() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ImageryRequest(
            scene_id="S2A_20250101",
            aoi=SAMPLE_AOI,
            product_type=ImageryProductType.ANALYSIS_RASTER,
            output_format=ImageryFormat.PNG,  # Invalid: analysis raster cannot be PNG
        )
    assert "analysis_raster product type requires geotiff" in str(exc_info.value)


def test_temporal_imagery_request_distinct_scenes() -> None:
    req = TemporalImageryRequest(
        before_scene_id="S2A_20250101",
        after_scene_id="S2B_20250120",
        aoi=SAMPLE_AOI,
        before_preset=VisualizationPreset.TRUE_COLOR,
        after_preset=VisualizationPreset.VEGETATION,
    )
    assert req.before_scene_id == "S2A_20250101"
    assert req.after_scene_id == "S2B_20250120"
    assert req.before_preset == VisualizationPreset.TRUE_COLOR
    assert req.after_preset == VisualizationPreset.VEGETATION


def test_temporal_imagery_request_identical_scenes_fail() -> None:
    with pytest.raises(ValidationError) as exc_info:
        TemporalImageryRequest(
            before_scene_id="S2A_SAME",
            after_scene_id="S2A_SAME",
            aoi=SAMPLE_AOI,
        )
    assert "must be distinct" in str(exc_info.value)


def test_raster_metadata_validation() -> None:
    meta = RasterMetadata(
        crs="EPSG:4326",
        bbox=(77.45, 12.85, 77.75, 13.15),
        width=512,
        height=512,
        pixel_size_x=0.0005,
        pixel_size_y=0.0005,
        band_count=3,
        band_names=["B04", "B03", "B02"],
        data_type="uint8",
        scene_id="S2A_20250101",
        provider="earth-search",
        collection="sentinel-2-c1-l2a",
    )
    assert meta.crs == "EPSG:4326"
    assert meta.band_count == 3
    assert len(meta.band_names) == 3
