"""Core geospatial engine for raster harmonization, reprojection, and grid alignment."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from rasterio.transform import Affine
from rasterio.warp import calculate_default_transform, reproject, transform_geom
from rio_tiler.utils import render

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    AOIGeometry,
    WarningSeverity,
)
from satquery.api.schemas.imagery import (
    AlignmentStatus,
)
from satquery.api.schemas.preparation import (
    PREPARATION_SCHEMA_VERSION,
    RasterProvenance,
    RasterQualityMetrics,
    ResamplingMethod,
    TargetGridStrategy,
)
from satquery.api.schemas.providers import DataOrigin

logger = logging.getLogger(__name__)

RESAMPLING_MAP: dict[ResamplingMethod, Resampling] = {
    ResamplingMethod.NEAREST: Resampling.nearest,
    ResamplingMethod.BILINEAR: Resampling.bilinear,
    ResamplingMethod.CUBIC: Resampling.cubic,
    ResamplingMethod.AVERAGE: Resampling.average,
}


class HarmonizationError(Exception):
    """Exception raised for raster harmonization and alignment failures."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(slots=True)
class HarmonizedRasterResult:
    geotiff_bytes: bytes
    preview_png_bytes: bytes
    crs: str
    bbox: tuple[float, float, float, float]
    width: int
    height: int
    pixel_size_x: float
    pixel_size_y: float
    transform: list[float]
    band_count: int
    band_names: list[str]
    data_type: str
    no_data_values: list[float | None]
    valid_pixel_count: int
    invalid_pixel_count: int
    valid_data_percent: float
    resolution_meters: float
    warnings: list[AnalysisWarning]
    provenance: RasterProvenance


@dataclass(slots=True)
class TemporalHarmonizationResult:
    before_result: HarmonizedRasterResult
    after_result: HarmonizedRasterResult
    common_crs: str
    common_bbox: tuple[float, float, float, float]
    common_width: int
    common_height: int
    common_transform: list[float]
    common_resolution_meters: float
    shared_valid_pixel_count: int
    shared_valid_percent: float
    alignment_status: AlignmentStatus
    quality: RasterQualityMetrics
    warnings: list[AnalysisWarning]
    blocking_issues: list[str]
    ready_for_analysis: bool


