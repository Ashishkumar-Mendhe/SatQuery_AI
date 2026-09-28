"""Pure geospatial and mathematical calculation engine for pixel-level change detection."""

from __future__ import annotations

import logging
import math
from typing import Any
from uuid import uuid4

import numpy as np
from pyproj import Transformer
from rasterio.features import shapes
from rasterio.io import MemoryFile
from rasterio.transform import Affine
from rio_tiler.utils import render

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    AOIGeometry,
    ConfidenceBreakdown,
    ConfidenceFactor,
    GeometryType,
)
from satquery.api.schemas.change import (
    ChangeDetectionDefinition,
    ChangeDetectionMethod,
    ChangeDirectionality,
    ChangeMetrics,
    ChangePixelCounts,
    ChangeRegion,
    ChangeThresholdConfig,
    ThresholdStrategy,
)
from satquery.api.schemas.spectral import SpectralIndexName
from satquery.services.spectral_engine import COLOR_LUTS, SpectralEngine

logger = logging.getLogger(__name__)


class ChangeCalculationError(RuntimeError):
    """Error raised when pixel-level change detection calculation fails."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class ChangeEngine:
    """Mathematical engine for grid alignment, differencing, thresholding, and vectorization."""

    @staticmethod
    def validate_grid_alignment(
        before_shape: tuple[int, int],
        after_shape: tuple[int, int],
        before_transform: list[float] | tuple[float, ...],
        after_transform: list[float] | tuple[float, ...],
        before_crs: str,
        after_crs: str,
    ) -> None:
        """Enforce strict geometric co-registration between before and after rasters."""
        if before_crs != after_crs:
            raise ChangeCalculationError(
                "CRS_MISMATCH",
                f"Before CRS ({before_crs}) does not match After CRS ({after_crs}).",
                {"before_crs": before_crs, "after_crs": after_crs},
            )

        if before_shape != after_shape:
            raise ChangeCalculationError(
                "DIMENSION_MISMATCH",
                f"Before dimensions {before_shape} do not match After dimensions {after_shape}.",
                {"before_shape": list(before_shape), "after_shape": list(after_shape)},
            )

        # Check transform coefficients with 1e-5 tolerance
        for i, (b_val, a_val) in enumerate(zip(before_transform, after_transform, strict=False)):
            if abs(b_val - a_val) > 1e-5:
                raise ChangeCalculationError(
                    "TRANSFORM_MISMATCH",
                    f"Grid transform mismatch at index {i}: {b_val} != {a_val}.",
                    {
                        "before_transform": list(before_transform),
                        "after_transform": list(after_transform),
                    },
                )

    @classmethod
    def compute_difference_array(
        cls,
        before_data: np.ndarray[Any, Any],
        after_data: np.ndarray[Any, Any],
        before_band_map: dict[str, int],
        after_band_map: dict[str, int],
        method: ChangeDetectionMethod,
    ) -> tuple[np.ndarray[Any, Any], list[AnalysisWarning]]:
        """Compute pixel-by-pixel difference array according to the selected change method."""
        warnings: list[AnalysisWarning] = []
        height, width = before_data.shape[1], before_data.shape[2]
        diff_arr = np.full((height, width), np.nan, dtype=np.float32)

        if method == ChangeDetectionMethod.NDVI_DIFFERENCE:
            b_ndvi, _ = SpectralEngine.calculate_index_array(
                before_data, before_band_map, SpectralIndexName.NDVI
            )
            a_ndvi, _ = SpectralEngine.calculate_index_array(
                after_data, after_band_map, SpectralIndexName.NDVI
            )
            diff_arr = a_ndvi - b_ndvi

        elif method == ChangeDetectionMethod.NDWI_DIFFERENCE:
            b_ndwi, _ = SpectralEngine.calculate_index_array(
                before_data, before_band_map, SpectralIndexName.NDWI
            )
            a_ndwi, _ = SpectralEngine.calculate_index_array(
                after_data, after_band_map, SpectralIndexName.NDWI
            )
            diff_arr = a_ndwi - b_ndwi

        elif method == ChangeDetectionMethod.NDBI_DIFFERENCE:
            b_ndbi, _ = SpectralEngine.calculate_index_array(
                before_data, before_band_map, SpectralIndexName.NDBI
            )
            a_ndbi, _ = SpectralEngine.calculate_index_array(
                after_data, after_band_map, SpectralIndexName.NDBI
            )
            diff_arr = a_ndbi - b_ndbi

        elif method == ChangeDetectionMethod.ABSOLUTE_INDEX_DIFFERENCE:
            b_ndvi, _ = SpectralEngine.calculate_index_array(
                before_data, before_band_map, SpectralIndexName.NDVI
            )
            a_ndvi, _ = SpectralEngine.calculate_index_array(
                after_data, after_band_map, SpectralIndexName.NDVI
            )
            diff_arr = np.abs(a_ndvi - b_ndvi)

        elif method == ChangeDetectionMethod.MULTIBAND_CHANGE_MAGNITUDE:
            # Common optical bands: blue, green, red, nir
            common_roles = [
                r
                for r in ["blue", "green", "red", "nir"]
                if r in before_band_map and r in after_band_map
            ]
            if not common_roles:
                raise ChangeCalculationError(
                    "INSUFFICIENT_BANDS",
                    "Multiband change magnitude requires mutual optical bands.",
                    {
                        "before_bands": list(before_band_map.keys()),
                        "after_bands": list(after_band_map.keys()),
                    },
                )
            sq_sum = np.zeros((height, width), dtype=np.float32)
            for role in common_roles:
                b_band = before_data[before_band_map[role]].astype(np.float32)
                a_band = after_data[after_band_map[role]].astype(np.float32)
                sq_sum += (a_band - b_band) ** 2
            diff_arr = np.sqrt(sq_sum)

        else:
            raise ChangeCalculationError(
                "UNSUPPORTED_METHOD", f"Change method {method} not supported."
            )

        return diff_arr, warnings

    @classmethod
    def apply_thresholds_and_classify(
        cls,
        diff_arr: np.ndarray[Any, Any],
        shared_valid_mask: np.ndarray[Any, Any],
        config: ChangeThresholdConfig,
        directionality: ChangeDirectionality,
    ) -> tuple[np.ndarray[Any, Any], float, float]:
        """Classify difference array into Gain (+1), Loss (-1), Stable (0)."""
        valid_values = diff_arr[shared_valid_mask & np.isfinite(diff_arr)]
        height, width = diff_arr.shape
        classified_arr = np.full((height, width), 0, dtype=np.int16)

        if len(valid_values) == 0:
            return classified_arr, 0.0, 0.0

        pos_thresh = config.positive_threshold
        neg_thresh = config.negative_threshold

        if config.strategy == ThresholdStrategy.STANDARD_DEVIATION:
            mean_val = float(np.mean(valid_values))
            std_val = float(np.std(valid_values))
            k = config.std_multiplier
            pos_thresh = mean_val + (k * std_val)
            neg_thresh = mean_val - (k * std_val)

        elif config.strategy == ThresholdStrategy.PERCENTILE:
            upper_p = config.percentile_cutoff
            lower_p = 100.0 - upper_p
            pos_thresh = float(np.percentile(valid_values, upper_p))
            neg_thresh = float(np.percentile(valid_values, lower_p))

        elif config.strategy == ThresholdStrategy.OTSU:
            # Otsu adaptive threshold on magnitude
            abs_vals = np.abs(valid_values)
            hist, bin_edges = np.histogram(abs_vals, bins=50)
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
            weight1 = np.cumsum(hist) / float(len(abs_vals))
            weight2 = 1.0 - weight1
            weight2[weight2 <= 0.0] = 1e-6
            mean1 = np.cumsum(hist * bin_centers) / np.maximum(np.cumsum(hist), 1)
            total_mean = mean1[-1]
            mean2 = (total_mean - weight1 * mean1) / weight2
            variance = weight1 * weight2 * ((mean1 - mean2) ** 2)
            otsu_thresh = float(bin_centers[np.argmax(variance)])
            pos_thresh = otsu_thresh
            neg_thresh = -otsu_thresh

        # Apply classification mask
        if directionality == ChangeDirectionality.BIDIRECTIONAL:
            gain_mask = shared_valid_mask & (diff_arr >= pos_thresh)
            loss_mask = shared_valid_mask & (diff_arr <= neg_thresh)
            classified_arr[gain_mask] = 1
            classified_arr[loss_mask] = -1
        else:
            # Magnitude only: everything >= pos_thresh is classified as change (+1)
            mag_mask = shared_valid_mask & (diff_arr >= pos_thresh)
            classified_arr[mag_mask] = 1

        return classified_arr, round(pos_thresh, 4), round(neg_thresh, 4)

    @classmethod
    def compute_change_metrics(
        cls,
        classified_arr: np.ndarray[Any, Any],
        shared_valid_mask: np.ndarray[Any, Any],
        total_aoi_pixels: int,
        transform: list[float] | tuple[float, ...],
        crs: str,
        pos_thresh_applied: float,
        neg_thresh_applied: float,
        strategy: ThresholdStrategy,
    ) -> ChangeMetrics:
        """Compute pixel counts and true spatial area (km2) for detected change categories."""
        shared_valid_pixels = int(np.sum(shared_valid_mask))
        gain_pixels = int(np.sum(shared_valid_mask & (classified_arr == 1)))
        loss_pixels = int(np.sum(shared_valid_mask & (classified_arr == -1)))
        stable_pixels = int(np.sum(shared_valid_mask & (classified_arr == 0)))
        uncertain_pixels = total_aoi_pixels - shared_valid_pixels

        # Calculate percentages strictly over shared valid pixels
        if shared_valid_pixels > 0:
            gain_pct = round((gain_pixels / shared_valid_pixels) * 100.0, 2)
            loss_pct = round((loss_pixels / shared_valid_pixels) * 100.0, 2)
            stable_pct = round((stable_pixels / shared_valid_pixels) * 100.0, 2)
        else:
            gain_pct = loss_pct = stable_pct = 0.0

        uncertain_pct = round((uncertain_pixels / max(1, total_aoi_pixels)) * 100.0, 2)

        pixel_counts = ChangePixelCounts(
            total_aoi_pixels=total_aoi_pixels,
            shared_valid_pixels=shared_valid_pixels,
            gain_pixels=gain_pixels,
            loss_pixels=loss_pixels,
            stable_pixels=stable_pixels,
            uncertain_pixels=uncertain_pixels,
            gain_percent=gain_pct,
            loss_percent=loss_pct,
            stable_percent=stable_pct,
            uncertain_percent=uncertain_pct,
        )

        # Calculate pixel area in km2
        dx = abs(transform[0])
        dy = abs(transform[4])
        if "326" in crs or "327" in crs or "UTM" in crs.upper() or "3857" in crs:
            # Projected metric coordinates (dx, dy in meters)
            pixel_area_km2 = (dx * dy) / 1_000_000.0
        else:
            # Geographic EPSG:4326 approximate mid-latitude calculation
            center_lat = transform[3] - (dy * (classified_arr.shape[0] / 2.0))
            lat_rad = math.radians(center_lat)
            m_per_deg_lon = 111320.0 * math.cos(lat_rad)
            m_per_deg_lat = 110540.0
            pixel_area_km2 = (dx * m_per_deg_lon * dy * m_per_deg_lat) / 1_000_000.0

        gain_area = round(gain_pixels * pixel_area_km2, 4)
        loss_area = round(loss_pixels * pixel_area_km2, 4)
        stable_area = round(stable_pixels * pixel_area_km2, 4)
        net_change_area = round(gain_area - loss_area, 4)
        shared_valid_area = round(shared_valid_pixels * pixel_area_km2, 4)

        return ChangeMetrics(
            gain_area_km2=gain_area,
            loss_area_km2=loss_area,
            stable_area_km2=stable_area,
            net_change_area_km2=net_change_area,
            shared_valid_area_km2=shared_valid_area,
            pixel_counts=pixel_counts,
            positive_threshold_applied=pos_thresh_applied,
            negative_threshold_applied=neg_thresh_applied,
            threshold_strategy=strategy,
        )

    @classmethod
    def vectorize_change_regions(
        cls,
        classified_arr: np.ndarray[Any, Any],
        diff_arr: np.ndarray[Any, Any],
        shared_valid_mask: np.ndarray[Any, Any],
        transform: list[float] | tuple[float, ...],
        crs: str,
        min_cluster_pixels: int = 5,
        max_regions: int = 100,
    ) -> list[ChangeRegion]:
        """Extract bounded, vectorized polygon regions of candidate spectral change."""
        regions: list[ChangeRegion] = []
        affine_transform = Affine(*transform[:6])

        # Extract shapes for both gain (+1) and loss (-1)
        mask_int = np.where(shared_valid_mask, classified_arr, 0).astype(np.int16)

        # Precalculate pixel area in km2
        dx = abs(transform[0])
        dy = abs(transform[4])
        if "326" in crs or "327" in crs or "UTM" in crs.upper() or "3857" in crs:
            pixel_area_km2 = (dx * dy) / 1_000_000.0
        else:
            center_lat = transform[3] - (dy * (classified_arr.shape[0] / 2.0))
            lat_rad = math.radians(center_lat)
            pixel_area_km2 = (dx * 111320.0 * math.cos(lat_rad) * dy * 110540.0) / 1_000_000.0

        for geom_dict, val in shapes(mask_int, mask=(mask_int != 0), transform=affine_transform):
            val_int = int(val)
            if val_int == 0:
                continue

            coords = geom_dict["coordinates"]
            if not coords or len(coords[0]) < 4:
                continue

            category = "spectral_gain" if val_int == 1 else "spectral_loss"
            # Estimate pixel count from bounding box coordinates
            pts = coords[0]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)

            # Raster coordinate slice to calculate exact region magnitude
            col_min = max(0, int((min_x - transform[2]) / transform[0]))
            col_max = min(diff_arr.shape[1], int((max_x - transform[2]) / transform[0]) + 1)
            row_min = max(0, int((max_y - transform[5]) / transform[4]))
            row_max = min(diff_arr.shape[0], int((min_y - transform[5]) / transform[4]) + 1)

            sub_diff = diff_arr[row_min:row_max, col_min:col_max]
            sub_mask = mask_int[row_min:row_max, col_min:col_max] == val_int
            region_values = sub_diff[sub_mask & np.isfinite(sub_diff)]

            pixel_count = len(region_values)
            if pixel_count < min_cluster_pixels:
                continue

            area_km2 = round(pixel_count * pixel_area_km2, 4)
            mean_mag = round(float(np.mean(region_values)), 4) if pixel_count > 0 else 0.0
            min_mag = round(float(np.min(region_values)), 4) if pixel_count > 0 else 0.0
            max_mag = round(float(np.max(region_values)), 4) if pixel_count > 0 else 0.0

            region_id = f"reg-chg-{uuid4().hex[:8]}"

            wgs84_coords = coords
            wgs84_bbox: tuple[float, float, float, float] = (min_x, min_y, max_x, max_y)
            if crs.upper() not in ["EPSG:4326", "WGS84", "OGC:CRS84", "4326"]:
                try:
                    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
                    reprojected_rings: list[list[list[float]]] = []
                    all_lons: list[float] = []
                    all_lats: list[float] = []
                    for ring in coords:
                        reprojected_ring: list[list[float]] = []
                        for pt in ring:
                            lon, lat = transformer.transform(pt[0], pt[1])
                            reprojected_ring.append([round(float(lon), 6), round(float(lat), 6)])
                            all_lons.append(lon)
                            all_lats.append(lat)
                        reprojected_rings.append(reprojected_ring)
                    wgs84_coords = reprojected_rings
                    if all_lons and all_lats:
                        wgs84_bbox = (
                            round(float(min(all_lons)), 6),
                            round(float(min(all_lats)), 6),
                            round(float(max(all_lons)), 6),
                            round(float(max(all_lats)), 6),
                        )
                except Exception as exc:
                    logger.warning(f"Failed to reproject region polygon to EPSG:4326: {exc}")

            aoi_geom = AOIGeometry(
                type=GeometryType.POLYGON,
                coordinates=wgs84_coords,
                bbox=wgs84_bbox,
                crs="EPSG:4326",
                area_km2=area_km2,
            )

            regions.append(
                ChangeRegion(
                    id=region_id,
                    category=category,
                    geometry=aoi_geom,
                    area_km2=area_km2,
                    pixel_count=pixel_count,
                    mean_magnitude=mean_mag,
                    min_magnitude=min_mag,
                    max_magnitude=max_mag,
                    threshold_rule=(
                        f"Classified {category} (cluster size >= {min_cluster_pixels} px)"
                    ),
                    evidence_id=f"evd-chg-{uuid4().hex[:8]}",
                    confidence=0.88,
                    warnings=[
                        (
                            "Candidate spectral change region. "
                            "Ambiguity exists between surface materials."
                        )
                    ],
                )
            )

        # Sort by area descending and cap at max_regions
        regions.sort(key=lambda r: r.area_km2, reverse=True)
        return regions[:max_regions]

    @classmethod
    def generate_scientific_geotiff(
        cls,
        diff_arr: np.ndarray[Any, Any],
        shared_valid_mask: np.ndarray[Any, Any],
        crs: str,
        transform: list[float] | tuple[float, ...],
        method_name: str,
    ) -> bytes:
        """Serialize difference array into a 1-band Float32 GeoTIFF with explicit nodata."""
        height, width = diff_arr.shape
        out_data = np.where(shared_valid_mask & np.isfinite(diff_arr), diff_arr, -9999.0).astype(
            np.float32
        )
        affine_transform = Affine(*transform[:6])

        with MemoryFile() as memfile:
            with memfile.open(
                driver="GTiff",
                height=height,
                width=width,
                count=1,
                dtype="float32",
                crs=crs,
                transform=affine_transform,
                nodata=-9999.0,
                compress="deflate",
            ) as dst:
                dst.write(out_data, 1)
                dst.set_band_description(1, method_name)
            return bytes(memfile.getbuffer())

    @classmethod
    def generate_continuous_preview_png(
        cls,
        diff_arr: np.ndarray[Any, Any],
        shared_valid_mask: np.ndarray[Any, Any],
        color_ramp: str = "RdYlGn",
        vmin: float = -0.5,
        vmax: float = 0.5,
    ) -> bytes:
        """Render transparent 8-bit RGBA PNG preview with diverging color ramp."""
        lut = COLOR_LUTS.get(color_ramp, COLOR_LUTS["RdYlGn"])
        norm = np.clip((diff_arr - vmin) / max(1e-6, (vmax - vmin)), 0.0, 1.0)
        norm_sanitized = np.nan_to_num(norm, nan=0.5)
        norm_int = (norm_sanitized * 255.0).astype(np.uint8)

        rgb_data = lut[norm_int].transpose(2, 0, 1)
        alpha_mask = np.where(shared_valid_mask & np.isfinite(diff_arr), 255, 0).astype(np.uint8)

        return render(rgb_data, mask=alpha_mask, img_format="PNG")

    @classmethod
    def generate_classified_preview_png(
        cls,
        classified_arr: np.ndarray[Any, Any],
        shared_valid_mask: np.ndarray[Any, Any],
    ) -> bytes:
        """Render transparent 8-bit discrete mask PNG: Gain=Green, Loss=Red, Stable=Transparent."""
        height, width = classified_arr.shape
        rgba = np.zeros((4, height, width), dtype=np.uint8)

        gain_mask = shared_valid_mask & (classified_arr == 1)
        loss_mask = shared_valid_mask & (classified_arr == -1)

        # Gain -> Bright Emerald Green [34, 197, 94, 210]
        rgba[0, gain_mask] = 34
        rgba[1, gain_mask] = 197
        rgba[2, gain_mask] = 94
        rgba[3, gain_mask] = 210

        # Loss -> Vibrant Rose Red [239, 68, 68, 210]
        rgba[0, loss_mask] = 239
        rgba[1, loss_mask] = 68
        rgba[2, loss_mask] = 68
        rgba[3, loss_mask] = 210

        alpha_mask = np.where(gain_mask | loss_mask, 255, 0).astype(np.uint8)
        return render(rgba[:3], mask=alpha_mask, img_format="PNG")

    @classmethod
    def calculate_confidence(
        cls,
        shared_valid_percent: float,
        is_mock: bool,
        definition: ChangeDetectionDefinition,
    ) -> ConfidenceBreakdown:
        """Calculate explainable multi-factor confidence breakdown (0.0 - 1.0)."""
        coverage_score = min(1.0, max(0.20, shared_valid_percent / 100.0))
        origin_score = 0.80 if is_mock else 1.0
        grid_score = 1.0  # Rigidly verified
        method_score = 0.95

        factors = [
            ConfidenceFactor(
                code="grid_co_registration",
                label="Grid Co-Registration",
                score=grid_score,
                weight=0.30,
                explanation="Rigid pixel-to-pixel transform and spatial CRS alignment.",
            ),
            ConfidenceFactor(
                code="shared_valid_coverage",
                label="Shared Valid Coverage",
                score=round(coverage_score, 2),
                weight=0.30,
                explanation=f"{shared_valid_percent:.1f}% mutual valid observation coverage.",
            ),
            ConfidenceFactor(
                code="sensor_data_origin",
                label="Sensor Data Origin",
                score=origin_score,
                weight=0.20,
                explanation="Real calibrated surface reflectance observation."
                if not is_mock
                else "Deterministic mock scene fixture.",
            ),
            ConfidenceFactor(
                code="algorithmic_fidelity",
                label="Algorithmic Fidelity",
                score=method_score,
                weight=0.20,
                explanation=f"Standardized {definition.display_name} formulation.",
            ),
        ]

        overall = sum(f.score * f.weight for f in factors)

        return ConfidenceBreakdown(
            overall=round(overall, 2),
            data_quality=origin_score,
            temporal_quality=0.95,
            spatial_quality=grid_score,
            model_confidence=method_score,
            evidence_agreement=round(coverage_score, 2),
            factors=factors,
            methodology=(
                "Weighted combination of spatial co-registration fidelity, "
                "shared valid observation coverage, and radiometric data origin."
            ),
            limitations=[
                "Pixel differencing indicates spectral shift, not verified semantic "
                "land-cover transition.",
                "Sun angle differences, seasonal phenology, and soil moisture "
                "variations can generate candidate change.",
            ],
        )
