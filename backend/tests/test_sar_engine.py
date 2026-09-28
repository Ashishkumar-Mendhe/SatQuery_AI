"""Tests for SAR backscatter differencing, unit verification, and statistics engine."""

from __future__ import annotations

import math

import numpy as np
import pytest

from satquery.api.schemas.fusion import (
    SARPolarization,
    SARPowerUnit,
    SARThresholdConfig,
)
from satquery.services.sar_engine import (
    SARCalculationError,
    SAREngine,
)


def test_linear_power_known_ratio_produces_expected_db() -> None:
    """Validate that linear power values produce exact mathematical dB differences."""
    # Case 1: 2x power gain -> +3.0103 dB
    before = np.array([[1.0, 10.0]], dtype=np.float32)
    after = np.array([[2.0, 1.0]], dtype=np.float32)

    delta_db, mask = SAREngine.compute_sar_difference(
        before_arr=before,
        after_arr=after,
        unit=SARPowerUnit.LINEAR_POWER,
    )

    assert mask.all()
    assert math.isclose(delta_db[0, 0], 10.0 * math.log10(2.0), rel_tol=1e-4)
    # Case 2: 10x power loss -> -10.0 dB
    assert math.isclose(delta_db[0, 1], -10.0, rel_tol=1e-4)


def test_decibel_inputs_subtracted_directly_without_double_conversion() -> None:
    """Validate that already-dB inputs are subtracted directly."""
    before_db = np.array([[-12.0, -18.5]], dtype=np.float32)
    after_db = np.array([[-8.0, -22.5]], dtype=np.float32)

    delta_db, mask = SAREngine.compute_sar_difference(
        before_arr=before_db,
        after_arr=after_db,
        unit=SARPowerUnit.DECIBELS,
    )

    assert mask.all()
    assert math.isclose(delta_db[0, 0], 4.0, rel_tol=1e-4)
    assert math.isclose(delta_db[0, 1], -4.0, rel_tol=1e-4)


def test_non_positive_power_masked_without_extreme_epsilons() -> None:
    """Non-positive power values (<= 0, NaN) must be masked prior to logarithms."""
    before = np.array([[1.0, 0.0, -5.0, np.nan]], dtype=np.float32)
    after = np.array([[2.0, 2.0, 2.0, 2.0]], dtype=np.float32)

    delta_db, mask = SAREngine.compute_sar_difference(
        before_arr=before,
        after_arr=after,
        unit=SARPowerUnit.LINEAR_POWER,
    )

    assert mask[0, 0] is np.True_
    assert mask[0, 1] is np.False_
    assert mask[0, 2] is np.False_
    assert mask[0, 3] is np.False_
    assert np.isnan(delta_db[0, 1])
    assert np.isnan(delta_db[0, 2])
    assert np.isnan(delta_db[0, 3])


def test_unknown_or_raw_dn_units_rejected() -> None:
    """Unknown units or raw DN must block quantitative SAR evidence."""
    with pytest.raises(SARCalculationError) as exc_info:
        SAREngine.validate_sar_metadata(
            before_polarization=SARPolarization.VV,
            after_polarization=SARPolarization.VV,
            before_unit=SARPowerUnit.RAW_DN,
            after_unit=SARPowerUnit.RAW_DN,
        )
    assert exc_info.value.code == "SAR_UNITS_UNKNOWN"


def test_polarization_mismatch_rejected() -> None:
    """Mismatched polarizations must not be silently compared."""
    with pytest.raises(SARCalculationError) as exc_info:
        SAREngine.validate_sar_metadata(
            before_polarization=SARPolarization.VV,
            after_polarization=SARPolarization.VH,
            before_unit=SARPowerUnit.DECIBELS,
            after_unit=SARPowerUnit.DECIBELS,
        )
    assert exc_info.value.code == "SAR_POLARIZATION_MISMATCH"


def test_sar_statistics_calculation() -> None:
    """Validate statistics computation over valid SAR delta pixels."""
    delta_db = np.array([[2.0, -4.0], [np.nan, 0.0]], dtype=np.float32)
    mask = np.array([[True, True], [False, True]], dtype=bool)

    stats = SAREngine.compute_sar_statistics(
        delta_db=delta_db,
        valid_mask=mask,
        pixel_size_x=10.0,
        pixel_size_y=10.0,
    )

    # 3 valid pixels of 100 m2 = 300 m2 = 0.0003 km2
    assert stats["valid_pixels"] == 3
    assert math.isclose(stats["valid_area_km2"], 0.0003, rel_tol=1e-4)
    assert math.isclose(stats["mean_delta_db"], (2.0 - 4.0 + 0.0) / 3.0, rel_tol=1e-4)
    assert stats["min_delta_db"] == -4.0
    assert stats["max_delta_db"] == 2.0


def test_sar_geotiff_and_png_rendering() -> None:
    """Validate serialized GeoTIFF and preview PNG generation."""
    delta_db = np.array([[3.0, -3.0], [0.0, np.nan]], dtype=np.float32)
    mask = np.array([[True, True], [True, False]], dtype=bool)
    th_config = SARThresholdConfig(increase_threshold_db=2.0, decrease_threshold_db=-2.0)

    geotiff_bytes = SAREngine.render_sar_difference_geotiff(
        delta_db=delta_db,
        transform=[10.0, 0.0, 100.0, 0.0, -10.0, 200.0],
        crs="EPSG:32631",
    )
    assert len(geotiff_bytes) > 0
    assert geotiff_bytes[:2] == b"II" or geotiff_bytes[:2] == b"MM"

    png_bytes = SAREngine.render_sar_difference_png(
        delta_db=delta_db,
        valid_mask=mask,
        threshold_config=th_config,
    )
    assert len(png_bytes) > 0
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
