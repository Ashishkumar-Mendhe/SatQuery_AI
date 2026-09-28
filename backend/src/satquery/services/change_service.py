"""Service layer orchestrating pixel-level change detection workflows."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np
from rasterio.io import MemoryFile

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    EvidenceItem,
    EvidenceProvenance,
    EvidenceType,
    OverlayFeature,
    OverlayStyle,
    OverlayType,
    WarningSeverity,
)
from satquery.api.schemas.change import (
    CHANGE_SCHEMA_VERSION,
    ChangeDetectionRequest,
    ChangeDetectionResult,
    ChangeRegion,
)
from satquery.api.schemas.imagery import (
    ImageryFormat,
    ImageryProductType,
    RasterMetadata,
)
from satquery.api.schemas.preparation import RasterProvenance
from satquery.api.schemas.providers import DataOrigin
from satquery.core.config import Settings
from satquery.services.asset_store import AssetStore
from satquery.services.change_engine import ChangeCalculationError, ChangeEngine
from satquery.services.change_registry import ChangeRegistry
from satquery.services.spectral_registry import SpectralRegistry

logger = logging.getLogger(__name__)


class ChangeService:
    """Service orchestrating pixel-level change detection, metrics, and asset persistence."""

    def __init__(self, settings: Settings, asset_store: AssetStore | None = None) -> None:
        self.settings = settings
        self.asset_store = asset_store or AssetStore(
            storage_dir=settings.imagery_storage_dir,
            default_ttl_seconds=settings.imagery_asset_cache_ttl_seconds,
            max_bytes=settings.max_imagery_file_size_bytes * 10,
        )
        self._results_cache: dict[str, ChangeDetectionResult] = {}

    def calculate_change(self, request: ChangeDetectionRequest) -> ChangeDetectionResult:
        """Execute pixel-level change detection across a co-registered before/after pair."""
        start_time = time.perf_counter()
        now = datetime.now(UTC)

        # 1. Retrieve before & after prepared assets
        before_record = self.asset_store.get_asset(request.before_prepared_asset_id)
        after_record = self.asset_store.get_asset(request.after_prepared_asset_id)

        if before_record.asset.product_type != ImageryProductType.ANALYSIS_RASTER:
            raise ChangeCalculationError(
                "NON_ANALYSIS_RASTER",
                f"Before asset '{request.before_prepared_asset_id}' is not an analysis raster.",
                {"product_type": before_record.asset.product_type.value},
            )
        if after_record.asset.product_type != ImageryProductType.ANALYSIS_RASTER:
            raise ChangeCalculationError(
                "NON_ANALYSIS_RASTER",
                f"After asset '{request.after_prepared_asset_id}' is not an analysis raster.",
                {"product_type": after_record.asset.product_type.value},
            )

        before_bytes, _, _ = self.asset_store.get_asset_bytes(request.before_prepared_asset_id)
        after_bytes, _, _ = self.asset_store.get_asset_bytes(request.after_prepared_asset_id)

        # 2. Read rasters from memory
        with MemoryFile(before_bytes) as mem_b, MemoryFile(after_bytes) as mem_a:
            with mem_b.open() as src_b, mem_a.open() as src_a:
                b_data = src_b.read()
                a_data = src_a.read()
                b_crs = src_b.crs.to_string() if src_b.crs else "EPSG:4326"
                a_crs = src_a.crs.to_string() if src_a.crs else "EPSG:4326"
                b_transform = list(src_b.transform)[:6]
                a_transform = list(src_a.transform)[:6]
                b_bounds = (
                    src_b.bounds.left,
                    src_b.bounds.bottom,
                    src_b.bounds.right,
                    src_b.bounds.top,
                )
                b_bands = [src_b.descriptions[i] or f"Band {i + 1}" for i in range(src_b.count)]
                a_bands = [src_a.descriptions[i] or f"Band {i + 1}" for i in range(src_a.count)]
                b_nodata = src_b.nodata
                a_nodata = src_a.nodata

        if (
            not any(src_b.descriptions)
            and before_record.raster_metadata
            and before_record.raster_metadata.band_names
        ):
            b_bands = before_record.raster_metadata.band_names
        if (
            not any(src_a.descriptions)
            and after_record.raster_metadata
            and after_record.raster_metadata.band_names
        ):
            a_bands = after_record.raster_metadata.band_names

        # 3. Validate rigid spatial co-registration
        ChangeEngine.validate_grid_alignment(
            before_shape=(b_data.shape[1], b_data.shape[2]),
            after_shape=(a_data.shape[1], a_data.shape[2]),
            before_transform=b_transform,
            after_transform=a_transform,
            before_crs=b_crs,
            after_crs=a_crs,
        )

        # 4. Resolve band mappings
        b_band_map = SpectralRegistry.resolve_band_indices(
            available_band_names=b_bands,
            required_roles=["blue", "green", "red", "nir", "swir1", "swir2"],
        )
        a_band_map = SpectralRegistry.resolve_band_indices(
            available_band_names=a_bands,
            required_roles=["blue", "green", "red", "nir", "swir1", "swir2"],
        )

        # 5. Build mutual shared validity mask
        height, width = b_data.shape[1], b_data.shape[2]
        total_aoi_pixels = height * width
        b_valid = np.ones((height, width), dtype=bool)
        a_valid = np.ones((height, width), dtype=bool)

        for _role, idx in b_band_map.items():
            arr = b_data[idx]
            if b_nodata is not None:
                b_valid &= (arr != b_nodata) & ~np.isnan(arr)
            else:
                b_valid &= ~np.isnan(arr)

        for _role, idx in a_band_map.items():
            arr = a_data[idx]
            if a_nodata is not None:
                a_valid &= (arr != a_nodata) & ~np.isnan(arr)
            else:
                a_valid &= ~np.isnan(arr)

        shared_valid_mask = b_valid & a_valid
        shared_valid_count = int(np.sum(shared_valid_mask))

        if shared_valid_count == 0:
            raise ChangeCalculationError(
                "NO_SHARED_VALID_PIXELS",
                "No overlapping valid pixels found between before and after rasters.",
                {"total_pixels": total_aoi_pixels},
            )

        # 6. Compute pixel difference array
        method_def = ChangeRegistry.get_method_definition(request.method)
        diff_arr, calc_warnings = ChangeEngine.compute_difference_array(
            before_data=b_data,
            after_data=a_data,
            before_band_map=b_band_map,
            after_band_map=a_band_map,
            method=request.method,
        )

        # Update valid mask with finite differences
        shared_valid_mask &= np.isfinite(diff_arr)

        # 7. Apply thresholds & classify change
        classified_arr, pos_thresh, neg_thresh = ChangeEngine.apply_thresholds_and_classify(
            diff_arr=diff_arr,
            shared_valid_mask=shared_valid_mask,
            config=request.threshold_config,
            directionality=method_def.directionality,
        )

        # 8. Compute quantitative spatial metrics
        metrics = ChangeEngine.compute_change_metrics(
            classified_arr=classified_arr,
            shared_valid_mask=shared_valid_mask,
            total_aoi_pixels=total_aoi_pixels,
            transform=b_transform,
            crs=b_crs,
            pos_thresh_applied=pos_thresh,
            neg_thresh_applied=neg_thresh,
            strategy=request.threshold_config.strategy,
        )

        # 9. Vectorize candidate change regions
        regions: list[ChangeRegion] = []
        if request.generate_regions:
            regions = ChangeEngine.vectorize_change_regions(
                classified_arr=classified_arr,
                diff_arr=diff_arr,
                shared_valid_mask=shared_valid_mask,
                transform=b_transform,
                crs=b_crs,
                min_cluster_pixels=request.threshold_config.min_cluster_size_pixels,
                max_regions=request.max_regions,
            )

        # 10. Generate scientific GeoTIFF & Preview PNGs
        geotiff_bytes = ChangeEngine.generate_scientific_geotiff(
            diff_arr=diff_arr,
            shared_valid_mask=shared_valid_mask,
            crs=b_crs,
            transform=b_transform,
            method_name=request.method.value,
        )

        cont_png_bytes = ChangeEngine.generate_continuous_preview_png(
            diff_arr=diff_arr,
            shared_valid_mask=shared_valid_mask,
            color_ramp=method_def.default_color_ramp,
        )

        class_png_bytes = ChangeEngine.generate_classified_preview_png(
            classified_arr=classified_arr,
            shared_valid_mask=shared_valid_mask,
        )

        # 11. Persist derived assets in AssetStore
        diff_asset_id = f"ast-chg-{uuid4().hex[:12]}"
        preview_asset_id = f"ast-chgprv-{uuid4().hex[:12]}"
        class_preview_asset_id = f"ast-chgcls-{uuid4().hex[:12]}"
        result_id = f"res-chg-{uuid4().hex[:12]}"

        geotiff_metadata = RasterMetadata(
            crs=b_crs,
            bbox=b_bounds,
            width=width,
            height=height,
            pixel_size_x=abs(b_transform[0]),
            pixel_size_y=abs(b_transform[4]),
            band_count=1,
            band_names=[request.method.value],
            data_type="float32",
            no_data_values=[-9999.0],
            acquisition_time=now,
            scene_id=f"{before_record.asset.scene_id}_{after_record.asset.scene_id}",
            provider=before_record.asset.provider_id,
            collection="pixel_change_difference",
            transform=b_transform,
        )

        resolution_meters = float(before_record.asset.resolution_meters or abs(b_transform[0]))

        # Save continuous GeoTIFF
        self.asset_store.save_asset(
            asset_id=diff_asset_id,
            scene_id=f"{before_record.asset.scene_id}_{after_record.asset.scene_id}",
            product_type=ImageryProductType.ANALYSIS_RASTER,
            format_type=ImageryFormat.GEOTIFF,
            content_type="image/tiff",
            width=width,
            height=height,
            resolution_meters=resolution_meters,
            bbox=b_bounds,
            crs=b_crs,
            data=geotiff_bytes,
            data_origin=before_record.asset.data_origin,
            provider_id=before_record.asset.provider_id,
            bands=[request.method.value],
            ttl_seconds=self.settings.imagery_asset_cache_ttl_seconds,
            raster_metadata=geotiff_metadata,
        )

        # Save continuous PNG
        self.asset_store.save_asset(
            asset_id=preview_asset_id,
            scene_id=f"{before_record.asset.scene_id}_{after_record.asset.scene_id}",
            product_type=ImageryProductType.MAP_PREVIEW,
            format_type=ImageryFormat.PNG,
            content_type="image/png",
            width=width,
            height=height,
            resolution_meters=resolution_meters,
            bbox=b_bounds,
            crs=b_crs,
            data=cont_png_bytes,
            data_origin=before_record.asset.data_origin,
            provider_id=before_record.asset.provider_id,
            bands=["R", "G", "B"],
            ttl_seconds=self.settings.imagery_asset_cache_ttl_seconds,
            raster_metadata=geotiff_metadata,
        )

        # Save classified PNG
        self.asset_store.save_asset(
            asset_id=class_preview_asset_id,
            scene_id=f"{before_record.asset.scene_id}_{after_record.asset.scene_id}",
            product_type=ImageryProductType.MAP_PREVIEW,
            format_type=ImageryFormat.PNG,
            content_type="image/png",
            width=width,
            height=height,
            resolution_meters=resolution_meters,
            bbox=b_bounds,
            crs=b_crs,
            data=class_png_bytes,
            data_origin=before_record.asset.data_origin,
            provider_id=before_record.asset.provider_id,
            bands=["R", "G", "B"],
            ttl_seconds=self.settings.imagery_asset_cache_ttl_seconds,
            raster_metadata=geotiff_metadata,
        )

        # 12. Build Map Overlays
        cont_overlay: OverlayFeature | None = None
        class_overlay: OverlayFeature | None = None

        if request.generate_overlay:
            cont_overlay = OverlayFeature(
                id=f"ovl-chg-cont-{uuid4().hex[:8]}",
                type=OverlayType.RASTER,
                title=f"{method_def.display_name} (Continuous)",
                description=f"Diverging spectral difference ({method_def.default_color_ramp})",
                geometry=request.aoi,
                raster_url=f"/api/v1/imagery/assets/{preview_asset_id}",
                bounds=b_bounds,
                style=OverlayStyle(
                    fill_opacity=0.75,
                    color_ramp=[method_def.default_color_ramp],
                    min_value=method_def.expected_range[0],
                    max_value=method_def.expected_range[1],
                ),
                visible_by_default=True,
                evidence_ids=[f"evd-chg-{uuid4().hex[:8]}"],
            )

            class_overlay = OverlayFeature(
                id=f"ovl-chg-cls-{uuid4().hex[:8]}",
                type=OverlayType.RASTER,
                title=f"{method_def.display_name} (Classified)",
                description="Discrete Change Mask: Green = Spectral Gain, Red = Spectral Loss",
                geometry=request.aoi,
                raster_url=f"/api/v1/imagery/assets/{class_preview_asset_id}",
                bounds=b_bounds,
                style=OverlayStyle(
                    fill_opacity=0.85,
                    color_ramp=["#22c55e", "#ef4444"],
                    min_value=-1.0,
                    max_value=1.0,
                ),
                visible_by_default=False,
                evidence_ids=[f"evd-chg-{uuid4().hex[:8]}"],
            )

        # 13. Build Provenance & Evidence Items
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        provenance = RasterProvenance(
            pipeline_version=CHANGE_SCHEMA_VERSION,
            source_asset_ids=[request.before_prepared_asset_id, request.after_prepared_asset_id],
            source_scene_ids=[before_record.asset.scene_id, after_record.asset.scene_id],
            operations=[
                "grid_co_registration_validation",
                f"compute_{request.method.value}",
                "threshold_segmentation",
                "cluster_noise_filtering",
                "polygon_vectorization",
            ],
            parameters={
                "method": request.method.value,
                "formula": method_def.formula,
                "threshold_strategy": request.threshold_config.strategy.value,
                "positive_threshold": pos_thresh,
                "negative_threshold": neg_thresh,
                "min_cluster_size_pixels": request.threshold_config.min_cluster_size_pixels,
            },
            software="SatQuery Change Engine 1.0 (NumPy, Rasterio, Rio-Tiler)",
            started_at=now,
            completed_at=datetime.now(UTC),
            duration_milliseconds=duration_ms,
            data_origin=before_record.asset.data_origin,
        )

        evidence_items: list[EvidenceItem] = []
        if request.generate_evidence:
            evd_id = f"evd-chg-{uuid4().hex[:8]}"
            evidence_items.append(
                EvidenceItem(
                    id=evd_id,
                    type=EvidenceType.CHANGE_MEASUREMENT,
                    title=f"Measured {method_def.display_name} Metrics",
                    description=(
                        f"Calculated {method_def.display_name} across co-registered grids. "
                        f"Gain: {metrics.gain_area_km2} km² "
                        f"({metrics.pixel_counts.gain_percent}%), "
                        f"Loss: {metrics.loss_area_km2} km² "
                        f"({metrics.pixel_counts.loss_percent}%), "
                        f"Stable: {metrics.stable_area_km2} km² across "
                        f"{shared_valid_count} mutual valid pixels."
                    ),
                    source_scene_ids=[before_record.asset.scene_id, after_record.asset.scene_id],
                    geometry=request.aoi,
                    measurement=metrics.model_dump(),
                    observed_at=now,
                    confidence=0.90 if before_record.asset.data_origin != DataOrigin.MOCK else 0.80,
                    provenance=EvidenceProvenance(
                        computation=f"pixel_change_{request.method.value}",
                        algorithm_name=method_def.formula,
                        version=method_def.version,
                        processed_at=now,
                        parameters={
                            "strategy": request.threshold_config.strategy.value,
                            "pos_threshold": pos_thresh,
                            "neg_threshold": neg_thresh,
                        },
                    ),
                )
            )

        # 14. Check Warnings
        if before_record.asset.data_origin != after_record.asset.data_origin:
            calc_warnings.append(
                AnalysisWarning(
                    code="MIXED_DATA_ORIGIN",
                    severity=WarningSeverity.HIGH,
                    title="Mixed Data Origin",
                    message=(
                        "Before and After rasters originate from different sources (mock vs real)."
                    ),
                )
            )

        shared_valid_pct = (shared_valid_count / float(total_aoi_pixels)) * 100.0
        if shared_valid_pct < 50.0:
            calc_warnings.append(
                AnalysisWarning(
                    code="LOW_SHARED_VALID_COVERAGE",
                    severity=WarningSeverity.MEDIUM,
                    title="Low Shared Valid Coverage",
                    message=(
                        f"Only {shared_valid_pct:.1f}% of pixels in the AOI contain "
                        "mutual valid observations."
                    ),
                )
            )

        # 15. Calculate Confidence
        confidence_breakdown = ChangeEngine.calculate_confidence(
            shared_valid_percent=shared_valid_pct,
            is_mock=(before_record.asset.data_origin == DataOrigin.MOCK),
            definition=method_def,
        )

        result = ChangeDetectionResult(
            result_id=result_id,
            pair_id=request.prepared_pair_id,
            method=request.method,
            definition=method_def,
            before_scene_id=before_record.asset.scene_id,
            after_scene_id=after_record.asset.scene_id,
            before_asset_id=request.before_prepared_asset_id,
            after_asset_id=request.after_prepared_asset_id,
            difference_asset_id=diff_asset_id,
            preview_asset_id=preview_asset_id,
            classified_preview_asset_id=class_preview_asset_id,
            metrics=metrics,
            regions=regions,
            overlay=cont_overlay,
            classified_overlay=class_overlay,
            evidence=evidence_items,
            confidence_breakdown=confidence_breakdown,
            confidence=confidence_breakdown.overall,
            warnings=calc_warnings,
            provenance=provenance,
            data_origin=before_record.asset.data_origin,
            created_at=now,
        )

        self._results_cache[result_id] = result
        return result

    def get_result(self, result_id: str) -> ChangeDetectionResult:
        """Fetch cached change detection result by result ID."""
        if result_id not in self._results_cache:
            raise ChangeCalculationError(
                "RESULT_NOT_FOUND",
                f"Change detection result '{result_id}' not found in memory cache.",
                {"result_id": result_id},
            )
        return self._results_cache[result_id]
