"""Unit tests for scientific raster harmonizer engine."""

from __future__ import annotations

import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds

from satquery.api.schemas.analysis import AOIGeometry
from satquery.api.schemas.imagery import AlignmentStatus
from satquery.api.schemas.preparation import (
    ResamplingMethod,
    TargetGridStrategy,
)
from satquery.api.schemas.providers import DataOrigin
from satquery.services.raster_harmonizer import (
    RasterHarmonizer,
)


def create_synthetic_geotiff(
    *,
    width: int = 100,
    height: int = 100,
    bands: int = 3,
    crs: str = "EPSG:4326",
    bounds: tuple[float, float, float, float] = (77.58, 12.96, 77.62, 13.00),
    nodata: float = -9999.0,
) -> bytes:
    """Create in-memory synthetic float32 GeoTIFF raster."""
    west, south, east, north = bounds
    transform = from_bounds(west, south, east, north, width, height)

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": bands,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
    }

    # Generate synthetic gradient reflectance [0.0 - 0.5]
    data = np.zeros((bands, height, width), dtype=np.float32)
    for b in range(bands):
        for r in range(height):
            for c in range(width):
                data[b, r, c] = float((r + c + (b * 10)) / (height + width + 50))

    memfile = MemoryFile()
    with memfile.open(**profile) as dst:
        dst.write(data)

    content = bytes(memfile.getbuffer())
    memfile.close()
    return content


def sample_aoi() -> AOIGeometry:
    return AOIGeometry(
        type="Polygon",
        coordinates=[
            [
                [77.585, 12.965],
                [77.615, 12.965],
                [77.615, 12.995],
                [77.585, 12.995],
                [77.585, 12.965],
            ]
        ],
        bbox=(77.585, 12.965, 77.615, 12.995),
    )


def test_calculate_utm_epsg() -> None:
    # Bengaluru (approx 77.59 E, 12.97 N) -> UTM Zone 43N (EPSG:32643)
    assert RasterHarmonizer.calculate_utm_epsg(77.59, 12.97) == 32643

    # London (approx 0.12 W, 51.50 N) -> UTM Zone 30N (EPSG:32630)
    assert RasterHarmonizer.calculate_utm_epsg(-0.12, 51.50) == 32630

    # Sydney (approx 151.2 E, -33.86 S) -> UTM Zone 56S (EPSG:32756)
    assert RasterHarmonizer.calculate_utm_epsg(151.2, -33.86) == 32756


def test_determine_target_crs_auto() -> None:
    aoi = sample_aoi()
    target_crs, warnings = RasterHarmonizer.determine_target_crs(aoi)
    assert target_crs == "EPSG:32643"
    assert any(w.code == "TARGET_CRS_SELECTED_AUTOMATICALLY" for w in warnings)


def test_reproject_and_harmonize_single() -> None:
    source_bytes = create_synthetic_geotiff()
    aoi = sample_aoi()

    result = RasterHarmonizer.reproject_and_harmonize_single(
        source_bytes=source_bytes,
        source_asset_id="ast-src-1",
        scene_id="S2A_20250101",
        aoi=aoi,
        target_crs="EPSG:32643",
        target_resolution_meters=10.0,
        resampling_method=ResamplingMethod.BILINEAR,
        clip_to_aoi=True,
    )

    assert result.crs == "EPSG:32643"
    assert result.width > 0
    assert result.height > 0
    assert result.resolution_meters == 10.0
    assert result.valid_data_percent > 0.0
    assert len(result.geotiff_bytes) > 0
    assert len(result.preview_png_bytes) > 0
    assert result.provenance.pipeline_version == "1.0"


def test_harmonize_and_align_temporal_pair() -> None:
    before_bytes = create_synthetic_geotiff(
        bounds=(77.58, 12.96, 77.62, 13.00), width=100, height=100
    )
    after_bytes = create_synthetic_geotiff(
        bounds=(77.58, 12.96, 77.62, 13.00), width=100, height=100
    )
    aoi = sample_aoi()

    pair_result = RasterHarmonizer.harmonize_and_align_temporal_pair(
        before_bytes=before_bytes,
        after_bytes=after_bytes,
        before_asset_id="ast-before",
        after_asset_id="ast-after",
        before_scene_id="S2A_20250101",
        after_scene_id="S2B_20250120",
        aoi=aoi,
        strategy=TargetGridStrategy.COMMON_INTERSECTION,
        target_crs="EPSG:32643",
        target_resolution_meters=10.0,
    )

    assert pair_result.common_crs == "EPSG:32643"
    assert (
        pair_result.common_width
        == pair_result.before_result.width
        == pair_result.after_result.width
    )
    assert (
        pair_result.common_height
        == pair_result.before_result.height
        == pair_result.after_result.height
    )
    assert (
        pair_result.common_transform
        == pair_result.before_result.transform
        == pair_result.after_result.transform
    )
    assert pair_result.alignment_status == AlignmentStatus.ALIGNED
    assert pair_result.shared_valid_percent > 50.0
    assert pair_result.ready_for_analysis is True
    assert len(pair_result.blocking_issues) == 0


def test_harmonize_temporal_pair_rejects_mixed_data_origin() -> None:
    before_bytes = create_synthetic_geotiff()
    after_bytes = create_synthetic_geotiff()
    aoi = sample_aoi()

    pair_result = RasterHarmonizer.harmonize_and_align_temporal_pair(
        before_bytes=before_bytes,
        after_bytes=after_bytes,
        before_asset_id="ast-before",
        after_asset_id="ast-after",
        before_scene_id="S2A_20250101",
        after_scene_id="mock-scene-after",
        aoi=aoi,
        before_origin=DataOrigin.REAL,
        after_origin=DataOrigin.MOCK,
    )

    assert "MIXED_DATA_ORIGIN" in pair_result.blocking_issues
    assert pair_result.ready_for_analysis is False
