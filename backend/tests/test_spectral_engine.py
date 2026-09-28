"""Tests for pure geospatial and mathematical spectral calculation engine."""

import numpy as np
import rasterio

from satquery.api.schemas.spectral import (
    SpectralIndexName,
    StatisticsOptions,
)
from satquery.services.spectral_engine import (
    SpectralEngine,
)


def test_ndvi_calculation_accuracy() -> None:
    """Verify NDVI numerical precision on known values: (NIR - RED) / (NIR + RED)."""
    # 2 bands: Red (idx 0), NIR (idx 1)
    # Pixel (0, 0): NIR=0.8, RED=0.2 -> (0.8 - 0.2) / (0.8 + 0.2) = 0.60 / 1.0 = 0.60
    # Pixel (0, 1): NIR=0.1, RED=0.5 -> (0.1 - 0.5) / (0.1 + 0.5) = -0.40 / 0.6 = -0.6667
    data = np.array(
        [
            [[0.2, 0.5]],  # Red
            [[0.8, 0.1]],  # NIR
        ],
        dtype=np.float32,
    )

    band_map = {"red": 0, "nir": 1}
    index_arr, warnings = SpectralEngine.calculate_index_array(
        data=data,
        band_map=band_map,
        index_name=SpectralIndexName.NDVI,
    )

    assert index_arr.shape == (1, 2)
    assert np.isclose(index_arr[0, 0], 0.6, atol=1e-4)
    assert np.isclose(index_arr[0, 1], -0.4 / 0.6, atol=1e-4)
    assert len(warnings) == 0


def test_ndwi_calculation_accuracy() -> None:
    """Verify McFeeters NDWI: (GREEN - NIR) / (GREEN + NIR)."""
    data = np.array(
        [
            [[0.4, 0.1]],  # Green (idx 0)
            [[0.1, 0.5]],  # NIR (idx 1)
        ],
        dtype=np.float32,
    )

    band_map = {"green": 0, "nir": 1}
    index_arr, _warnings = SpectralEngine.calculate_index_array(
        data=data,
        band_map=band_map,
        index_name=SpectralIndexName.NDWI,
    )

    # Pixel (0, 0): (0.4 - 0.1) / (0.4 + 0.1) = 0.3 / 0.5 = 0.60 (Water response)
    # Pixel (0, 1): (0.1 - 0.5) / (0.1 + 0.5) = -0.4 / 0.6 = -0.6667 (Vegetation/land)
    assert np.isclose(index_arr[0, 0], 0.6, atol=1e-4)
    assert np.isclose(index_arr[0, 1], -0.6667, atol=1e-4)


def test_ndbi_calculation_accuracy() -> None:
    """Verify NDBI: (SWIR1 - NIR) / (SWIR1 + NIR)."""
    data = np.array(
        [
            [[0.5, 0.2]],  # SWIR1 (idx 0)
            [[0.3, 0.6]],  # NIR (idx 1)
        ],
        dtype=np.float32,
    )

    band_map = {"swir1": 0, "nir": 1}
    index_arr, _ = SpectralEngine.calculate_index_array(
        data=data,
        band_map=band_map,
        index_name=SpectralIndexName.NDBI,
    )

    # Pixel (0, 0): (0.5 - 0.3) / (0.5 + 0.3) = 0.2 / 0.8 = 0.25 (Built-up / dry soil)
    # Pixel (0, 1): (0.2 - 0.6) / (0.2 + 0.6) = -0.4 / 0.8 = -0.50 (Vegetation)
    assert np.isclose(index_arr[0, 0], 0.25, atol=1e-4)
    assert np.isclose(index_arr[0, 1], -0.50, atol=1e-4)


def test_division_by_zero_safety() -> None:
    """Verify zero denominator produces NaN without raising ZeroDivisionError."""
    data = np.array(
        [
            [[0.0, 0.0]],  # Red
            [[0.0, 0.5]],  # NIR
        ],
        dtype=np.float32,
    )

    band_map = {"red": 0, "nir": 1}
    index_arr, _ = SpectralEngine.calculate_index_array(
        data=data,
        band_map=band_map,
        index_name=SpectralIndexName.NDVI,
    )

    assert np.isnan(index_arr[0, 0])
    assert np.isclose(index_arr[0, 1], 1.0, atol=1e-4)


