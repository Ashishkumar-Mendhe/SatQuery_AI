"""Unit tests for ChangeEngine mathematical, thresholding, and vectorization logic."""

import numpy as np
import pytest

from satquery.api.schemas.change import (
    ChangeDetectionMethod,
    ChangeDirectionality,
    ChangeThresholdConfig,
    ThresholdStrategy,
)
from satquery.services.change_engine import (
    ChangeCalculationError,
    ChangeEngine,
)
from satquery.services.change_registry import ChangeRegistry


def test_grid_alignment_validation_pass() -> None:
    """Verify identical grid geometry passes validation."""
    shape = (64, 64)
    transform = [10.0, 0.0, 77.5, 0.0, -10.0, 13.0]
    crs = "EPSG:32643"

    ChangeEngine.validate_grid_alignment(
        before_shape=shape,
        after_shape=shape,
        before_transform=transform,
        after_transform=transform,
        before_crs=crs,
        after_crs=crs,
    )


def test_grid_alignment_validation_fails_on_mismatch() -> None:
    """Verify mismatched CRS, dimension, or transform raises ChangeCalculationError."""
    # 1. CRS mismatch
    with pytest.raises(ChangeCalculationError) as exc_crs:
        ChangeEngine.validate_grid_alignment(
            before_shape=(32, 32),
            after_shape=(32, 32),
            before_transform=[10.0, 0.0, 0.0, 0.0, -10.0, 0.0],
            after_transform=[10.0, 0.0, 0.0, 0.0, -10.0, 0.0],
            before_crs="EPSG:4326",
            after_crs="EPSG:32643",
        )
    assert exc_crs.value.code == "CRS_MISMATCH"

    # 2. Shape mismatch
    with pytest.raises(ChangeCalculationError) as exc_shape:
        ChangeEngine.validate_grid_alignment(
            before_shape=(32, 32),
            after_shape=(32, 64),
            before_transform=[10.0, 0.0, 0.0, 0.0, -10.0, 0.0],
            after_transform=[10.0, 0.0, 0.0, 0.0, -10.0, 0.0],
            before_crs="EPSG:32643",
            after_crs="EPSG:32643",
        )
    assert exc_shape.value.code == "DIMENSION_MISMATCH"

    # 3. Transform mismatch
    with pytest.raises(ChangeCalculationError) as exc_tf:
        ChangeEngine.validate_grid_alignment(
            before_shape=(32, 32),
            after_shape=(32, 32),
            before_transform=[10.0, 0.0, 0.0, 0.0, -10.0, 0.0],
            after_transform=[20.0, 0.0, 0.0, 0.0, -20.0, 0.0],
            before_crs="EPSG:32643",
            after_crs="EPSG:32643",
        )
    assert exc_tf.value.code == "TRANSFORM_MISMATCH"


def test_ndvi_difference_calculation() -> None:
    """Verify before and after NDVI subtraction produces exact delta array."""
    # Before: Red=0.2, NIR=0.6 -> NDVI = (0.6 - 0.2) / 0.8 = 0.50
    # After:  Red=0.4, NIR=0.4 -> NDVI = (0.4 - 0.4) / 0.8 = 0.00
    # Difference (after - before) = 0.00 - 0.50 = -0.50 (Vegetation decrease)
    b_data = np.zeros((4, 2, 2), dtype=np.float32)
    b_data[0] = 0.2  # red
    b_data[1] = 0.6  # nir

    a_data = np.zeros((4, 2, 2), dtype=np.float32)
    a_data[0] = 0.4  # red
    a_data[1] = 0.4  # nir

    band_map = {"red": 0, "nir": 1}

    diff_arr, _ = ChangeEngine.compute_difference_array(
        before_data=b_data,
        after_data=a_data,
        before_band_map=band_map,
        after_band_map=band_map,
        method=ChangeDetectionMethod.NDVI_DIFFERENCE,
    )

    assert np.allclose(diff_arr, -0.50, atol=1e-4)


def test_apply_thresholds_and_classify_fixed() -> None:
    """Verify fixed threshold segmentation into Gain (+1), Loss (-1), Stable (0)."""
    # 4 pixels: Gain (+0.30), Loss (-0.25), Stable (+0.05), Invalid (-0.50 but masked out)
    diff_arr = np.array([[0.30, -0.25], [0.05, -0.50]], dtype=np.float32)
    valid_mask = np.array([[True, True], [True, False]], dtype=bool)

    cfg = ChangeThresholdConfig(
        strategy=ThresholdStrategy.FIXED,
        positive_threshold=0.15,
        negative_threshold=-0.15,
    )

    classified, pos_t, neg_t = ChangeEngine.apply_thresholds_and_classify(
        diff_arr=diff_arr,
        shared_valid_mask=valid_mask,
        config=cfg,
        directionality=ChangeDirectionality.BIDIRECTIONAL,
    )

    assert pos_t == 0.15
    assert neg_t == -0.15
    assert classified[0, 0] == 1  # Gain
    assert classified[0, 1] == -1  # Loss
    assert classified[1, 0] == 0  # Stable
    assert classified[1, 1] == 0  # Masked out remains 0 in classified array


