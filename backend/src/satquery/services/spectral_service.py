"""Service layer orchestrating single-scene and temporal spectral index calculation jobs."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np
from rasterio.io import MemoryFile

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    EvidenceProvenance,
    OverlayFeature,
    OverlayStyle,
    OverlayType,
    WarningSeverity,
)
from satquery.api.schemas.imagery import (
    ImageryFormat,
    ImageryProductType,
    RasterMetadata,
)
from satquery.api.schemas.preparation import (
    RasterProvenance,
)
from satquery.api.schemas.providers import DataOrigin
from satquery.api.schemas.spectral import (
    SPECTRAL_SCHEMA_VERSION,
    SpectralEvidenceItem,
    SpectralIndexRequest,
    SpectralIndexResult,
    TemporalSpectralRequest,
    TemporalSpectralResult,
)
from satquery.core.config import Settings
from satquery.services.asset_store import AssetStore
from satquery.services.spectral_engine import (
    SpectralCalculationError,
    SpectralEngine,
)
from satquery.services.spectral_registry import (
    SpectralRegistry,
)

logger = logging.getLogger(__name__)


class SpectralService:
    """Orchestrates spectral index computations, statistical evidence, and asset persistence."""

    def __init__(self, settings: Settings, asset_store: AssetStore | None = None) -> None:
        self.settings = settings
        self.asset_store = asset_store or AssetStore(
            storage_dir=settings.imagery_storage_dir,
            default_ttl_seconds=settings.imagery_asset_cache_ttl_seconds,
            max_bytes=settings.max_imagery_file_size_bytes * 10,
        )
        self._results_cache: dict[str, SpectralIndexResult] = {}

    def calculate_single(self, request: SpectralIndexRequest) -> SpectralIndexResult:
        """Calculate a spectral index over a single prepared analysis raster."""
        start_time = time.perf_counter()
        now = datetime.now(UTC)

        # 1. Retrieve source prepared asset
        source_record = self.asset_store.get_asset(request.prepared_asset_id)
        if source_record.asset.product_type != ImageryProductType.ANALYSIS_RASTER:
            raise SpectralCalculationError(
                "NON_ANALYSIS_RASTER",
                f"Asset '{request.prepared_asset_id}' is not an analysis_raster.",
                {"product_type": source_record.asset.product_type.value},
            )

        source_bytes, _, _ = self.asset_store.get_asset_bytes(request.prepared_asset_id)

        # 2. Read dataset from memory
        with MemoryFile(source_bytes) as memfile:
            with memfile.open() as src:
                data = src.read()  # Shape (B, H, W)
                crs = src.crs.to_string() if src.crs else "EPSG:4326"
                transform = list(src.transform)[:6]
                bounds = (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)
                band_descriptions = [
                    src.descriptions[i] or f"Band {i + 1}" for i in range(src.count)
                ]
                nodata = src.nodata

        # Fallback band names if descriptions empty
        if not any(src.descriptions):
            if source_record.raster_metadata and source_record.raster_metadata.band_names:
                band_descriptions = source_record.raster_metadata.band_names

        # 3. Retrieve index definition and resolve band mappings
        index_def = SpectralRegistry.get_index_definition(request.index_name)
        band_map = SpectralRegistry.resolve_band_indices(
            available_band_names=band_descriptions,
            required_roles=index_def.required_bands,
        )

        # 4. Construct initial validity mask
        height, width = data.shape[1], data.shape[2]
        valid_mask = np.ones((height, width), dtype=bool)

        for _role, b_idx in band_map.items():
            band_arr = data[b_idx]
            if nodata is not None:
                valid_mask &= (band_arr != nodata) & ~np.isnan(band_arr)
            else:
                valid_mask &= ~np.isnan(band_arr)

        # 5. Compute floating-point spectral index
        index_arr, calc_warnings = SpectralEngine.calculate_index_array(
            data=data,
            band_map=band_map,
            index_name=request.index_name,
        )

        # 6. Extract summary statistics & histogram
        stats = SpectralEngine.compute_statistics(
            index_arr=index_arr,
            valid_mask=valid_mask,
            options=request.statistics_options,
        )

        # Check minimum valid coverage constraint
        if stats.valid_data_percent < request.mask_options.minimum_valid_data_percent:
            calc_warnings.append(
                AnalysisWarning(
                    code="LOW_VALID_DATA_COVERAGE",
                    severity=WarningSeverity.MEDIUM,
                    title="Low Valid Data Coverage",
                    message=(
                        f"Only {stats.valid_data_percent:.1f}% of pixels are valid in the AOI "
                        f"(threshold: {request.mask_options.minimum_valid_data_percent}%)."
                    ),
                )
            )

        # 7. Generate scientific GeoTIFF and preview PNG assets
        geotiff_bytes = SpectralEngine.generate_scientific_geotiff(
            index_arr=index_arr,
            valid_mask=valid_mask,
            crs=crs,
            transform=transform,
            index_name=request.index_name.value,
        )

        preview_png_bytes = SpectralEngine.generate_colormapped_png(
            index_arr=index_arr,
            valid_mask=valid_mask,
            color_ramp=index_def.default_color_ramp,
        )

        # 8. Persist derived assets in AssetStore
        output_asset_id = f"ast-spec-{uuid4().hex[:12]}"
        preview_asset_id = f"ast-specprv-{uuid4().hex[:12]}"
        result_id = f"res-spec-{uuid4().hex[:12]}"

        geotiff_metadata = RasterMetadata(
            crs=crs,
            bbox=bounds,
            width=width,
            height=height,
            pixel_size_x=abs(transform[0]),
            pixel_size_y=abs(transform[4]),
            band_count=1,
            band_names=[request.index_name.value],
            data_type="float32",
            no_data_values=[-9999.0],
            acquisition_time=source_record.raster_metadata.acquisition_time
            if source_record.raster_metadata
            else None,
            scene_id=request.scene_id,
            provider=source_record.asset.provider_id,
            collection="spectral_index",
            transform=transform,
        )

        resolution_meters = float(source_record.asset.resolution_meters or abs(transform[0]))

        self.asset_store.save_asset(
            asset_id=output_asset_id,
            scene_id=request.scene_id,
            product_type=ImageryProductType.ANALYSIS_RASTER,
            format_type=ImageryFormat.GEOTIFF,
            content_type="image/tiff",
            width=width,
            height=height,
            resolution_meters=resolution_meters,
            bbox=bounds,
            crs=crs,
            data=geotiff_bytes,
            data_origin=source_record.asset.data_origin,
            provider_id=source_record.asset.provider_id,
            bands=[request.index_name.value],
            ttl_seconds=self.settings.imagery_asset_cache_ttl_seconds,
            raster_metadata=geotiff_metadata,
        )

        self.asset_store.save_asset(
            asset_id=preview_asset_id,
            scene_id=request.scene_id,
            product_type=ImageryProductType.MAP_PREVIEW,
            format_type=ImageryFormat.PNG,
            content_type="image/png",
            width=width,
            height=height,
            resolution_meters=resolution_meters,
            bbox=bounds,
            crs=crs,
            data=preview_png_bytes,
            data_origin=source_record.asset.data_origin,
            provider_id=source_record.asset.provider_id,
            bands=["R", "G", "B"],
            ttl_seconds=self.settings.imagery_asset_cache_ttl_seconds,
            raster_metadata=geotiff_metadata,
        )

        # 9. Build Map Overlay Feature
        preview_url = f"/api/v1/imagery/assets/{preview_asset_id}"
        overlay_feature: OverlayFeature | None = None
        if request.generate_overlay:
            overlay_feature = OverlayFeature(
                id=f"ovl-{request.index_name.value}-{uuid4().hex[:8]}",
                type=OverlayType.RASTER,
                title=f"{index_def.display_name} Overlay",
                description=(
                    f"Colormapped {index_def.name.upper()} visualization "
                    f"({index_def.default_color_ramp})"
                ),
                geometry=request.aoi,
                raster_url=preview_url,
                bounds=bounds,
                style=OverlayStyle(
                    fill_opacity=0.75,
                    color_ramp=[index_def.default_color_ramp],
                    min_value=index_def.expected_range[0],
                    max_value=index_def.expected_range[1],
                ),
                visible_by_default=True,
                evidence_ids=[f"evd-spec-{uuid4().hex[:8]}"],
            )

        # 10. Build Provenance & Evidence Records
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        provenance = RasterProvenance(
            pipeline_version=SPECTRAL_SCHEMA_VERSION,
            source_asset_ids=[request.prepared_asset_id],
            source_scene_ids=[request.scene_id],
            operations=[
                "band_extraction",
                f"calculate_{request.index_name.value}",
                "no_data_masking",
                "statistics_extraction",
                "colormapped_rendering",
            ],
            parameters={
                "index_name": request.index_name.value,
                "formula": index_def.formula,
                "required_bands": index_def.required_bands,
                "resolved_bands": band_map,
                "color_ramp": index_def.default_color_ramp,
            },
            software="SatQuery Spectral Engine 1.0 (NumPy, Rasterio, Pillow)",
            started_at=now,
            completed_at=datetime.now(UTC),
            duration_milliseconds=duration_ms,
            data_origin=source_record.asset.data_origin,
        )

        evidence_items: list[SpectralEvidenceItem] = []
        evidence_ids: list[str] = []
        if request.generate_evidence:
            evd_id = f"evd-spec-{uuid4().hex[:8]}"
            evidence_ids.append(evd_id)
            evidence_items.append(
                SpectralEvidenceItem(
                    id=evd_id,
                    type="spectral_measurement",
                    title=f"Measured {index_def.name.upper()} Statistics",
                    description=(
                        f"Calculated {index_def.display_name} over AOI polygon. "
                        f"Mean: {stats.mean}, Min: {stats.minimum}, Max: {stats.maximum}, "
                        f"StdDev: {stats.standard_deviation} across "
                        f"{stats.valid_pixel_count} valid pixels."
                    ),
                    index_name=request.index_name,
                    measured_statistics=stats,
                    source_scene_ids=[request.scene_id],
                    source_asset_ids=[request.prepared_asset_id],
                    geometry=request.aoi,
                    result_asset_id=output_asset_id,
                    observed_at=source_record.raster_metadata.acquisition_time
                    if source_record.raster_metadata
                    else now,
                    confidence=0.90 if source_record.asset.data_origin != DataOrigin.MOCK else 0.80,
                    provenance=EvidenceProvenance(
                        computation=f"spectral_index_{request.index_name.value}",
                        algorithm_name=index_def.formula,
                        version=index_def.version,
                        processed_at=now,
                        parameters={"bands": band_map},
                    ),
                    limitations=[index_def.limitations],
                    data_origin=source_record.asset.data_origin,
                )
            )

        # 11. Compute Quality Confidence
        confidence = SpectralEngine.calculate_confidence(
            valid_data_percent=stats.valid_data_percent,
            has_cloud_mask=request.mask_options.apply_cloud_mask,
            required_bands_present=True,
            is_mock=(source_record.asset.data_origin == DataOrigin.MOCK),
        )

        # 12. Build Final Result
        observed_min = stats.minimum if stats.minimum is not None else index_def.expected_range[0]
        observed_max = stats.maximum if stats.maximum is not None else index_def.expected_range[1]

        result = SpectralIndexResult(
            result_id=result_id,
            index_name=request.index_name,
            definition=index_def,
            scene_id=request.scene_id,
            prepared_asset_id=request.prepared_asset_id,
            source_asset_ids=[request.prepared_asset_id],
            aoi_fingerprint=f"aoi-{abs(hash(str(request.aoi.coordinates))) % 1000000}",
            output_asset_id=output_asset_id,
            preview_asset_id=preview_asset_id,
            preview_url=preview_url,
            overlay=overlay_feature,
            statistics=stats,
            observed_range=(observed_min, observed_max),
            valid_data_percent=stats.valid_data_percent,
            evidence=evidence_items,
            evidence_ids=evidence_ids,
            confidence=confidence,
            warnings=calc_warnings,
            provenance=provenance,
            data_origin=source_record.asset.data_origin,
            created_at=now,
        )

        self._results_cache[result_id] = result
        return result

    def calculate_temporal(self, request: TemporalSpectralRequest) -> TemporalSpectralResult:
        """Calculate spectral index independently on Before and After prepared rasters."""
        now = datetime.now(UTC)

        # Calculate Before
        before_req = SpectralIndexRequest(
            request_id=f"{request.request_id or 'req'}-before",
            prepared_asset_id=request.before_prepared_asset_id,
            scene_id=f"scene-before-{request.before_prepared_asset_id}",
            aoi=request.aoi,
            index_name=request.index_name,
            mask_options=request.mask_options,
            statistics_options=request.statistics_options,
            generate_overlay=request.generate_overlays,
            generate_evidence=request.generate_evidence,
        )
        before_result = self.calculate_single(before_req)

        # Calculate After
        after_req = SpectralIndexRequest(
            request_id=f"{request.request_id or 'req'}-after",
            prepared_asset_id=request.after_prepared_asset_id,
            scene_id=f"scene-after-{request.after_prepared_asset_id}",
            aoi=request.aoi,
            index_name=request.index_name,
            mask_options=request.mask_options,
            statistics_options=request.statistics_options,
            generate_overlay=request.generate_overlays,
            generate_evidence=request.generate_evidence,
        )
        after_result = self.calculate_single(after_req)

        # Evaluate Comparability
        comparability_warnings: list[AnalysisWarning] = []
        if before_result.data_origin != after_result.data_origin:
            comparability_warnings.append(
                AnalysisWarning(
                    code="MIXED_DATA_ORIGIN",
                    severity=WarningSeverity.HIGH,
                    title="Mixed Data Origin",
                    message=(
                        "Before and After rasters originate from different sources (mock vs real)."
                    ),
                )
            )

        shared_valid_pct = round(
            min(before_result.valid_data_percent, after_result.valid_data_percent), 2
        )

        index_def = SpectralRegistry.get_index_definition(request.index_name)
        pair_result_id = f"res-spectemp-{uuid4().hex[:12]}"

        return TemporalSpectralResult(
            result_id=pair_result_id,
            pair_id=request.prepared_pair_id,
            index_name=request.index_name,
            definition=index_def,
            before_result=before_result,
            after_result=after_result,
            comparability_warnings=comparability_warnings,
            shared_valid_percent=shared_valid_pct,
            created_at=now,
        )

    def get_result(self, result_id: str) -> SpectralIndexResult:
        """Retrieve a cached spectral calculation result."""
        if result_id not in self._results_cache:
            raise SpectralCalculationError(
                "RESULT_NOT_FOUND",
                f"Spectral result '{result_id}' was not found or has expired.",
                {"result_id": result_id},
            )
        return self._results_cache[result_id]