class RasterHarmonizer:
    """Scientific geospatial processor for clipping, reprojection, and grid co-registration."""

    @staticmethod
    def calculate_utm_epsg(lon: float, lat: float) -> int:
        """Compute the appropriate WGS84 UTM EPSG code for a given longitude and latitude."""
        zone = int(np.floor((lon + 180.0) / 6.0)) + 1
        zone = max(1, min(60, zone))
        return 32600 + zone if lat >= 0 else 32700 + zone

    @classmethod
    def determine_target_crs(
        cls,
        aoi: AOIGeometry,
        requested_crs: str | None = None,
    ) -> tuple[str, list[AnalysisWarning]]:
        """Determine and validate the target projected metric CRS (e.g. UTM)."""
        warnings: list[AnalysisWarning] = []

        if requested_crs and requested_crs.strip().upper() not in {"AUTO", ""}:
            try:
                crs_obj = CRS.from_user_input(requested_crs.strip())
                if crs_obj.is_geographic:
                    warnings.append(
                        AnalysisWarning(
                            code="GEOGRAPHIC_CRS_NOT_SUITABLE_FOR_METRIC_GRID",
                            severity=WarningSeverity.MEDIUM,
                            title="Geographic Target CRS",
                            message=(
                                f"Target CRS '{requested_crs}' is geographic (degrees); "
                                "metric grid calculations may be distorted."
                            ),
                        )
                    )
                return crs_obj.to_string(), warnings
            except Exception as exc:
                raise HarmonizationError(
                    "UNSUPPORTED_TARGET_CRS", f"Invalid target CRS '{requested_crs}': {exc}"
                ) from exc

        # Calculate centroid from AOI coordinates
        lons: list[float] = []
        lats: list[float] = []
        for ring in aoi.coordinates:
            for coord in ring:
                lons.append(coord[0])
                lats.append(coord[1])

        if not lons or not lats:
            raise HarmonizationError("INVALID_AOI_GEOMETRY", "AOI coordinate array is empty.")

        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)
        centroid_lon = (min_lon + max_lon) / 2.0
        centroid_lat = (min_lat + max_lat) / 2.0

        if (max_lon - min_lon) > 6.0:
            warnings.append(
                AnalysisWarning(
                    code="AOI_SPANS_MULTIPLE_ZONES",
                    severity=WarningSeverity.LOW,
                    title="AOI Spans Multiple UTM Zones",
                    message=(
                        "The AOI spans multiple UTM zones (>6° longitude). "
                        "Selected primary zone centroid."
                    ),
                )
            )

        epsg = cls.calculate_utm_epsg(centroid_lon, centroid_lat)
        target_crs_str = f"EPSG:{epsg}"
        warnings.append(
            AnalysisWarning(
                code="TARGET_CRS_SELECTED_AUTOMATICALLY",
                severity=WarningSeverity.INFO,
                title="Target Metric CRS Selected",
                message=f"Automatically selected UTM metric projected CRS {target_crs_str}.",
            )
        )
        return target_crs_str, warnings

    @classmethod
    def reproject_and_harmonize_single(
        cls,
        *,
        source_bytes: bytes,
        source_asset_id: str,
        scene_id: str,
        aoi: AOIGeometry,
        target_crs: str | None = None,
        target_resolution_meters: float | None = None,
        resampling_method: ResamplingMethod = ResamplingMethod.BILINEAR,
        selected_bands: list[str] | None = None,
        clip_to_aoi: bool = True,
        mask_no_data: bool = True,
        data_origin: DataOrigin = DataOrigin.REAL,
    ) -> HarmonizedRasterResult:
        """Harmonise, reproject to metric grid, clip to AOI, and mask invalid pixels."""
        start_time = time.perf_counter()
        started_at = datetime.now(UTC)
        warnings: list[AnalysisWarning] = []
        operations: list[str] = []

        resolved_crs, crs_warnings = cls.determine_target_crs(aoi, target_crs)
        warnings.extend(crs_warnings)
        operations.append(f"select_target_crs:{resolved_crs}")

        with MemoryFile(source_bytes) as memfile, memfile.open() as src:
            src_crs = src.crs
            src_transform = src.transform
            src_width = src.width
            src_height = src.height
            src_dtypes = src.dtypes
            src_nodata = src.nodata

            if src_crs is None:
                raise HarmonizationError(
                    "MISSING_SOURCE_CRS", "Source analysis raster is missing georeferenced CRS."
                )

            # Transform AOI polygon to target CRS
            aoi_geojson = {"type": aoi.type, "coordinates": aoi.coordinates}
            try:
                transformed_aoi = transform_geom("EPSG:4326", resolved_crs, aoi_geojson)
            except Exception as exc:
                raise HarmonizationError(
                    "CRS_TRANSFORMATION_FAILED", f"Failed to transform AOI to {resolved_crs}: {exc}"
                ) from exc

            # Compute bounding box in target CRS
            aoi_coords = transformed_aoi["coordinates"]
            all_x: list[float] = []
            all_y: list[float] = []
            for ring in aoi_coords:
                for pt in ring:
                    all_x.append(pt[0])
                    all_y.append(pt[1])
            min_x, max_x = min(all_x), max(all_x)
            min_y, max_y = min(all_y), max(all_y)

            # Determine native resolution in target CRS
            native_transform, _, _ = calculate_default_transform(
                src_crs, resolved_crs, src_width, src_height, *src.bounds
            )
            native_res_x = abs(native_transform.a)
            native_res_y = abs(native_transform.e)
            native_res = (native_res_x + native_res_y) / 2.0

            res = target_resolution_meters or native_res
            res_x = res
            res_y = res

            if target_resolution_meters is not None:
                if target_resolution_meters < native_res * 0.9:
                    warnings.append(
                        AnalysisWarning(
                            code="UPSAMPLING_APPLIED",
                            severity=WarningSeverity.MEDIUM,
                            title="Upsampling Applied",
                            message=(
                                f"Requested resolution ({target_resolution_meters}m) is finer than "
                                f"native resolution ({native_res:.1f}m). Upsampling does not add "
                                "new detail."
                            ),
                        )
                    )
                elif target_resolution_meters > native_res * 1.1:
                    warnings.append(
                        AnalysisWarning(
                            code="DOWNSAMPLING_APPLIED",
                            severity=WarningSeverity.LOW,
                            title="Downsampling Applied",
                            message=(
                                f"Requested resolution ({target_resolution_meters}m) is coarser "
                                f"than native resolution ({native_res:.1f}m)."
                            ),
                        )
                    )

            # Snap destination bounds to target pixel grid
            snap_min_x = np.floor(min_x / res_x) * res_x
            snap_max_y = np.ceil(max_y / res_y) * res_y
            dst_width = max(1, round((max_x - min_x) / res_x))
            dst_height = max(1, round((max_y - min_y) / res_y))
            dst_transform = Affine.translation(snap_min_x, snap_max_y) @ Affine.scale(res_x, -res_y)

            # Check pixel safety limits
            total_pixels = dst_width * dst_height
            if total_pixels > 16_777_216:
                raise HarmonizationError(
                    "PIXEL_LIMIT_EXCEEDED",
                    (
                        f"Calculated dimensions ({dst_width}x{dst_height} = {total_pixels:,} px) "
                        "exceed 16MP limit."
                    ),
                )

            # Allocate destination array
            band_count = src.count
            dst_nodata_val = -9999.0 if np.issubdtype(src_dtypes[0], np.floating) else 0.0
            if src_nodata is not None:
                dst_nodata_val = float(src_nodata)

            dst_data = np.full(
                (band_count, dst_height, dst_width), dst_nodata_val, dtype=np.float32
            )

            rasterio_resampling = RESAMPLING_MAP.get(resampling_method, Resampling.bilinear)
            for b_idx in range(1, band_count + 1):
                src_band = src.read(b_idx).astype(np.float32)
                reproject(
                    source=src_band,
                    destination=dst_data[b_idx - 1],
                    src_transform=src_transform,
                    src_crs=src_crs,
                    dst_transform=dst_transform,
                    dst_crs=resolved_crs,
                    src_nodata=src_nodata,
                    dst_nodata=dst_nodata_val,
                    resampling=rasterio_resampling,
                )
            operations.append(f"reproject:{resampling_method.value}")

            # Exact AOI polygon clipping mask
            if clip_to_aoi:
                aoi_mask = geometry_mask(
                    [transformed_aoi],
                    out_shape=(dst_height, dst_width),
                    transform=dst_transform,
                    invert=True,  # True inside AOI polygon
                )
                for b_idx in range(band_count):
                    dst_data[b_idx][~aoi_mask] = dst_nodata_val
                operations.append("aoi_polygon_mask")

            # Validate valid/invalid pixels
            valid_mask = (dst_data[0] != dst_nodata_val) & ~np.isnan(dst_data[0])
            valid_pixels = int(np.count_nonzero(valid_mask))
            invalid_pixels = int(total_pixels - valid_pixels)
            valid_percent = float((valid_pixels / total_pixels) * 100.0) if total_pixels > 0 else 0

            if valid_percent < 5.0:
                warnings.append(
                    AnalysisWarning(
                        code="LOW_VALID_DATA_COVERAGE",
                        severity=WarningSeverity.HIGH,
                        title="Low Valid Data Coverage",
                        message=(
                            f"Prepared raster has only {valid_percent:.1f}% valid data "
                            "within requested bounds."
                        ),
                    )
                )

            # Compute WGS84 bounding box for metadata
            transformer_to_wgs84 = Transformer.from_crs(resolved_crs, "EPSG:4326", always_xy=True)
            wgs84_min_lon, wgs84_min_lat = transformer_to_wgs84.transform(min_x, min_y)
            wgs84_max_lon, wgs84_max_lat = transformer_to_wgs84.transform(max_x, max_y)
            wgs84_bbox = (
                min(wgs84_min_lon, wgs84_max_lon),
                min(wgs84_min_lat, wgs84_max_lat),
                max(wgs84_min_lon, wgs84_max_lon),
                max(wgs84_min_lat, wgs84_max_lat),
            )

            # Write prepared GeoTIFF
            out_profile = {
                "driver": "GTiff",
                "height": dst_height,
                "width": dst_width,
                "count": band_count,
                "dtype": "float32",
                "crs": resolved_crs,
                "transform": dst_transform,
                "nodata": dst_nodata_val,
                "compress": "lzw",
            }

            out_mem = MemoryFile()
            with out_mem.open(**out_profile) as dst:
                dst.write(dst_data)
                dst.descriptions = src.descriptions or tuple(
                    f"B{i}" for i in range(1, band_count + 1)
                )

            geotiff_bytes = bytes(out_mem.getbuffer())
            out_mem.close()

            # Generate transparent 8-bit RGB preview PNG
            preview_bytes = cls._generate_preview_png(dst_data, valid_mask)
            operations.append("generate_preview_png")

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        completed_at = datetime.now(UTC)

        provenance = RasterProvenance(
            pipeline_version=PREPARATION_SCHEMA_VERSION,
            source_asset_ids=[source_asset_id],
            source_scene_ids=[scene_id],
            operations=operations,
            parameters={
                "target_crs": resolved_crs,
                "resolution_meters": res,
                "resampling_method": resampling_method.value,
                "clip_to_aoi": clip_to_aoi,
                "mask_no_data": mask_no_data,
            },
            software="SatQuery Raster Harmonizer 1.0 (Rasterio/GDAL)",
            started_at=started_at,
            completed_at=completed_at,
            duration_milliseconds=round(duration_ms, 2),
            data_origin=data_origin,
        )

        return HarmonizedRasterResult(
            geotiff_bytes=geotiff_bytes,
            preview_png_bytes=preview_bytes,
            crs=resolved_crs,
            bbox=wgs84_bbox,
            width=dst_width,
            height=dst_height,
            pixel_size_x=res_x,
            pixel_size_y=res_y,
            transform=[
                dst_transform.a,
                dst_transform.b,
                dst_transform.c,
                dst_transform.d,
                dst_transform.e,
                dst_transform.f,
            ],
            band_count=band_count,
            band_names=list(selected_bands or [f"B{i}" for i in range(1, band_count + 1)]),
            data_type="float32",
            no_data_values=[dst_nodata_val] * band_count,
            valid_pixel_count=valid_pixels,
            invalid_pixel_count=invalid_pixels,
            valid_data_percent=round(valid_percent, 2),
            resolution_meters=round(res, 2),
            warnings=warnings,
            provenance=provenance,
        )

    @classmethod
    def harmonize_and_align_temporal_pair(
        cls,
        *,
        before_bytes: bytes,
        after_bytes: bytes,
        before_asset_id: str,
        after_asset_id: str,
        before_scene_id: str,
        after_scene_id: str,
        aoi: AOIGeometry,
        strategy: TargetGridStrategy = TargetGridStrategy.COMMON_INTERSECTION,
        target_crs: str | None = None,
        target_resolution_meters: float | None = None,
        optical_resampling: ResamplingMethod = ResamplingMethod.BILINEAR,
        sar_resampling: ResamplingMethod = ResamplingMethod.BILINEAR,
        mask_resampling: ResamplingMethod = ResamplingMethod.NEAREST,
        use_common_intersection: bool = True,
        before_origin: DataOrigin = DataOrigin.REAL,
        after_origin: DataOrigin = DataOrigin.REAL,
    ) -> TemporalHarmonizationResult:
        """Harmonise before/after temporal rasters onto a mathematically identical analysis grid."""
        start_time = time.perf_counter()
        started_at = datetime.now(UTC)
        warnings: list[AnalysisWarning] = []
        blocking_issues: list[str] = []

        if before_origin != after_origin:
            blocking_issues.append("MIXED_DATA_ORIGIN")
            warnings.append(
                AnalysisWarning(
                    code="MIXED_DATA_ORIGIN",
                    severity=WarningSeverity.HIGH,
                    title="Mixed Data Origin",
                    message="Temporal pair mixes synthetic mock data and real provider imagery.",
                )
            )

        resolved_crs, crs_warnings = cls.determine_target_crs(aoi, target_crs)
        warnings.extend(crs_warnings)

        # Open both rasters to inspect source geometries
        with (
            MemoryFile(before_bytes) as mem_b,
            mem_b.open() as src_b,
            MemoryFile(after_bytes) as mem_a,
            mem_a.open() as src_a,
        ):
            if src_b.crs is None or src_a.crs is None:
                raise HarmonizationError(
                    "MISSING_SOURCE_CRS", "One or both temporal rasters lack valid CRS metadata."
                )

            # Transform AOI polygon to target CRS
            aoi_geojson = {"type": aoi.type, "coordinates": aoi.coordinates}
            transformed_aoi = transform_geom("EPSG:4326", resolved_crs, aoi_geojson)

            aoi_coords = transformed_aoi["coordinates"]
            all_x = [pt[0] for ring in aoi_coords for pt in ring]
            all_y = [pt[1] for ring in aoi_coords for pt in ring]
            aoi_min_x, aoi_max_x = min(all_x), max(all_x)
            aoi_min_y, aoi_max_y = min(all_y), max(all_y)

            # Native resolutions in target CRS
            trans_b, _, _ = calculate_default_transform(
                src_b.crs, resolved_crs, src_b.width, src_b.height, *src_b.bounds
            )
            trans_a, _, _ = calculate_default_transform(
                src_a.crs, resolved_crs, src_a.width, src_a.height, *src_a.bounds
            )
            res_b = (abs(trans_b.a) + abs(trans_b.e)) / 2.0
            res_a = (abs(trans_a.a) + abs(trans_a.e)) / 2.0

            # Resolution strategy
            if strategy == TargetGridStrategy.REFERENCE_BEFORE:
                common_res = res_b
            elif strategy == TargetGridStrategy.REFERENCE_AFTER:
                common_res = res_a
            elif strategy == TargetGridStrategy.HIGHEST_RESOLUTION:
                common_res = min(res_b, res_a)
            elif strategy == TargetGridStrategy.LOWEST_RESOLUTION:
                common_res = max(res_b, res_a)
            elif strategy == TargetGridStrategy.CONFIGURED_RESOLUTION and target_resolution_meters:
                common_res = target_resolution_meters
            else:
                common_res = target_resolution_meters or min(res_b, res_a)

            # Transform source bounds to target CRS
            transformer_b = Transformer.from_crs(src_b.crs, resolved_crs, always_xy=True)
            transformer_a = Transformer.from_crs(src_a.crs, resolved_crs, always_xy=True)

            b_min_x, b_min_y = transformer_b.transform(src_b.bounds.left, src_b.bounds.bottom)
            b_max_x, b_max_y = transformer_b.transform(src_b.bounds.right, src_b.bounds.top)
            a_min_x, a_min_y = transformer_a.transform(src_a.bounds.left, src_a.bounds.bottom)
            a_max_x, a_max_y = transformer_a.transform(src_a.bounds.right, src_a.bounds.top)

            # Common extent bounding box
            if use_common_intersection:
                min_x = max(min(b_min_x, b_max_x), min(a_min_x, a_max_x), aoi_min_x)
                max_x = min(max(b_min_x, b_max_x), max(a_min_x, a_max_x), aoi_max_x)
                min_y = max(min(b_min_y, b_max_y), min(a_min_y, a_max_y), aoi_min_y)
                max_y = min(max(b_min_y, b_max_y), max(a_min_y, a_max_y), aoi_max_y)

                if min_x >= max_x or min_y >= max_y:
                    blocking_issues.append("NO_SHARED_COVERAGE")
                    # Fallback to AOI extent to allow failure diagnostics
                    min_x, max_x = aoi_min_x, aoi_max_x
                    min_y, max_y = aoi_min_y, aoi_max_y
            else:
                min_x, max_x = aoi_min_x, aoi_max_x
                min_y, max_y = aoi_min_y, aoi_max_y

            # Snap to integer pixel grid
            snap_min_x = np.floor(min_x / common_res) * common_res
            snap_max_y = np.ceil(max_y / common_res) * common_res
            common_width = max(1, round((max_x - min_x) / common_res))
            common_height = max(1, round((max_y - min_y) / common_res))
            common_transform = Affine.translation(snap_min_x, snap_max_y) @ Affine.scale(
                common_res, -common_res
            )

            total_pixels = common_width * common_height
            if total_pixels > 16_777_216:
                raise HarmonizationError(
                    "PIXEL_LIMIT_EXCEEDED",
                    f"Aligned dimensions ({common_width}x{common_height} = {total_pixels:,} px) "
                    "exceed 16MP limit.",
                )

            nodata_val = -9999.0
            data_b = np.full(
                (src_b.count, common_height, common_width), nodata_val, dtype=np.float32
            )
            data_a = np.full(
                (src_a.count, common_height, common_width), nodata_val, dtype=np.float32
            )

            resamp_b = RESAMPLING_MAP.get(optical_resampling, Resampling.bilinear)
            resamp_a = RESAMPLING_MAP.get(optical_resampling, Resampling.bilinear)

            for b_idx in range(1, src_b.count + 1):
                reproject(
                    source=src_b.read(b_idx).astype(np.float32),
                    destination=data_b[b_idx - 1],
                    src_transform=src_b.transform,
                    src_crs=src_b.crs,
                    dst_transform=common_transform,
                    dst_crs=resolved_crs,
                    src_nodata=src_b.nodata,
                    dst_nodata=nodata_val,
                    resampling=resamp_b,
                )

            for b_idx in range(1, src_a.count + 1):
                reproject(
                    source=src_a.read(b_idx).astype(np.float32),
                    destination=data_a[b_idx - 1],
                    src_transform=src_a.transform,
                    src_crs=src_a.crs,
                    dst_transform=common_transform,
                    dst_crs=resolved_crs,
                    src_nodata=src_a.nodata,
                    dst_nodata=nodata_val,
                    resampling=resamp_a,
                )

            # AOI clipping mask applied to both
            aoi_mask = geometry_mask(
                [transformed_aoi],
                out_shape=(common_height, common_width),
                transform=common_transform,
                invert=True,
            )
            for b_idx in range(src_b.count):
                data_b[b_idx][~aoi_mask] = nodata_val
            for b_idx in range(src_a.count):
                data_a[b_idx][~aoi_mask] = nodata_val

            # Shared validity mask calculation
            valid_b = (data_b[0] != nodata_val) & ~np.isnan(data_b[0])
            valid_a = (data_a[0] != nodata_val) & ~np.isnan(data_a[0])
            shared_valid = valid_b & valid_a
            shared_valid_count = int(np.count_nonzero(shared_valid))
            shared_valid_pct = (
                float((shared_valid_count / total_pixels) * 100.0) if total_pixels > 0 else 0
            )

            if shared_valid_count == 0:
                blocking_issues.append("NO_SHARED_VALID_PIXELS")
                warnings.append(
                    AnalysisWarning(
                        code="NO_SHARED_VALID_PIXELS",
                        severity=WarningSeverity.HIGH,
                        title="No Shared Valid Pixels",
                        message=(
                            "Zero shared valid pixels exist between the two "
                            "acquisitions within the AOI."
                        ),
                    )
                )
            elif shared_valid_pct < 10.0:
                warnings.append(
                    AnalysisWarning(
                        code="SHARED_VALID_COVERAGE_LOW",
                        severity=WarningSeverity.MEDIUM,
                        title="Low Shared Valid Coverage",
                        message=(
                            f"Shared valid data coverage is low ({shared_valid_pct:.1f}%). "
                            "Change analysis reliability may be limited."
                        ),
                    )
                )

            # Compute WGS84 bounding box
            trans_to_wgs84 = Transformer.from_crs(resolved_crs, "EPSG:4326", always_xy=True)
            wgs84_min_lon, wgs84_min_lat = trans_to_wgs84.transform(min_x, min_y)
            wgs84_max_lon, wgs84_max_lat = trans_to_wgs84.transform(max_x, max_y)
            wgs84_bbox = (
                min(wgs84_min_lon, wgs84_max_lon),
                min(wgs84_min_lat, wgs84_max_lat),
                max(wgs84_min_lon, wgs84_max_lon),
                max(wgs84_min_lat, wgs84_max_lat),
            )

            # Write before and after GeoTIFFs
            profile = {
                "driver": "GTiff",
                "height": common_height,
                "width": common_width,
                "count": src_b.count,
                "dtype": "float32",
                "crs": resolved_crs,
                "transform": common_transform,
                "nodata": nodata_val,
                "compress": "lzw",
            }

            mem_out_b = MemoryFile()
            with mem_out_b.open(**profile) as dst:
                dst.write(data_b)
                if src_b.descriptions:
                    dst.descriptions = src_b.descriptions
            geotiff_b = bytes(mem_out_b.getbuffer())
            mem_out_b.close()

            profile["count"] = src_a.count
            mem_out_a = MemoryFile()
            with mem_out_a.open(**profile) as dst:
                dst.write(data_a)
                if src_a.descriptions:
                    dst.descriptions = src_a.descriptions
            geotiff_a = bytes(mem_out_a.getbuffer())
            mem_out_a.close()

            preview_b = cls._generate_preview_png(data_b, valid_b)
            preview_a = cls._generate_preview_png(data_a, valid_a)

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        completed_at = datetime.now(UTC)

        prov_b = RasterProvenance(
            pipeline_version=PREPARATION_SCHEMA_VERSION,
            source_asset_ids=[before_asset_id],
            source_scene_ids=[before_scene_id],
            operations=["reproject_common_grid", "aoi_polygon_mask", "generate_preview_png"],
            parameters={
                "target_crs": resolved_crs,
                "common_resolution_meters": common_res,
                "strategy": strategy.value,
            },
            software="SatQuery Raster Harmonizer 1.0 (Rasterio/GDAL)",
            started_at=started_at,
            completed_at=completed_at,
            duration_milliseconds=round(duration_ms, 2),
            data_origin=before_origin,
        )

        prov_a = RasterProvenance(
            pipeline_version=PREPARATION_SCHEMA_VERSION,
            source_asset_ids=[after_asset_id],
            source_scene_ids=[after_scene_id],
            operations=["reproject_common_grid", "aoi_polygon_mask", "generate_preview_png"],
            parameters={
                "target_crs": resolved_crs,
                "common_resolution_meters": common_res,
                "strategy": strategy.value,
            },
            software="SatQuery Raster Harmonizer 1.0 (Rasterio/GDAL)",
            started_at=started_at,
            completed_at=completed_at,
            duration_milliseconds=round(duration_ms, 2),
            data_origin=after_origin,
        )

        res_b_out = HarmonizedRasterResult(
            geotiff_bytes=geotiff_b,
            preview_png_bytes=preview_b,
            crs=resolved_crs,
            bbox=wgs84_bbox,
            width=common_width,
            height=common_height,
            pixel_size_x=common_res,
            pixel_size_y=common_res,
            transform=[
                common_transform.a,
                common_transform.b,
                common_transform.c,
                common_transform.d,
                common_transform.e,
                common_transform.f,
            ],
            band_count=src_b.count,
            band_names=[f"B{i}" for i in range(1, src_b.count + 1)],
            data_type="float32",
            no_data_values=[nodata_val] * src_b.count,
            valid_pixel_count=int(np.count_nonzero(valid_b)),
            invalid_pixel_count=int(total_pixels - np.count_nonzero(valid_b)),
            valid_data_percent=round(float((np.count_nonzero(valid_b) / total_pixels) * 100.0), 2),
            resolution_meters=round(common_res, 2),
            warnings=warnings,
            provenance=prov_b,
        )

        res_a_out = HarmonizedRasterResult(
            geotiff_bytes=geotiff_a,
            preview_png_bytes=preview_a,
            crs=resolved_crs,
            bbox=wgs84_bbox,
            width=common_width,
            height=common_height,
            pixel_size_x=common_res,
            pixel_size_y=common_res,
            transform=[
                common_transform.a,
                common_transform.b,
                common_transform.c,
                common_transform.d,
                common_transform.e,
                common_transform.f,
            ],
            band_count=src_a.count,
            band_names=[f"B{i}" for i in range(1, src_a.count + 1)],
            data_type="float32",
            no_data_values=[nodata_val] * src_a.count,
            valid_pixel_count=int(np.count_nonzero(valid_a)),
            invalid_pixel_count=int(total_pixels - np.count_nonzero(valid_a)),
            valid_data_percent=round(float((np.count_nonzero(valid_a) / total_pixels) * 100.0), 2),
            resolution_meters=round(common_res, 2),
            warnings=warnings,
            provenance=prov_a,
        )

        res_consistency = min(res_b, res_a) / max(res_b, res_a) if max(res_b, res_a) > 0 else 1.0
        quality_score = float(
            np.clip(
                (shared_valid_pct / 100.0) * 0.5
                + res_consistency * 0.3
                + (1.0 if not blocking_issues else 0.0) * 0.2,
                0.0,
                1.0,
            )
        )

        quality_metrics = RasterQualityMetrics(
            valid_data_percent=round(
                min(res_b_out.valid_data_percent, res_a_out.valid_data_percent), 2
            ),
            no_data_percent=round(100.0 - shared_valid_pct, 2),
            aoi_coverage_percent=round(shared_valid_pct, 2),
            shared_coverage_percent=round(shared_valid_pct, 2),
            resolution_consistency=round(res_consistency, 3),
            grid_alignment_score=1.0,  # Exact mathematical alignment
            metadata_completeness=1.0,
            quality_score=round(quality_score, 3),
            factors={
                "shared_valid_coverage": round(shared_valid_pct / 100.0, 3),
                "resolution_consistency": round(res_consistency, 3),
                "grid_alignment": 1.0,
            },
            limitations=[
                "Display contrast stretching is excluded from analysis bands.",
                (
                    "Scientific co-registration does not perform radiometric "
                    "calibration or atmospheric correction."
                ),
            ],
        )

        ready_for_analysis = len(blocking_issues) == 0 and shared_valid_pct > 5.0

        return TemporalHarmonizationResult(
            before_result=res_b_out,
            after_result=res_a_out,
            common_crs=resolved_crs,
            common_bbox=wgs84_bbox,
            common_width=common_width,
            common_height=common_height,
            common_transform=[
                common_transform.a,
                common_transform.b,
                common_transform.c,
                common_transform.d,
                common_transform.e,
                common_transform.f,
            ],
            common_resolution_meters=round(common_res, 2),
            shared_valid_pixel_count=shared_valid_count,
            shared_valid_percent=round(shared_valid_pct, 2),
            alignment_status=AlignmentStatus.ALIGNED,
            quality=quality_metrics,
            warnings=warnings,
            blocking_issues=blocking_issues,
            ready_for_analysis=ready_for_analysis,
        )

    @staticmethod
    def _generate_preview_png(data: np.ndarray, valid_mask: np.ndarray) -> bytes:
        """Create a transparent 8-bit RGBA display PNG from multi-band analysis raster."""
        band_count, height, width = data.shape

        if band_count >= 3:
            r_band, g_band, b_band = data[0], data[1], data[2]
        else:
            r_band = g_band = b_band = data[0]

        rgb_stretched = np.zeros((3, height, width), dtype=np.uint8)
        for i, band in enumerate([r_band, g_band, b_band]):
            valid_pixels = band[valid_mask]
            if len(valid_pixels) > 0:
                p2 = np.percentile(valid_pixels, 2)
                p98 = np.percentile(valid_pixels, 98)
                if p98 > p2:
                    stretched = np.clip((band - p2) / (p98 - p2) * 255.0, 0, 255).astype(np.uint8)
                else:
                    stretched = np.clip(band, 0, 255).astype(np.uint8)
            else:
                stretched = np.zeros_like(band, dtype=np.uint8)

            rgb_stretched[i] = stretched

        mask_uint8 = np.where(valid_mask, 255, 0).astype(np.uint8)
        return render(rgb_stretched, mask=mask_uint8, img_format="PNG")