def test_compute_change_metrics_strict_denominator() -> None:
    """Verify metrics use shared_valid_pixels strictly as the percentage denominator."""
    # 4 total AOI pixels: 1 gain (+1), 1 loss (-1), 1 stable (0), 1 invalid (masked out)
    classified = np.array([[1, -1], [0, 0]], dtype=np.int16)
    valid_mask = np.array([[True, True], [True, False]], dtype=bool)  # 3 valid pixels
    transform = [10.0, 0.0, 77.5, 0.0, -10.0, 13.0]  # 10m pixel size -> 100 m2 per pixel

    metrics = ChangeEngine.compute_change_metrics(
        classified_arr=classified,
        shared_valid_mask=valid_mask,
        total_aoi_pixels=4,
        transform=transform,
        crs="EPSG:32643",
        pos_thresh_applied=0.15,
        neg_thresh_applied=-0.15,
        strategy=ThresholdStrategy.FIXED,
    )

    assert metrics.pixel_counts.total_aoi_pixels == 4
    assert metrics.pixel_counts.shared_valid_pixels == 3
    assert metrics.pixel_counts.gain_pixels == 1
    assert metrics.pixel_counts.loss_pixels == 1
    assert metrics.pixel_counts.stable_pixels == 1
    assert metrics.pixel_counts.uncertain_pixels == 1

    # 1 / 3 = 33.33% (NOT 1 / 4 = 25%)
    assert np.isclose(metrics.pixel_counts.gain_percent, 33.33, atol=1e-2)
    assert np.isclose(metrics.pixel_counts.loss_percent, 33.33, atol=1e-2)
    assert np.isclose(metrics.pixel_counts.stable_percent, 33.33, atol=1e-2)


def test_vectorize_change_regions() -> None:
    """Verify region vectorization extracts candidate change polygons with bounding boxes."""
    classified = np.zeros((16, 16), dtype=np.int16)
    diff_arr = np.zeros((16, 16), dtype=np.float32)

    # 4x4 cluster of gain (+1) with mean diff +0.40
    classified[2:6, 2:6] = 1
    diff_arr[2:6, 2:6] = 0.40
    valid_mask = np.ones((16, 16), dtype=bool)
    transform = [10.0, 0.0, 77.5, 0.0, -10.0, 13.0]

    regions = ChangeEngine.vectorize_change_regions(
        classified_arr=classified,
        diff_arr=diff_arr,
        shared_valid_mask=valid_mask,
        transform=transform,
        crs="EPSG:32643",
        min_cluster_pixels=4,
        max_regions=10,
    )

    assert len(regions) == 1
    reg = regions[0]
    assert reg.category == "spectral_gain"
    assert reg.pixel_count == 16
    assert np.isclose(reg.mean_magnitude, 0.40, atol=1e-3)
    assert reg.geometry.type == "Polygon"


def test_preview_png_generation() -> None:
    """Verify continuous and discrete classified PNGs are valid RGBA image bytes."""
    diff_arr = np.linspace(-0.5, 0.5, 64).reshape((8, 8)).astype(np.float32)
    valid_mask = np.ones((8, 8), dtype=bool)
    classified = np.where(diff_arr > 0.15, 1, np.where(diff_arr < -0.15, -1, 0)).astype(np.int16)

    # Continuous PNG
    cont_png = ChangeEngine.generate_continuous_preview_png(
        diff_arr=diff_arr,
        shared_valid_mask=valid_mask,
        color_ramp="RdYlGn",
    )
    assert isinstance(cont_png, bytes)
    assert cont_png.startswith(b"\x89PNG\r\n\x1a\n")

    # Discrete Classified PNG
    class_png = ChangeEngine.generate_classified_preview_png(
        classified_arr=classified,
        shared_valid_mask=valid_mask,
    )
    assert isinstance(class_png, bytes)
    assert class_png.startswith(b"\x89PNG\r\n\x1a\n")


def test_confidence_calculation() -> None:
    """Verify multi-factor confidence calculation returns valid calibrated score."""
    defn = ChangeRegistry.get_method_definition(ChangeDetectionMethod.NDVI_DIFFERENCE)
    conf = ChangeEngine.calculate_confidence(
        shared_valid_percent=95.0,
        is_mock=False,
        definition=defn,
    )

    assert 0.85 <= conf.overall <= 1.0
    assert len(conf.factors) == 4
    assert len(conf.limitations) >= 1
