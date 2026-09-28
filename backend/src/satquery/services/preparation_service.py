"""Preparation service for orchestrating single-scene and temporal raster harmonization jobs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from satquery.api.schemas.imagery import (
    ImageryFormat,
    ImageryProductType,
    RasterMetadata,
)
from satquery.api.schemas.preparation import (
    PreparedRasterAsset,
    PreparedTemporalPair,
    RasterPreparationRequest,
    TemporalRasterPreparationRequest,
)
from satquery.core.config import Settings
from satquery.services.asset_store import AssetStore
from satquery.services.raster_harmonizer import (
    HarmonizationError,
    RasterHarmonizer,
)

logger = logging.getLogger(__name__)


class PreparationService:
    """Orchestrates raster preparation pipelines, input validation, and derived asset storage."""

    def __init__(self, settings: Settings, asset_store: AssetStore | None = None) -> None:
        self.settings = settings
        self.asset_store = asset_store or AssetStore(
            storage_dir=settings.imagery_storage_dir,
            default_ttl_seconds=settings.imagery_asset_cache_ttl_seconds,
            max_bytes=settings.max_imagery_file_size_bytes * 10,
        )

    def prepare_single_raster(self, request: RasterPreparationRequest) -> PreparedRasterAsset:
        """Prepare a single analysis raster: reproject, clip to AOI, and mask invalid pixels."""
        source_record = self.asset_store.get_asset(request.source_asset_id)
        if source_record.asset.product_type != ImageryProductType.ANALYSIS_RASTER:
            raise HarmonizationError(
                "INVALID_PRODUCT_TYPE",
                (
                    f"Source asset '{request.source_asset_id}' is a "
                    f"{source_record.asset.product_type.value}, not an analysis_raster."
                ),
            )

        source_bytes, _, _ = self.asset_store.get_asset_bytes(request.source_asset_id)

        harmonized = RasterHarmonizer.reproject_and_harmonize_single(
            source_bytes=source_bytes,
            source_asset_id=request.source_asset_id,
            scene_id=request.scene_id,
            aoi=request.aoi,
            target_crs=request.target_crs,
            target_resolution_meters=request.target_resolution_meters,
            resampling_method=request.resampling_method,
            selected_bands=request.selected_bands,
            clip_to_aoi=request.clip_to_aoi,
            mask_no_data=request.mask_no_data,
            data_origin=source_record.asset.data_origin,
        )

        # Store derived GeoTIFF analysis asset
        prep_asset_id = f"ast-prep-{uuid4().hex[:12]}"
        preview_asset_id = f"ast-prepprv-{uuid4().hex[:12]}"
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self.settings.imagery_asset_cache_ttl_seconds)

        geotiff_metadata = RasterMetadata(
            crs=harmonized.crs,
            bbox=harmonized.bbox,
            width=harmonized.width,
            height=harmonized.height,
            pixel_size_x=harmonized.pixel_size_x,
            pixel_size_y=harmonized.pixel_size_y,
            band_count=harmonized.band_count,
            band_names=harmonized.band_names,
            data_type=harmonized.data_type,
            no_data_values=harmonized.no_data_values,
            acquisition_time=source_record.raster_metadata.acquisition_time
            if source_record.raster_metadata
            else None,
            scene_id=request.scene_id,
            provider=source_record.asset.provider_id,
            collection="prepared_raster",
            transform=harmonized.transform,
        )

        # Store derived GeoTIFF asset
        self.asset_store.save_asset(
            asset_id=prep_asset_id,
            scene_id=request.scene_id,
            product_type=ImageryProductType.ANALYSIS_RASTER,
            format_type=ImageryFormat.GEOTIFF,
            content_type="image/tiff",
            width=harmonized.width,
            height=harmonized.height,
            resolution_meters=harmonized.resolution_meters,
            bbox=harmonized.bbox,
            crs=harmonized.crs,
            data=harmonized.geotiff_bytes,
            provider_id=source_record.asset.provider_id,
            data_origin=source_record.asset.data_origin,
            bands=harmonized.band_names,
            ttl_seconds=self.settings.imagery_asset_cache_ttl_seconds,
            raster_metadata=geotiff_metadata,
            warnings=harmonized.warnings,
        )

        # Store preview PNG asset
        self.asset_store.save_asset(
            asset_id=preview_asset_id,
            scene_id=request.scene_id,
            product_type=ImageryProductType.MAP_PREVIEW,
            format_type=ImageryFormat.PNG,
            content_type="image/png",
            width=harmonized.width,
            height=harmonized.height,
            resolution_meters=harmonized.resolution_meters,
            bbox=harmonized.bbox,
            crs=harmonized.crs,
            data=harmonized.preview_png_bytes,
            provider_id=source_record.asset.provider_id,
            data_origin=source_record.asset.data_origin,
            bands=["R", "G", "B"],
            ttl_seconds=self.settings.imagery_asset_cache_ttl_seconds,
        )

        return PreparedRasterAsset(
            asset_id=prep_asset_id,
            source_asset_ids=[request.source_asset_id],
            scene_ids=[request.scene_id],
            role="single",
            format=ImageryFormat.GEOTIFF,
            crs=harmonized.crs,
            bbox=harmonized.bbox,
            geometry=request.aoi,
            width=harmonized.width,
            height=harmonized.height,
            pixel_size_x=harmonized.pixel_size_x,
            pixel_size_y=harmonized.pixel_size_y,
            transform=harmonized.transform,
            band_count=harmonized.band_count,
            band_names=harmonized.band_names,
            data_type=harmonized.data_type,
            no_data_values=harmonized.no_data_values,
            valid_pixel_count=harmonized.valid_pixel_count,
            invalid_pixel_count=harmonized.invalid_pixel_count,
            valid_data_percent=harmonized.valid_data_percent,
            resolution_meters=harmonized.resolution_meters,
            resampling_method=request.resampling_method,
            clip_applied=request.clip_to_aoi,
            mask_applied=request.mask_no_data,
            created_at=now,
            expires_at=expires_at,
            data_origin=source_record.asset.data_origin,
            provenance=harmonized.provenance,
            warnings=harmonized.warnings,
            preview_url=f"/api/v1/imagery/assets/{preview_asset_id}",
            metadata_url=f"/api/v1/imagery/assets/{prep_asset_id}/metadata",
        )

    def prepare_temporal_pair(
        self, request: TemporalRasterPreparationRequest
    ) -> PreparedTemporalPair:
        """Prepare a multitemporal before/after pair onto an identical analysis grid."""
        rec_b = self.asset_store.get_asset(request.before_asset_id)
        rec_a = self.asset_store.get_asset(request.after_asset_id)

        if (
            rec_b.asset.product_type != ImageryProductType.ANALYSIS_RASTER
            or rec_a.asset.product_type != ImageryProductType.ANALYSIS_RASTER
        ):
            raise HarmonizationError(
                "INVALID_PRODUCT_TYPE", "Both before and after assets must be analysis_raster type."
            )

        bytes_b, _, _ = self.asset_store.get_asset_bytes(request.before_asset_id)
        bytes_a, _, _ = self.asset_store.get_asset_bytes(request.after_asset_id)

        res = RasterHarmonizer.harmonize_and_align_temporal_pair(
            before_bytes=bytes_b,
            after_bytes=bytes_a,
            before_asset_id=request.before_asset_id,
            after_asset_id=request.after_asset_id,
            before_scene_id=rec_b.asset.scene_id,
            after_scene_id=rec_a.asset.scene_id,
            aoi=request.aoi,
            strategy=request.strategy,
            target_crs=request.target_crs,
            target_resolution_meters=request.target_resolution_meters,
            optical_resampling=request.optical_resampling_method,
            sar_resampling=request.sar_resampling_method,
            mask_resampling=request.mask_resampling_method,
            use_common_intersection=request.use_common_intersection,
            before_origin=rec_b.asset.data_origin,
            after_origin=rec_a.asset.data_origin,
        )

        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self.settings.imagery_asset_cache_ttl_seconds)

        # Store derived before GeoTIFF and preview
        prep_id_b = f"ast-prep-{uuid4().hex[:12]}"
        prev_id_b = f"ast-prepprv-{uuid4().hex[:12]}"
        # Store derived after GeoTIFF and preview
        prep_id_a = f"ast-prep-{uuid4().hex[:12]}"
        prev_id_a = f"ast-prepprv-{uuid4().hex[:12]}"

        # Save Before Assets
        meta_b = RasterMetadata(
            crs=res.common_crs,
            bbox=res.common_bbox,
            width=res.common_width,
            height=res.common_height,
            pixel_size_x=res.common_resolution_meters,
            pixel_size_y=res.common_resolution_meters,
            band_count=res.before_result.band_count,
            band_names=res.before_result.band_names,
            data_type="float32",
            no_data_values=res.before_result.no_data_values,
            scene_id=rec_b.asset.scene_id,
            provider=rec_b.asset.provider_id,
            collection="prepared_raster",
            transform=res.common_transform,
        )
        self.asset_store.save_asset(
            asset_id=prep_id_b,
            scene_id=rec_b.asset.scene_id,
            product_type=ImageryProductType.ANALYSIS_RASTER,
            format_type=ImageryFormat.GEOTIFF,
            content_type="image/tiff",
            width=res.common_width,
            height=res.common_height,
            resolution_meters=res.common_resolution_meters,
            bbox=res.common_bbox,
            crs=res.common_crs,
            data=res.before_result.geotiff_bytes,
            provider_id=rec_b.asset.provider_id,
            data_origin=rec_b.asset.data_origin,
            bands=res.before_result.band_names,
            ttl_seconds=self.settings.imagery_asset_cache_ttl_seconds,
            raster_metadata=meta_b,
            warnings=res.before_result.warnings,
        )
        self.asset_store.save_asset(
            asset_id=prev_id_b,
            scene_id=rec_b.asset.scene_id,
            product_type=ImageryProductType.MAP_PREVIEW,
            format_type=ImageryFormat.PNG,
            content_type="image/png",
            width=res.common_width,
            height=res.common_height,
            resolution_meters=res.common_resolution_meters,
            bbox=res.common_bbox,
            crs=res.common_crs,
            data=res.before_result.preview_png_bytes,
            provider_id=rec_b.asset.provider_id,
            data_origin=rec_b.asset.data_origin,
            bands=["R", "G", "B"],
            ttl_seconds=self.settings.imagery_asset_cache_ttl_seconds,
        )

        # Save After Assets
        meta_a = RasterMetadata(
            crs=res.common_crs,
            bbox=res.common_bbox,
            width=res.common_width,
            height=res.common_height,
            pixel_size_x=res.common_resolution_meters,
            pixel_size_y=res.common_resolution_meters,
            band_count=res.after_result.band_count,
            band_names=res.after_result.band_names,
            data_type="float32",
            no_data_values=res.after_result.no_data_values,
            scene_id=rec_a.asset.scene_id,
            provider=rec_a.asset.provider_id,
            collection="prepared_raster",
            transform=res.common_transform,
        )
        self.asset_store.save_asset(
            asset_id=prep_id_a,
            scene_id=rec_a.asset.scene_id,
            product_type=ImageryProductType.ANALYSIS_RASTER,
            format_type=ImageryFormat.GEOTIFF,
            content_type="image/tiff",
            width=res.common_width,
            height=res.common_height,
            resolution_meters=res.common_resolution_meters,
            bbox=res.common_bbox,
            crs=res.common_crs,
            data=res.after_result.geotiff_bytes,
            provider_id=rec_a.asset.provider_id,
            data_origin=rec_a.asset.data_origin,
            bands=res.after_result.band_names,
            ttl_seconds=self.settings.imagery_asset_cache_ttl_seconds,
            raster_metadata=meta_a,
            warnings=res.after_result.warnings,
        )
        self.asset_store.save_asset(
            asset_id=prev_id_a,
            scene_id=rec_a.asset.scene_id,
            product_type=ImageryProductType.MAP_PREVIEW,
            format_type=ImageryFormat.PNG,
            content_type="image/png",
            width=res.common_width,
            height=res.common_height,
            resolution_meters=res.common_resolution_meters,
            bbox=res.common_bbox,
            crs=res.common_crs,
            data=res.after_result.preview_png_bytes,
            provider_id=rec_a.asset.provider_id,
            data_origin=rec_a.asset.data_origin,
            bands=["R", "G", "B"],
            ttl_seconds=self.settings.imagery_asset_cache_ttl_seconds,
        )

        prep_before = PreparedRasterAsset(
            asset_id=prep_id_b,
            source_asset_ids=[request.before_asset_id],
            scene_ids=[rec_b.asset.scene_id],
            role="before",
            format=ImageryFormat.GEOTIFF,
            crs=res.common_crs,
            bbox=res.common_bbox,
            geometry=request.aoi,
            width=res.common_width,
            height=res.common_height,
            pixel_size_x=res.common_resolution_meters,
            pixel_size_y=res.common_resolution_meters,
            transform=res.common_transform,
            band_count=res.before_result.band_count,
            band_names=res.before_result.band_names,
            data_type="float32",
            no_data_values=res.before_result.no_data_values,
            valid_pixel_count=res.before_result.valid_pixel_count,
            invalid_pixel_count=res.before_result.invalid_pixel_count,
            valid_data_percent=res.before_result.valid_data_percent,
            resolution_meters=res.common_resolution_meters,
            resampling_method=request.optical_resampling_method,
            clip_applied=True,
            mask_applied=True,
            created_at=now,
            expires_at=expires_at,
            data_origin=rec_b.asset.data_origin,
            provenance=res.before_result.provenance,
            warnings=res.before_result.warnings,
            preview_url=f"/api/v1/imagery/assets/{prev_id_b}",
            metadata_url=f"/api/v1/imagery/assets/{prep_id_b}/metadata",
        )

        prep_after = PreparedRasterAsset(
            asset_id=prep_id_a,
            source_asset_ids=[request.after_asset_id],
            scene_ids=[rec_a.asset.scene_id],
            role="after",
            format=ImageryFormat.GEOTIFF,
            crs=res.common_crs,
            bbox=res.common_bbox,
            geometry=request.aoi,
            width=res.common_width,
            height=res.common_height,
            pixel_size_x=res.common_resolution_meters,
            pixel_size_y=res.common_resolution_meters,
            transform=res.common_transform,
            band_count=res.after_result.band_count,
            band_names=res.after_result.band_names,
            data_type="float32",
            no_data_values=res.after_result.no_data_values,
            valid_pixel_count=res.after_result.valid_pixel_count,
            invalid_pixel_count=res.after_result.invalid_pixel_count,
            valid_data_percent=res.after_result.valid_data_percent,
            resolution_meters=res.common_resolution_meters,
            resampling_method=request.optical_resampling_method,
            clip_applied=True,
            mask_applied=True,
            created_at=now,
            expires_at=expires_at,
            data_origin=rec_a.asset.data_origin,
            provenance=res.after_result.provenance,
            warnings=res.after_result.warnings,
            preview_url=f"/api/v1/imagery/assets/{prev_id_a}",
            metadata_url=f"/api/v1/imagery/assets/{prep_id_a}/metadata",
        )

        return PreparedTemporalPair(
            preparation_id=f"prep-{uuid4().hex[:12]}",
            pair_id=request.pair_id,
            before_asset=prep_before,
            after_asset=prep_after,
            common_crs=res.common_crs,
            common_bbox=res.common_bbox,
            common_width=res.common_width,
            common_height=res.common_height,
            common_transform=res.common_transform,
            common_resolution_meters=res.common_resolution_meters,
            shared_valid_pixel_count=res.shared_valid_pixel_count,
            shared_valid_percent=res.shared_valid_percent,
            alignment_status=res.alignment_status,
            quality=res.quality,
            warnings=res.warnings,
            blocking_issues=res.blocking_issues,
            ready_for_analysis=res.ready_for_analysis,
            created_at=now,
            expires_at=expires_at,
            processing_metadata={
                "strategy": request.strategy.value,
                "use_common_intersection": request.use_common_intersection,
            },
        )
