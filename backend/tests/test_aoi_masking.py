"""Unit tests verifying strict AOI polygon masking and domain isolation."""

from __future__ import annotations

import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds

from satquery.api.schemas.analysis import AOIGeometry
from satquery.api.schemas.change import (
    ChangeDetectionMethod,
    ChangeDirectionality,
    ChangeThresholdConfig,
    ThresholdStrategy,
)
from satquery.api.schemas.preparation import (
    ResamplingMethod,
    TargetGridStrategy,
)
from satquery.services.change_engine import ChangeEngine
from satquery.services.raster_harmonizer import RasterHarmonizer


def create_synthetic_geotiff_with_hotspot(
    *,
    width: int = 100,
    height: int = 100,
    bounds: tuple[float, float, float, float] = (77.50, 12.90, 77.60, 13.00),
    inside_value: float = 0.20,
    outside_hotspot_value: float = 0.95,
) -> bytes:
    """Create a GeoTIFF where the top-right corner (outside the test triangle AOI) has a massive hotspot."""
    west, south, east, north = bounds
    transform = from_bounds(west, south, east, north, width, height)

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 4,  # b0=blue, b1=green, b2=red, b3=nir
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": transform,
        "nodata": -9999.0,
    }

    # Initialize with inside_value
    data = np.full((4, height, width), inside_value, dtype=np.float32)

    # Put a massive hotspot in the upper-right quadrant (rows 0..30, cols 70..100)
    data[:, 0:30, 70:100] = outside_hotspot_value

    memfile = MemoryFile()
    with memfile.open(**profile) as dst:
        dst.write(data)

    content = bytes(memfile.getbuffer())
    memfile.close()
    return content


def test_aoi_polygon_masking_excludes_outside_hotspot() -> None:
    """Verify that a triangle AOI in the lower-left completely masks out the upper-right hotspot."""
    # Triangular AOI covering lower-left corner: (77.51, 12.91) to (77.55, 12.91) to (77.51, 12.95)
    triangle_aoi = AOIGeometry(
        type="Polygon",
        coordinates=[
            [
                [77.51, 12.91],
                [77.55, 12.91],
                [77.51, 12.95],
                [77.51, 12.91],
            ]
        ],
        bbox=(77.51, 12.91, 77.55, 12.95),
    )

    source_bytes = create_synthetic_geotiff_with_hotspot(
        inside_value=0.20,
        outside_hotspot_value=0.95,
    )

    harmonized = RasterHarmonizer.reproject_and_harmonize_single(
        source_bytes=source_bytes,
        source_asset_id="ast-aoi-test",
        scene_id="S2A_AOI_TEST",
        aoi=triangle_aoi,
        target_crs="EPSG:32643",
        target_resolution_meters=10.0,
        resampling_method=ResamplingMethod.BILINEAR,
        clip_to_aoi=True,
    )

    # Read back harmonized raster
    with MemoryFile(harmonized.geotiff_bytes) as mem:
        with mem.open() as ds:
            data = ds.read()
            nodata = ds.nodata

    # Check that pixels outside the triangle are strictly masked to nodata
    # Inside pixels should have values near 0.20 and NONE near 0.95
    valid_pixels = data[0][data[0] != nodata]
    assert len(valid_pixels) > 0
    assert np.all(valid_pixels < 0.35), "Outside hotspot leaked into valid AOI pixels!"
    assert not np.any(np.isclose(valid_pixels, 0.95, atol=0.05)), (
        "Outside hotspot was included in valid AOI pixels!"
    )


def test_change_detection_outside_pixels_do_not_affect_metrics() -> None:
    """Verify that changes occurring strictly outside the AOI polygon do not alter AOI change statistics."""
    triangle_aoi = AOIGeometry(
        type="Polygon",
        coordinates=[
            [
                [77.51, 12.91],
                [77.55, 12.91],
                [77.51, 12.95],
                [77.51, 12.91],
            ]
        ],
        bbox=(77.51, 12.91, 77.55, 12.95),
    )

    # Before: Uniform 0.20 inside and outside
    before_bytes = create_synthetic_geotiff_with_hotspot(
        inside_value=0.20,
        outside_hotspot_value=0.20,
    )
    # After: Uniform 0.20 inside, but massive change (0.95) outside in top-right
    after_bytes = create_synthetic_geotiff_with_hotspot(
        inside_value=0.20,
        outside_hotspot_value=0.95,
    )

    pair_result = RasterHarmonizer.harmonize_and_align_temporal_pair(
        before_bytes=before_bytes,
        after_bytes=after_bytes,
        before_asset_id="ast-before",
        after_asset_id="ast-after",
        before_scene_id="S2A_1",
        after_scene_id="S2B_2",
        aoi=triangle_aoi,
        strategy=TargetGridStrategy.COMMON_INTERSECTION,
        target_crs="EPSG:32643",
        target_resolution_meters=10.0,
    )

    # Read raster data from geotiff bytes
    with MemoryFile(pair_result.before_result.geotiff_bytes) as mb:
        with mb.open() as dsb:
            b_data = dsb.read()
    with MemoryFile(pair_result.after_result.geotiff_bytes) as ma:
        with ma.open() as dsa:
            a_data = dsa.read()

    # Compute difference array
    band_map = {"blue": 0, "green": 1, "red": 2, "nir": 3}
    diff_arr, _ = ChangeEngine.compute_difference_array(
        before_data=b_data,
        after_data=a_data,
        before_band_map=band_map,
        after_band_map=band_map,
        method=ChangeDetectionMethod.NDVI_DIFFERENCE,
    )

    # Compute shared valid mask
    shared_valid_mask = (b_data[0] != -9999.0) & (a_data[0] != -9999.0)

    # Classify
    cfg = ChangeThresholdConfig(
        strategy=ThresholdStrategy.FIXED,
        positive_threshold=0.15,
        negative_threshold=-0.15,
    )
    classified, pos_t, neg_t = ChangeEngine.apply_thresholds_and_classify(
        diff_arr=diff_arr,
        shared_valid_mask=shared_valid_mask,
        config=cfg,
        directionality=ChangeDirectionality.BIDIRECTIONAL,
    )

    # Compute metrics
    metrics = ChangeEngine.compute_change_metrics(
        classified_arr=classified,
        shared_valid_mask=shared_valid_mask,
        total_aoi_pixels=int(shared_valid_mask.size),
        transform=pair_result.common_transform,
        crs=pair_result.common_crs,
        pos_thresh_applied=pos_t,
        neg_thresh_applied=neg_t,
        strategy=ThresholdStrategy.FIXED,
    )

    # Inside the AOI, both before and after had the same value (0.20), so NDVI change is 0.0 (stable)
    # Gain percent inside the AOI must be 0%, and loss percent must be 0%
    assert metrics.pixel_counts.gain_pixels == 0, (
        f"Expected 0 gain pixels inside AOI, got {metrics.pixel_counts.gain_pixels}"
    )
    assert metrics.pixel_counts.loss_pixels == 0, (
        f"Expected 0 loss pixels inside AOI, got {metrics.pixel_counts.loss_pixels}"
    )
    assert metrics.pixel_counts.stable_pixels == metrics.pixel_counts.shared_valid_pixels
    assert np.isclose(metrics.pixel_counts.stable_percent, 100.0, atol=0.1)
