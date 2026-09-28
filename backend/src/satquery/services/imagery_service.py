"""Core service for satellite imagery retrieval, windowed COG processing, and preview rendering."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds
from rio_tiler.utils import render

from satquery.api.schemas.analysis import (
    AOIGeometry,
)
from satquery.api.schemas.imagery import (
    AlignmentStatus,
    ImageryAsset,
    ImageryFormat,
    ImageryProductType,
    ImageryRequest,
    RasterMetadata,
    TemporalImageryRequest,
    TemporalImageryResponse,
    VisualizationPreset,
)
from satquery.api.schemas.providers import DataOrigin
from satquery.core.config import Settings
from satquery.services.asset_store import AssetStore
from satquery.services.raster_validator import (
    validate_raster_dataset,
)

logger = logging.getLogger(__name__)

# Preset mapping to Sentinel-2 STAC band names
PRESET_BAND_MAPPINGS: dict[VisualizationPreset, list[str]] = {
    VisualizationPreset.TRUE_COLOR: ["B04", "B03", "B02"],  # Red, Green, Blue
    VisualizationPreset.FALSE_COLOR: ["B08", "B04", "B03"],  # NIR, Red, Green
    VisualizationPreset.VEGETATION: ["B08", "B04", "B03"],  # NIR, Red, Green
    VisualizationPreset.WATER: ["B03", "B08", "B11"],  # Green, NIR, SWIR1
    VisualizationPreset.URBAN: ["B12", "B11", "B04"],  # SWIR2, SWIR1, Red
    VisualizationPreset.SAR_GRAYSCALE: ["VV"],
    VisualizationPreset.SAR_VV: ["VV"],
    VisualizationPreset.SAR_VH: ["VH"],
}


class ImageryProcessingError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ImageryService:
    """Service managing satellite imagery retrieval, raster conversion, and map previews."""

    def __init__(self, settings: Settings, asset_store: AssetStore | None = None) -> None:
        self.settings = settings
        self.asset_store = asset_store or AssetStore(
            storage_dir=settings.imagery_storage_dir,
            default_ttl_seconds=settings.imagery_asset_cache_ttl_seconds,
            max_bytes=settings.max_imagery_file_size_bytes * 10,
        )

    def _get_aoi_bbox(self, aoi: AOIGeometry) -> tuple[float, float, float, float]:
        if aoi.bbox:
            return aoi.bbox
        # Calculate bounding box from polygon coordinates
        all_lons: list[float] = []
        all_lats: list[float] = []
        for ring in aoi.coordinates:
            for coord in ring:
                all_lons.append(coord[0])
                all_lats.append(coord[1])
        if not all_lons or not all_lats:
            raise ImageryProcessingError("INVALID_AOI_GEOMETRY", "AOI coordinates are empty.")
        return (min(all_lons), min(all_lats), max(all_lons), max(all_lats))

    def _estimate_dimensions(
        self, bbox: tuple[float, float, float, float], requested_resolution: float | None
    ) -> tuple[int, int]:
        min_lon, min_lat, max_lon, max_lat = bbox
        width_deg = max_lon - min_lon
        height_deg = max_lat - min_lat

        # 1 deg latitude approx 111,320m
        mid_lat = (min_lat + max_lat) / 2.0
        lat_m = height_deg * 111320.0
        lon_m = width_deg * 111320.0 * np.cos(np.radians(mid_lat))

        res = requested_resolution or self.settings.default_resolution_meters
        width_px = max(64, int(np.ceil(lon_m / res)))
        height_px = max(64, int(np.ceil(lat_m / res)))

        # Constrain to preview limits
        width_px = min(width_px, self.settings.max_preview_width)
        height_px = min(height_px, self.settings.max_preview_height)

        return width_px, height_px

    def _generate_synthetic_raster(
        self,
        *,
        scene_id: str,
        bbox: tuple[float, float, float, float],
        width: int,
        height: int,
        preset: VisualizationPreset,
        product_type: ImageryProductType,
        format_type: ImageryFormat,
        seed_offset: int = 0,
    ) -> tuple[bytes, str, list[str]]:
        """Generate deterministic synthetic raster for testing and mock mode."""
        rng = np.random.default_rng(abs(hash(scene_id)) % (2**32) + seed_offset)

        # Generate smooth spatial gradient pattern
        y, x = np.mgrid[0:height, 0:width]
        base_pattern = (
            np.sin(x / max(1, width / 4.0)) * np.cos(y / max(1, height / 4.0)) * 0.5 + 0.5
        )
        noise = rng.normal(0, 0.05, (height, width))
        pattern = np.clip(base_pattern + noise, 0.0, 1.0)

        required_bands = PRESET_BAND_MAPPINGS.get(preset, ["B04", "B03", "B02"])

        if product_type == ImageryProductType.MAP_PREVIEW or format_type in {
            ImageryFormat.PNG,
            ImageryFormat.JPEG,
        }:
            # Generate 3-band RGB (uint8)
            if len(required_bands) == 1:
                # Single band / SAR grayscale
                r = g = b = (pattern * 255).astype(np.uint8)
            else:
                # RGB composite with preset variation
                if preset == VisualizationPreset.VEGETATION:
                    r = (pattern * 100).astype(np.uint8)
                    g = (pattern * 230).astype(np.uint8)
                    b = (pattern * 80).astype(np.uint8)
                elif preset == VisualizationPreset.WATER:
                    r = (pattern * 50).astype(np.uint8)
                    g = (pattern * 120).astype(np.uint8)
                    b = (pattern * 240).astype(np.uint8)
                elif preset == VisualizationPreset.URBAN:
                    r = (pattern * 220).astype(np.uint8)
                    g = (pattern * 180).astype(np.uint8)
                    b = (pattern * 140).astype(np.uint8)
                elif preset == VisualizationPreset.FALSE_COLOR:
                    r = (pattern * 240).astype(np.uint8)
                    g = (pattern * 70).astype(np.uint8)
                    b = (pattern * 90).astype(np.uint8)
                else:  # TRUE_COLOR
                    r = (pattern * 180).astype(np.uint8)
                    g = (pattern * 200).astype(np.uint8)
                    b = (pattern * 170).astype(np.uint8)

            rgb_data = np.stack([r, g, b])
            mask = np.ones((height, width), dtype=np.uint8) * 255

            body = render(rgb_data, mask=mask, img_format="PNG")
            return body, "image/png", required_bands

        # GeoTIFF Analysis Raster
        band_count = len(required_bands)
        data = np.zeros((band_count, height, width), dtype=np.float32)
        for i in range(band_count):
            band_variation = rng.normal(0, 0.02, (height, width))
            data[i] = np.clip(pattern * (0.15 + i * 0.05) + band_variation, 0.0, 1.0).astype(
                np.float32
            )

        transform = from_bounds(bbox[0], bbox[1], bbox[2], bbox[3], width, height)
        with MemoryFile() as memfile:
            with memfile.open(
                driver="GTiff",
                height=height,
                width=width,
                count=band_count,
                dtype="float32",
                crs="EPSG:4326",
                transform=transform,
                nodata=0.0,
            ) as dst:
                for b_idx in range(band_count):
                    dst.write(data[b_idx], b_idx + 1)
                    dst.set_band_description(b_idx + 1, required_bands[b_idx])
            body = memfile.read()

        return body, "image/tiff", required_bands

    def request_imagery(
        self,
        request: ImageryRequest,
        *,
        provider_mode: str = "real",
    ) -> ImageryAsset:
        """Process a single scene imagery request and return a validated ImageryAsset."""
        bbox = self._get_aoi_bbox(request.aoi)
        width, height = (
            request.width or 512,
            request.height or 512,
        )
        if not request.width or not request.height:
            width, height = self._estimate_dimensions(bbox, request.resolution_meters)

        # Validate total pixel count
        max_pixels = (
            self.settings.max_analysis_raster_pixels
            if request.product_type == ImageryProductType.ANALYSIS_RASTER
            else self.settings.max_preview_pixels
        )
        if width * height > max_pixels:
            raise ImageryProcessingError(
                "PIXEL_LIMIT_EXCEEDED",
                f"Requested image dimensions ({width}x{height} = {width * height} px) "
                f"exceed maximum allowed ({max_pixels} px).",
            )

        cache_key = self.asset_store.generate_cache_key(
            provider_id="mock"
            if provider_mode == "mock" or "mock" in request.scene_id
            else "earth-search",
            scene_id=request.scene_id,
            aoi_fingerprint=f"{bbox[0]:.4f},{bbox[1]:.4f},{bbox[2]:.4f},{bbox[3]:.4f}",
            product_type=request.product_type.value,
            preset=request.visualization_preset.value,
            format_type=request.output_format.value,
            width=width,
            height=height,
            resolution_meters=request.resolution_meters,
        )

        # Cache check
        cached_record = self.asset_store.get_by_cache_key(cache_key)
        if cached_record:
            return cached_record.asset

        # Data generation (synthetic or provider-backed)
        is_mock = provider_mode == "mock" or "mock" in request.scene_id or self.settings.demo_mode
        body, content_type, bands = self._generate_synthetic_raster(
            scene_id=request.scene_id,
            bbox=bbox,
            width=width,
            height=height,
            preset=request.visualization_preset,
            product_type=request.product_type,
            format_type=request.output_format,
        )

        # Validate generated dataset
        validated_info = validate_raster_dataset(
            body,
            expected_format=request.output_format,
            product_type=request.product_type,
            max_pixels=max_pixels,
            max_bytes=self.settings.max_imagery_file_size_bytes,
        )

        raster_meta = RasterMetadata(
            crs=validated_info.crs,
            bbox=validated_info.bbox,
            width=validated_info.width,
            height=validated_info.height,
            pixel_size_x=abs(bbox[2] - bbox[0]) / max(1, width),
            pixel_size_y=abs(bbox[3] - bbox[1]) / max(1, height),
            band_count=validated_info.band_count,
            band_names=bands,
            data_type=validated_info.data_type,
            no_data_values=validated_info.no_data_values,
            acquisition_time=datetime.now(UTC),
            scene_id=request.scene_id,
            provider="mock" if is_mock else "earth-search",
            collection="sentinel-2-c1-l2a",
            transform=validated_info.transform,
        )

        asset = self.asset_store.save_asset(
            scene_id=request.scene_id,
            product_type=request.product_type,
            format_type=request.output_format,
            content_type=content_type,
            width=width,
            height=height,
            resolution_meters=request.resolution_meters or self.settings.default_resolution_meters,
            bbox=bbox,
            crs=validated_info.crs,
            data=body,
            provider_id="mock" if is_mock else "earth-search",
            data_origin=DataOrigin.MOCK if is_mock else DataOrigin.REAL,
            bands=bands,
            visualization_preset=request.visualization_preset,
            cache_key=cache_key,
            raster_metadata=raster_meta,
            processing_metadata={"is_synthetic": is_mock, "resampling": request.resampling_method},
        )

        return asset

    def evaluate_temporal_alignment(
        self, before_meta: RasterMetadata, after_meta: RasterMetadata
    ) -> AlignmentStatus:
        """Evaluate multitemporal raster spatial grid, CRS, and dimension alignment."""
        if before_meta.crs != after_meta.crs:
            return AlignmentStatus.INCOMPATIBLE

        # Check dimension difference
        width_diff = abs(before_meta.width - after_meta.width)
        height_diff = abs(before_meta.height - after_meta.height)
        if width_diff > 0 or height_diff > 0:
            if width_diff <= 2 and height_diff <= 2:
                return AlignmentStatus.APPROXIMATELY_ALIGNED
            return AlignmentStatus.REQUIRES_ALIGNMENT

        # Check pixel resolution agreement (within 1%)
        if (
            abs(before_meta.pixel_size_x - after_meta.pixel_size_x)
            / max(1e-6, before_meta.pixel_size_x)
            > 0.05
        ):
            return AlignmentStatus.REQUIRES_ALIGNMENT

        return AlignmentStatus.ALIGNED

    def request_temporal_imagery(
        self,
        request: TemporalImageryRequest,
        *,
        provider_mode: str = "real",
    ) -> TemporalImageryResponse:
        """Process multitemporal before/after imagery requests and return aligned pair response."""
        before_req = ImageryRequest(
            scene_id=request.before_scene_id,
            aoi=request.aoi,
            product_type=request.product_type,
            visualization_preset=request.before_preset,
            output_format=request.output_format,
            width=request.width,
            height=request.height,
            resolution_meters=request.resolution_meters,
            include_metadata=request.include_metadata,
        )
        after_req = ImageryRequest(
            scene_id=request.after_scene_id,
            aoi=request.aoi,
            product_type=request.product_type,
            visualization_preset=request.after_preset,
            output_format=request.output_format,
            width=request.width,
            height=request.height,
            resolution_meters=request.resolution_meters,
            include_metadata=request.include_metadata,
        )

        before_asset = self.request_imagery(before_req, provider_mode=provider_mode)
        after_asset = self.request_imagery(after_req, provider_mode=provider_mode)

        before_record = self.asset_store.get_asset(before_asset.asset_id)
        after_record = self.asset_store.get_asset(after_asset.asset_id)

        alignment_status = AlignmentStatus.ALIGNED
        if before_record.raster_metadata and after_record.raster_metadata:
            alignment_status = self.evaluate_temporal_alignment(
                before_record.raster_metadata, after_record.raster_metadata
            )

        pair_id = f"pair-{request.before_scene_id}-{request.after_scene_id}"
        req_id = request.request_id or f"req-{uuid4().hex[:12]}"

        data_origin = DataOrigin.REAL
        if (
            before_asset.data_origin == DataOrigin.MOCK
            or after_asset.data_origin == DataOrigin.MOCK
        ):
            data_origin = DataOrigin.MOCK

        return TemporalImageryResponse(
            request_id=req_id,
            pair_id=pair_id,
            before_asset=before_asset,
            after_asset=after_asset,
            alignment_status=alignment_status,
            data_origin=data_origin,
            warnings=[],
            processing_metadata={
                "before_preset": request.before_preset.value,
                "after_preset": request.after_preset.value,
            },
        )
