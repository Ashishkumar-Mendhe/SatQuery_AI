"""Pure geospatial and mathematical calculation engine for spectral indices."""

from __future__ import annotations

import logging
from typing import Any, cast

import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import Affine
from rio_tiler.utils import render

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    ConfidenceBreakdown,
    ConfidenceFactor,
    WarningSeverity,
)
from satquery.api.schemas.spectral import (
    SpectralHistogram,
    SpectralIndexName,
    SpectralIndexStatistics,
    StatisticsOptions,
)

logger = logging.getLogger(__name__)

NODATA_VALUE: float = -9999.0


class SpectralCalculationError(Exception):
    """Exception raised for mathematical or processing errors in spectral calculation."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


# ---------------------------------------------------------------------------
# Color Ramp Definitions
# ---------------------------------------------------------------------------

# Normalized gradient control points: (position 0.0..1.0, (R, G, B))
COLOR_RAMP_STOPS: dict[str, list[tuple[float, tuple[int, int, int]]]] = {
    "RdYlGn": [
        (0.0, (215, 48, 39)),  # Red
        (0.25, (252, 141, 89)),  # Orange
        (0.5, (254, 224, 139)),  # Yellow
        (0.75, (145, 207, 96)),  # Light Green
        (1.0, (26, 152, 80)),  # Deep Green
    ],
    "viridis": [
        (0.0, (68, 1, 84)),  # Purple
        (0.25, (59, 82, 139)),  # Blue
        (0.5, (33, 145, 140)),  # Teal
        (0.75, (94, 201, 98)),  # Light Green
        (1.0, (253, 231, 37)),  # Yellow
    ],
    "YlGnBu": [
        (0.0, (255, 255, 204)),  # Pale Yellow
        (0.25, (161, 218, 180)),  # Pale Green
        (0.5, (65, 182, 196)),  # Cyan
        (0.75, (44, 127, 184)),  # Blue
        (1.0, (37, 52, 148)),  # Deep Navy
    ],
    "YlOrRd": [
        (0.0, (255, 255, 178)),  # Light Yellow
        (0.25, (254, 204, 92)),  # Yellow-Orange
        (0.5, (253, 141, 60)),  # Orange
        (0.75, (240, 59, 32)),  # Bright Red
        (1.0, (189, 0, 38)),  # Dark Red
    ],
    "YlGn": [
        (0.0, (255, 255, 204)),  # Pale Yellow
        (0.33, (199, 233, 180)),  # Light Green
        (0.66, (127, 205, 187)),  # Green
        (1.0, (0, 104, 55)),  # Deep Forest Green
    ],
}


def _interpolate_color_ramp(ramp_name: str) -> np.ndarray:
    """Generate 256-entry RGB lookup table from gradient stops."""
    stops = COLOR_RAMP_STOPS.get(ramp_name, COLOR_RAMP_STOPS["RdYlGn"])
    lut = np.zeros((256, 3), dtype=np.uint8)

    for i in range(256):
        pos = i / 255.0
        # Find enclosing stops
        idx = 0
        while idx < len(stops) - 1 and stops[idx + 1][0] < pos:
            idx += 1
        if idx >= len(stops) - 1:
            lut[i] = stops[-1][1]
        else:
            p0, c0 = stops[idx]
            p1, c1 = stops[idx + 1]
            t = (pos - p0) / max(1e-6, (p1 - p0))
            r = int(c0[0] + t * (c1[0] - c0[0]))
            g = int(c0[1] + t * (c1[1] - c0[1]))
            b = int(c0[2] + t * (c1[2] - c0[2]))
            lut[i] = [np.clip(r, 0, 255), np.clip(g, 0, 255), np.clip(b, 0, 255)]

    return lut


# Precompute lookup tables
COLOR_LUTS: dict[str, np.ndarray] = {
    name: _interpolate_color_ramp(name) for name in COLOR_RAMP_STOPS
}


class SpectralEngine:
    """Scientific computation engine for remote-sensing spectral indices."""

    @classmethod
    def calculate_index_array(
        cls,
        data: np.ndarray,
        band_map: dict[str, int],
        index_name: SpectralIndexName,
        scale: float = 1.0,
        offset: float = 0.0,
    ) -> tuple[np.ndarray, list[AnalysisWarning]]:
        """Calculate floating-point spectral index array from multi-band raster data.

        Args:
            data: Shape (B, H, W) numpy float array of reflectance.
            band_map: Mapping from canonical band role to 0-indexed band slice.
            index_name: The spectral index to compute.
            scale: Multiplicative scale factor (applied if != 1.0).
            offset: Additive offset (applied if != 0.0).

        Returns:
            Tuple of (index_array_2d, warnings).
        """
        warnings: list[AnalysisWarning] = []

        def get_band(role: str) -> np.ndarray[Any, Any]:
            idx = band_map[role]
            band_data = data[idx].astype(np.float32)
            if scale != 1.0 or offset != 0.0:
                band_data = band_data * scale + offset
            return cast(np.ndarray[Any, Any], band_data)

        height, width = data.shape[1], data.shape[2]
        index_arr = np.full((height, width), np.nan, dtype=np.float32)

        if index_name == SpectralIndexName.NDVI:
            nir = get_band("nir")
            red = get_band("red")
            numer = nir - red
            denom = nir + red
            valid = (np.abs(denom) > 1e-6) & np.isfinite(nir) & np.isfinite(red)
            np.divide(numer, denom, out=index_arr, where=valid)

        elif index_name == SpectralIndexName.NDWI:
            green = get_band("green")
            nir = get_band("nir")
            numer = green - nir
            denom = green + nir
            valid = (np.abs(denom) > 1e-6) & np.isfinite(green) & np.isfinite(nir)
            np.divide(numer, denom, out=index_arr, where=valid)

        elif index_name == SpectralIndexName.NDBI:
            swir1 = get_band("swir1")
            nir = get_band("nir")
            numer = swir1 - nir
            denom = swir1 + nir
            valid = (np.abs(denom) > 1e-6) & np.isfinite(swir1) & np.isfinite(nir)
            np.divide(numer, denom, out=index_arr, where=valid)

        elif index_name == SpectralIndexName.EVI:
            nir = get_band("nir")
            red = get_band("red")
            blue = get_band("blue")
            numer = 2.5 * (nir - red)
            denom = nir + 6.0 * red - 7.5 * blue + 1.0
            valid = (np.abs(denom) > 1e-6) & np.isfinite(nir) & np.isfinite(red) & np.isfinite(blue)
            np.divide(numer, denom, out=index_arr, where=valid)

        elif index_name == SpectralIndexName.SAVI:
            nir = get_band("nir")
            red = get_band("red")
            numer = (nir - red) * 1.5
            denom = nir + red + 0.5
            valid = (np.abs(denom) > 1e-6) & np.isfinite(nir) & np.isfinite(red)
            np.divide(numer, denom, out=index_arr, where=valid)

        elif index_name == SpectralIndexName.MNDWI:
            green = get_band("green")
            swir1 = get_band("swir1")
            numer = green - swir1
            denom = green + swir1
            valid = (np.abs(denom) > 1e-6) & np.isfinite(green) & np.isfinite(swir1)
            np.divide(numer, denom, out=index_arr, where=valid)

        else:
            raise SpectralCalculationError(
                "UNSUPPORTED_INDEX",
                f"Formula for spectral index '{index_name}' is not implemented.",
            )

        # Validate theoretical bounds [-1.0, 1.0] with small epsilon for numerical drift
        finite_mask = np.isfinite(index_arr)
        if np.any(finite_mask):
            out_of_bounds = finite_mask & ((index_arr < -1.1) | (index_arr > 1.1))
            out_count = int(np.sum(out_of_bounds))
            total_finite = int(np.sum(finite_mask))
            if out_count > 0:
                pct = (out_count / total_finite) * 100.0
                if pct > 1.0:
                    warnings.append(
                        AnalysisWarning(
                            code="OUT_OF_BOUNDS_VALUES",
                            severity=WarningSeverity.LOW,
                            title="Out-of-Bounds Index Values",
                            message=(
                                f"{out_count} pixels ({pct:.1f}%) fell outside the expected "
                                "theoretical range [-1.0, 1.0] due to extreme reflectance "
                                "or atmospheric distortion."
                            ),
                        )
                    )

        return index_arr, warnings

    @classmethod
    def compute_statistics(
        cls,
        index_arr: np.ndarray,
        valid_mask: np.ndarray,
        options: StatisticsOptions | None = None,
    ) -> SpectralIndexStatistics:
        """Calculate summary statistics and histogram over valid AOI pixels."""
        opts = options or StatisticsOptions()
        total_pixels = int(index_arr.size)

        combined_valid = valid_mask & np.isfinite(index_arr)
        valid_values = index_arr[combined_valid]
        valid_count = int(valid_values.size)
        invalid_count = total_pixels - valid_count
        masked_count = int(np.sum(~valid_mask))
        valid_pct = (valid_count / total_pixels * 100.0) if total_pixels > 0 else 0.0

        if valid_count == 0:
            return SpectralIndexStatistics(
                minimum=None,
                maximum=None,
                mean=None,
                median=None,
                standard_deviation=None,
                percentiles={},
                histogram=None,
                valid_pixel_count=0,
                invalid_pixel_count=invalid_count,
                masked_pixel_count=masked_count,
                valid_data_percent=0.0,
                units="normalized_index",
                calculation_scope="exact_aoi_polygon",
            )

        # Basic scalar statistics
        minimum = float(np.min(valid_values)) if opts.calculate_minimum else None
        maximum = float(np.max(valid_values)) if opts.calculate_maximum else None
        mean = float(np.mean(valid_values)) if opts.calculate_mean else None
        median = float(np.median(valid_values)) if opts.calculate_median else None
        std_dev = float(np.std(valid_values)) if opts.calculate_standard_deviation else None

        # Percentiles
        percentile_dict: dict[str, float] = {}
        if opts.calculate_percentiles and opts.percentiles:
            for p in opts.percentiles:
                percentile_dict[f"p{int(p)}"] = round(float(np.percentile(valid_values, p)), 4)

        # Histogram
        histogram_obj: SpectralHistogram | None = None
        if opts.calculate_histogram:
            # Fixed theoretical range [-1.0, 1.0] for standard normalized difference indices
            counts, bin_edges = np.histogram(
                valid_values,
                bins=opts.histogram_bins,
                range=(-1.0, 1.0),
            )
            histogram_obj = SpectralHistogram(
                bin_edges=[round(float(e), 4) for e in bin_edges],
                counts=[int(c) for c in counts],
                total_samples=valid_count,
            )

        return SpectralIndexStatistics(
            minimum=round(minimum, 4) if minimum is not None else None,
            maximum=round(maximum, 4) if maximum is not None else None,
            mean=round(mean, 4) if mean is not None else None,
            median=round(median, 4) if median is not None else None,
            standard_deviation=round(std_dev, 4) if std_dev is not None else None,
            percentiles=percentile_dict,
            histogram=histogram_obj,
            valid_pixel_count=valid_count,
            invalid_pixel_count=invalid_count,
            masked_pixel_count=masked_count,
            valid_data_percent=round(valid_pct, 2),
            units="normalized_index",
            calculation_scope="exact_aoi_polygon",
        )

    @classmethod
    def generate_colormapped_png(
        cls,
        index_arr: np.ndarray,
        valid_mask: np.ndarray,
        color_ramp: str = "RdYlGn",
        vmin: float = -1.0,
        vmax: float = 1.0,
    ) -> bytes:
        """Render transparent 8-bit RGBA PNG overlay from spectral index array."""
        lut = COLOR_LUTS.get(color_ramp, COLOR_LUTS["RdYlGn"])

        # Normalize index values to 0..255 (NaNs become 0 and are masked out by alpha)
        norm = np.clip((index_arr - vmin) / max(1e-6, (vmax - vmin)), 0.0, 1.0)
        norm_sanitized = np.nan_to_num(norm, nan=0.0)
        norm_int = (norm_sanitized * 255.0).astype(np.uint8)

        # Apply LUT: (H, W) -> (H, W, 3) -> (3, H, W)
        rgb_data = lut[norm_int].transpose(2, 0, 1)

        # Build alpha transparency mask (255 for valid, 0 for invalid/nodata)
        alpha_mask = np.where(valid_mask & np.isfinite(index_arr), 255, 0).astype(np.uint8)

        png_bytes = render(rgb_data, mask=alpha_mask, img_format="PNG")
        return png_bytes

    @classmethod
    def generate_scientific_geotiff(
        cls,
        index_arr: np.ndarray,
        valid_mask: np.ndarray,
        crs: str,
        transform: list[float] | Affine,
        index_name: str,
        nodata_val: float = NODATA_VALUE,
    ) -> bytes:
        """Generate lossless single-band Float32 GeoTIFF scientific raster asset."""
        height, width = index_arr.shape
        out_data = np.where(valid_mask & np.isfinite(index_arr), index_arr, nodata_val).astype(
            np.float32
        )

        affine_transform = Affine(*transform[:6]) if isinstance(transform, list) else transform

        with MemoryFile() as memfile:
            with memfile.open(
                driver="GTiff",
                height=height,
                width=width,
                count=1,
                dtype="float32",
                crs=crs,
                transform=affine_transform,
                nodata=nodata_val,
                compress="deflate",
            ) as dst:
                dst.write(out_data, 1)
                dst.set_band_description(1, f"Spectral Index - {index_name.upper()}")
            return bytes(memfile.getbuffer())

    @classmethod
    def calculate_confidence(
        cls,
        valid_data_percent: float,
        has_cloud_mask: bool,
        required_bands_present: bool = True,
        is_mock: bool = False,
    ) -> ConfidenceBreakdown:
        """Compute transparent multi-factor evidence confidence score (0.0 - 1.0)."""
        factors: list[ConfidenceFactor] = []

        # Factor 1: Data Quality
        data_quality_score = 1.0 if not is_mock else 0.85
        factors.append(
            ConfidenceFactor(
                code="DATA_QUALITY",
                label="Sensor & Processing Level",
                score=data_quality_score,
                weight=0.30,
                explanation="Surface reflectance analysis raster with validated radiometric bands.",
            )
        )

        # Factor 2: Valid Coverage
        spatial_quality_score = min(1.0, max(0.0, valid_data_percent / 100.0))
        factors.append(
            ConfidenceFactor(
                code="SPATIAL_VALIDITY",
                label="AOI Valid Coverage",
                score=spatial_quality_score,
                weight=0.30,
                explanation=f"{valid_data_percent:.1f}% of pixels inside the AOI are valid.",
            )
        )

        # Factor 3: Cloud & Mask Integrity
        cloud_score = 0.95 if has_cloud_mask else 0.80
        factors.append(
            ConfidenceFactor(
                code="ATMOSPHERIC_QUALITY",
                label="Cloud & Quality Masking",
                score=cloud_score,
                weight=0.20,
                explanation=(
                    "Pixel-level quality mask applied."
                    if has_cloud_mask
                    else "Quality mask unavailable; standard no-data filtering applied."
                ),
            )
        )

        # Factor 4: Spectral Formula Clarity
        spectral_score = 0.95 if required_bands_present else 0.0
        factors.append(
            ConfidenceFactor(
                code="SPECTRAL_FORMULA",
                label="Index Formulation Consistency",
                score=spectral_score,
                weight=0.20,
                explanation="Exact canonical scientific formula computed in 32-bit floating point.",
            )
        )

        overall = sum(f.score * f.weight for f in factors)

        return ConfidenceBreakdown(
            overall=round(overall, 2),
            data_quality=data_quality_score,
            temporal_quality=1.0,
            spatial_quality=spatial_quality_score,
            model_confidence=spectral_score,
            evidence_agreement=0.90,
            factors=factors,
            methodology=(
                "Weighted combination of radiometric data quality, valid coverage, "
                "cloud masking, and formula fidelity."
            ),
            limitations=[
                "Spectral indices indicate relative spectral response, "
                "not definitive land-cover classification.",
                "Sub-pixel mixed materials and atmospheric aerosol variations "
                "can affect absolute values.",
            ],
        )
