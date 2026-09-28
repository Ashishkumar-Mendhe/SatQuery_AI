"""Scientific calculation engine for SAR backscatter differencing and change evidence."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import Affine
from rio_tiler.utils import render

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    WarningSeverity,
)
from satquery.api.schemas.fusion import (
    SARBackscatterCoefficient,
    SARPolarization,
    SARPowerUnit,
    SARThresholdConfig,
)

logger = logging.getLogger(__name__)

SAR_DIFFERENCE_COLOR_RAMP: dict[int, tuple[int, int, int, int]] = {
    0: (0, 0, 0, 0),  # No data / invalid -> Transparent
    1: (215, 48, 39, 255),  # Significant Increase (dB >= +2.0) -> Crimson / Red
    2: (69, 117, 180, 255),  # Significant Decrease (dB <= -2.0) -> Cobalt / Blue
    3: (180, 180, 180, 180),  # Stable (-2.0 < dB < +2.0) -> Muted Grey
}


class SARCalculationError(RuntimeError):
    """Error raised when SAR evidence calculation fails due to unit or metadata mismatch."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class SAREngine:
    """Mathematical engine for SAR backscatter conversion, differencing, and statistics."""

    @staticmethod
    def validate_sar_metadata(
        before_polarization: SARPolarization | str,
        after_polarization: SARPolarization | str,
        before_unit: SARPowerUnit | str,
        after_unit: SARPowerUnit | str,
        before_coefficient: SARBackscatterCoefficient | str = SARBackscatterCoefficient.SIGMA0,
        after_coefficient: SARBackscatterCoefficient | str = SARBackscatterCoefficient.SIGMA0,
    ) -> list[AnalysisWarning]:
        """Validate radiometric comparability between before and after SAR acquisitions."""
        warnings: list[AnalysisWarning] = []

        b_unit = SARPowerUnit(before_unit) if isinstance(before_unit, str) else before_unit
        a_unit = SARPowerUnit(after_unit) if isinstance(after_unit, str) else after_unit

        if b_unit in {SARPowerUnit.RAW_DN, SARPowerUnit.UNKNOWN} or a_unit in {
            SARPowerUnit.RAW_DN,
            SARPowerUnit.UNKNOWN,
        }:
            raise SARCalculationError(
                "SAR_UNITS_UNKNOWN",
                "SAR backscatter units are unknown or raw digital numbers. Calibrated backscatter is required.",
                {"before_unit": str(b_unit), "after_unit": str(a_unit)},
            )

        if b_unit != a_unit:
            raise SARCalculationError(
                "SAR_UNIT_MISMATCH",
                f"Before unit ({b_unit}) does not match after unit ({a_unit}). Cannot silently mix linear and dB.",
                {"before_unit": str(b_unit), "after_unit": str(a_unit)},
            )

        b_pol = (
            SARPolarization(before_polarization)
            if isinstance(before_polarization, str)
            else before_polarization
        )
        a_pol = (
            SARPolarization(after_polarization)
            if isinstance(after_polarization, str)
            else after_polarization
        )
        if b_pol != a_pol:
            raise SARCalculationError(
                "SAR_POLARIZATION_MISMATCH",
                f"Before polarization ({b_pol}) does not match after polarization ({a_pol}).",
                {"before_polarization": str(b_pol), "after_polarization": str(a_pol)},
            )

        b_coeff = (
            SARBackscatterCoefficient(before_coefficient)
            if isinstance(before_coefficient, str)
            else before_coefficient
        )
        a_coeff = (
            SARBackscatterCoefficient(after_coefficient)
            if isinstance(after_coefficient, str)
            else after_coefficient
        )
        if b_coeff != a_coeff:
            warnings.append(
                AnalysisWarning(
                    code="SAR_COEFFICIENT_MISMATCH",
                    severity=WarningSeverity.MEDIUM,
                    title="SAR Coefficient Mismatch",
                    message=f"Differing backscatter coefficients: before is {b_coeff}, after is {a_coeff}.",
                )
            )

        return warnings

    @classmethod
    def compute_sar_difference(
        cls,
        before_arr: np.ndarray[Any, Any],
        after_arr: np.ndarray[Any, Any],
        unit: SARPowerUnit,
        before_mask: np.ndarray[Any, Any] | None = None,
        after_mask: np.ndarray[Any, Any] | None = None,
    ) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        """Compute signed backscatter difference in decibels (dB) with strict validity masking.

        Returns:
            (delta_db_array, valid_mask_array)
        """
        # Ensure 2D arrays (height, width)
        if before_arr.ndim == 3:
            b_data = before_arr[0].astype(np.float32)
        else:
            b_data = before_arr.astype(np.float32)

        if after_arr.ndim == 3:
            a_data = after_arr[0].astype(np.float32)
        else:
            a_data = after_arr.astype(np.float32)

        if b_data.shape != a_data.shape:
            raise SARCalculationError(
                "SHAPE_MISMATCH",
                f"SAR before shape {b_data.shape} does not match after shape {a_data.shape}.",
            )

        height, width = b_data.shape
        valid_mask = np.ones((height, width), dtype=bool)

        # Apply provided masks if present
        if before_mask is not None:
            valid_mask &= before_mask.astype(bool)
        if after_mask is not None:
            valid_mask &= after_mask.astype(bool)

        # Mask out NaNs and Infs
        valid_mask &= np.isfinite(b_data) & np.isfinite(a_data)

        delta_db = np.full((height, width), np.nan, dtype=np.float32)

        if unit == SARPowerUnit.LINEAR_POWER:
            # Mask out non-positive power values prior to logarithms (no epsilon injection)
            positive_mask = (b_data > 0.0) & (a_data > 0.0)
            valid_mask &= positive_mask

            valid_idx = np.where(valid_mask)
            if len(valid_idx[0]) > 0:
                b_db = 10.0 * np.log10(b_data[valid_idx])
                a_db = 10.0 * np.log10(a_data[valid_idx])
                delta_db[valid_idx] = a_db - b_db

        elif unit == SARPowerUnit.DECIBELS:
            valid_idx = np.where(valid_mask)
            if len(valid_idx[0]) > 0:
                delta_db[valid_idx] = a_data[valid_idx] - b_data[valid_idx]
        else:
            raise SARCalculationError(
                "SAR_UNITS_UNKNOWN",
                f"Unsupported SAR unit for quantitative differencing: {unit}",
            )

        return delta_db, valid_mask

    @classmethod
    def compute_sar_statistics(
        cls,
        delta_db: np.ndarray[Any, Any],
        valid_mask: np.ndarray[Any, Any],
        pixel_size_x: float,
        pixel_size_y: float,
    ) -> dict[str, float]:
        """Compute statistical properties of the valid backscatter difference array."""
        valid_vals = delta_db[valid_mask]
        valid_count = len(valid_vals)
        pixel_area_m2 = abs(pixel_size_x * pixel_size_y)
        valid_area_km2 = (valid_count * pixel_area_m2) / 1_000_000.0

        if valid_count == 0:
            return {
                "mean_delta_db": 0.0,
                "min_delta_db": 0.0,
                "max_delta_db": 0.0,
                "std_delta_db": 0.0,
                "valid_area_km2": 0.0,
                "valid_pixels": 0.0,
            }

        return {
            "mean_delta_db": float(np.mean(valid_vals)),
            "min_delta_db": float(np.min(valid_vals)),
            "max_delta_db": float(np.max(valid_vals)),
            "std_delta_db": float(np.std(valid_vals)),
            "valid_area_km2": round(valid_area_km2, 6),
            "valid_pixels": float(valid_count),
        }

    @classmethod
    def render_sar_difference_geotiff(
        cls,
        delta_db: np.ndarray[Any, Any],
        transform: list[float] | Affine,
        crs: str,
        nodata: float = -9999.0,
    ) -> bytes:
        """Serialize SAR delta dB array to an in-memory 1-band GeoTIFF."""
        height, width = delta_db.shape
        data_to_write = np.where(np.isnan(delta_db), nodata, delta_db).astype(np.float32)

        if isinstance(transform, list | tuple):
            aff = Affine(*transform[:6])
        else:
            aff = transform

        with MemoryFile() as memfile:
            with memfile.open(
                driver="GTiff",
                height=height,
                width=width,
                count=1,
                dtype="float32",
                crs=crs,
                transform=aff,
                nodata=nodata,
            ) as dst:
                dst.write(data_to_write, 1)
                dst.set_band_description(1, "SAR Backscatter Delta (dB)")
            return bytes(memfile.getbuffer())

    @classmethod
    def render_sar_difference_png(
        cls,
        delta_db: np.ndarray[Any, Any],
        valid_mask: np.ndarray[Any, Any],
        threshold_config: SARThresholdConfig,
    ) -> bytes:
        """Render a color-classified 4-channel RGBA preview PNG."""
        height, width = delta_db.shape
        rgba = np.zeros((4, height, width), dtype=np.uint8)

        inc_th = threshold_config.increase_threshold_db
        dec_th = threshold_config.decrease_threshold_db

        inc_mask = valid_mask & (delta_db >= inc_th)
        dec_mask = valid_mask & (delta_db <= dec_th)
        stable_mask = valid_mask & (delta_db > dec_th) & (delta_db < inc_th)

        # Increase -> Red (215, 48, 39, 255)
        rgba[0, inc_mask] = 215
        rgba[1, inc_mask] = 48
        rgba[2, inc_mask] = 39
        rgba[3, inc_mask] = 255

        # Decrease -> Blue (69, 117, 180, 255)
        rgba[0, dec_mask] = 69
        rgba[1, dec_mask] = 117
        rgba[2, dec_mask] = 180
        rgba[3, dec_mask] = 255

        # Stable -> Muted Grey (180, 180, 180, 180)
        rgba[0, stable_mask] = 180
        rgba[1, stable_mask] = 180
        rgba[2, stable_mask] = 180
        rgba[3, stable_mask] = 180

        return render(rgba, img_format="PNG")
