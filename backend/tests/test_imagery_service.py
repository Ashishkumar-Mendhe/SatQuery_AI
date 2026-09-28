"""Unit tests for the ImageryService."""

from __future__ import annotations

import pytest
from conftest import make_settings

from satquery.api.schemas.analysis import AOIGeometry, GeometryType
from satquery.api.schemas.imagery import (
    AlignmentStatus,
    ImageryFormat,
    ImageryProductType,
    ImageryRequest,
    RasterMetadata,
    TemporalImageryRequest,
    VisualizationPreset,
)
from satquery.api.schemas.providers import DataOrigin
from satquery.services.imagery_service import ImageryProcessingError, ImageryService

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


@pytest.fixture
def imagery_service() -> ImageryService:
    settings = make_settings()
    return ImageryService(settings)


def test_request_map_preview_png(imagery_service: ImageryService) -> None:
    req = ImageryRequest(
        scene_id="mock-scene-optical-01",
        aoi=SAMPLE_AOI,
        product_type=ImageryProductType.MAP_PREVIEW,
        visualization_preset=VisualizationPreset.TRUE_COLOR,
        output_format=ImageryFormat.PNG,
        width=256,
        height=256,
    )
    asset = imagery_service.request_imagery(req, provider_mode="mock")
    assert asset.scene_id == "mock-scene-optical-01"
    assert asset.product_type == ImageryProductType.MAP_PREVIEW
    assert asset.format == ImageryFormat.PNG
    assert asset.content_type == "image/png"
    assert asset.width == 256
    assert asset.height == 256
    assert asset.display_url == f"/api/v1/imagery/assets/{asset.asset_id}"
    assert asset.data_origin == DataOrigin.MOCK


def test_request_analysis_raster_geotiff(imagery_service: ImageryService) -> None:
    req = ImageryRequest(
        scene_id="mock-scene-optical-01",
        aoi=SAMPLE_AOI,
        product_type=ImageryProductType.ANALYSIS_RASTER,
        visualization_preset=VisualizationPreset.VEGETATION,
        output_format=ImageryFormat.GEOTIFF,
        width=128,
        height=128,
    )
    asset = imagery_service.request_imagery(req, provider_mode="mock")
    assert asset.product_type == ImageryProductType.ANALYSIS_RASTER
    assert asset.format == ImageryFormat.GEOTIFF
    assert asset.content_type == "image/tiff"
    assert asset.width == 128
    assert asset.height == 128
    assert asset.download_url is not None


def test_request_imagery_pixel_limit_exceeded(imagery_service: ImageryService) -> None:
    req = ImageryRequest(
        scene_id="mock-scene-01",
        aoi=SAMPLE_AOI,
        product_type=ImageryProductType.MAP_PREVIEW,
        width=3000,
        height=3000,  # 9,000,000 px > 4,194,304 max_preview_pixels
    )
    with pytest.raises(ImageryProcessingError) as exc:
        imagery_service.request_imagery(req, provider_mode="mock")
    assert "exceed maximum allowed" in str(exc.value)


def test_request_temporal_imagery_pair(imagery_service: ImageryService) -> None:
    req = TemporalImageryRequest(
        before_scene_id="mock-scene-optical-02-before",
        after_scene_id="mock-scene-optical-03-after",
        aoi=SAMPLE_AOI,
        product_type=ImageryProductType.MAP_PREVIEW,
        before_preset=VisualizationPreset.TRUE_COLOR,
        after_preset=VisualizationPreset.FALSE_COLOR,
        width=256,
        height=256,
    )
    res = imagery_service.request_temporal_imagery(req, provider_mode="mock")
    assert res.before_asset.scene_id == "mock-scene-optical-02-before"
    assert res.after_asset.scene_id == "mock-scene-optical-03-after"
    assert res.before_asset.visualization_preset == VisualizationPreset.TRUE_COLOR
    assert res.after_asset.visualization_preset == VisualizationPreset.FALSE_COLOR
    assert res.alignment_status in {
        AlignmentStatus.ALIGNED,
        AlignmentStatus.APPROXIMATELY_ALIGNED,
    }


def test_temporal_alignment_evaluation_incompatible_crs(imagery_service: ImageryService) -> None:
    meta_a = RasterMetadata(
        crs="EPSG:4326",
        bbox=(77.45, 12.85, 77.75, 13.15),
        width=256,
        height=256,
        pixel_size_x=0.001,
        pixel_size_y=0.001,
        band_count=3,
        data_type="uint8",
        scene_id="A",
        provider="mock",
        collection="s2",
    )
    meta_b = RasterMetadata(
        crs="EPSG:32643",
        bbox=(77.45, 12.85, 77.75, 13.15),
        width=256,
        height=256,
        pixel_size_x=0.001,
        pixel_size_y=0.001,
        band_count=3,
        data_type="uint8",
        scene_id="B",
        provider="mock",
        collection="s2",
    )
    status = imagery_service.evaluate_temporal_alignment(meta_a, meta_b)
    assert status == AlignmentStatus.INCOMPATIBLE