def test_statistics_computation() -> None:
    """Verify accurate extraction of summary statistics, percentiles, and histogram."""
    # Create 4x4 array with known values
    index_arr = np.array(
        [
            [0.1, 0.2, 0.3, 0.4],
            [0.5, 0.6, 0.7, 0.8],
            [np.nan, 0.2, 0.4, 0.6],
            [0.8, 0.0, -0.2, np.nan],
        ],
        dtype=np.float32,
    )

    valid_mask = np.ones((4, 4), dtype=bool)
    valid_mask[0, 0] = False  # Mask out (0, 0)

    options = StatisticsOptions(
        calculate_minimum=True,
        calculate_maximum=True,
        calculate_mean=True,
        calculate_median=True,
        calculate_standard_deviation=True,
        calculate_percentiles=True,
        percentiles=[50.0],
        calculate_histogram=True,
        histogram_bins=10,
    )

    stats = SpectralEngine.compute_statistics(
        index_arr=index_arr,
        valid_mask=valid_mask,
        options=options,
    )

    # Total valid: 16 - 1 (masked) - 2 (NaN) = 13 pixels
    assert stats.valid_pixel_count == 13
    assert stats.invalid_pixel_count == 3
    assert stats.masked_pixel_count == 1
    assert stats.minimum == -0.2
    assert stats.maximum == 0.8
    assert stats.histogram is not None
    assert len(stats.histogram.counts) == 10
    assert stats.histogram.total_samples == 13
    assert "p50" in stats.percentiles


def test_empty_valid_data_statistics() -> None:
    """Verify all-invalid array produces zero counts and None scalar statistics."""
    index_arr = np.full((5, 5), np.nan, dtype=np.float32)
    valid_mask = np.zeros((5, 5), dtype=bool)

    stats = SpectralEngine.compute_statistics(
        index_arr=index_arr,
        valid_mask=valid_mask,
    )

    assert stats.valid_pixel_count == 0
    assert stats.valid_data_percent == 0.0
    assert stats.minimum is None
    assert stats.maximum is None
    assert stats.mean is None
    assert stats.median is None


def test_generate_colormapped_png() -> None:
    """Verify RGBA PNG generation with transparent nodata."""
    index_arr = np.array(
        [
            [0.6, -0.4],
            [np.nan, 0.2],
        ],
        dtype=np.float32,
    )
    valid_mask = np.array(
        [
            [True, True],
            [False, True],
        ],
        dtype=bool,
    )

    png_bytes = SpectralEngine.generate_colormapped_png(
        index_arr=index_arr,
        valid_mask=valid_mask,
        color_ramp="RdYlGn",
    )

    assert isinstance(png_bytes, bytes)
    assert len(png_bytes) > 0
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_generate_scientific_geotiff() -> None:
    """Verify single-band Float32 GeoTIFF generation with valid metadata."""
    index_arr = np.array([[0.5, 0.7], [0.1, 0.3]], dtype=np.float32)
    valid_mask = np.ones((2, 2), dtype=bool)

    geotiff_bytes = SpectralEngine.generate_scientific_geotiff(
        index_arr=index_arr,
        valid_mask=valid_mask,
        crs="EPSG:32643",
        transform=[10.0, 0.0, 500000.0, 0.0, -10.0, 1400000.0],
        index_name="ndvi",
    )

    with rasterio.io.MemoryFile(geotiff_bytes) as memfile:
        with memfile.open() as src:
            assert src.count == 1
            assert src.dtypes[0] == "float32"
            assert src.crs.to_string() == "EPSG:32643"
            assert src.nodata == -9999.0
            assert "NDVI" in src.descriptions[0]


def test_calculate_confidence_breakdown() -> None:
    """Verify multi-factor confidence scoring is calibrated within [0.0, 1.0]."""
    conf = SpectralEngine.calculate_confidence(
        valid_data_percent=85.0,
        has_cloud_mask=True,
        required_bands_present=True,
        is_mock=False,
    )
    assert 0.0 <= conf.overall <= 1.0
    assert len(conf.factors) == 4
    total_weight = sum(f.weight for f in conf.factors)
    assert np.isclose(total_weight, 1.0)
