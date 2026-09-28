"""Service layer orchestrating multimodal optical and SAR evidence fusion workflows."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any
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
from satquery.api.schemas.change import ChangeDetectionResult
from satquery.api.schemas.fusion import (
    FUSION_SCHEMA_VERSION,
    CompatibilityAssessment,
    CoveragePartitionPixelCounts,
    CoveragePartitions,
    FusionCapabilitiesResponse,
    FusionCompatibilityStatus,
    FusionQualityBreakdown,
    FusionRequest,
    FusionResult,
    FusionRuleDefinition,
    FusionRuleId,
    JointStateMetrics,
    JointStatePixelCounts,
    SARBackscatterCoefficient,
    SARCalibrationStatus,
    SARChangeEvidence,
    SAROrbitDirection,
    SARPolarization,
    SARPowerUnit,
    TemporalObservationRole,
)
from satquery.api.schemas.imagery import (
    ImageryFormat,
    ImageryProductType,
)
from satquery.api.schemas.preparation import (
    RasterProvenance,
)
from satquery.core.config import Settings
from satquery.services.asset_store import AssetStore
from satquery.services.change_service import ChangeService
from satquery.services.fusion_engine import FusionCalculationError, FusionEngine
from satquery.services.sar_engine import SAREngine

logger = logging.getLogger(__name__)


class FusionService:
    """Service orchestrating multimodal optical and SAR evidence fusion, validation, and persistence."""

    def __init__(
        self,
        settings: Settings,
        asset_store: AssetStore | None = None,
        change_service: ChangeService | None = None,
    ) -> None:
        self.settings = settings
        self.asset_store = asset_store or AssetStore(
            storage_dir=settings.imagery_storage_dir,
            default_ttl_seconds=settings.imagery_asset_cache_ttl_seconds,
            max_bytes=settings.max_imagery_file_size_bytes * 10,
        )
        self.change_service = change_service or ChangeService(
            settings=settings, asset_store=self.asset_store
        )
        self._results_cache: dict[str, FusionResult] = {}

    def get_capabilities(self) -> FusionCapabilitiesResponse:
        """Return supported fusion rules, polarizations, and coefficients."""
        return FusionCapabilitiesResponse(
            rules=FusionEngine.get_supported_rule_definitions(),
            supported_polarizations=[p.value for p in SARPolarization],
            supported_coefficients=[c.value for c in SARBackscatterCoefficient],
            version=FUSION_SCHEMA_VERSION,
        )

    def get_result(self, result_id: str) -> FusionResult | None:
        """Retrieve a cached fusion result by its ID."""
        return self._results_cache.get(result_id)

    def calculate_fusion(self, request: FusionRequest) -> FusionResult:
        """Execute deterministic multimodal optical and SAR evidence fusion."""
        start_time = time.perf_counter()
        now = datetime.now(UTC)
        result_id = f"fusion-{uuid4().hex[:12]}"

        rule_defs = {r.rule_id: r for r in FusionEngine.get_supported_rule_definitions()}
        selected_rule = rule_defs.get(
            request.rule_id,
            FusionRuleDefinition(
                rule_id=FusionRuleId.CO_OBSERVED_RESPONSE_CHANGE,
                name="Co-Observed Multimodal Response Change",
                version=FUSION_SCHEMA_VERSION,
                description="Co-occurrence of measured optical and SAR response changes.",
                supported_modalities=["Optical", "SAR"],
                disclaimer="Evidence-level fusion does not prove physical cause.",
            ),
        )

        # 1. Resolve Optical Change Evidence
        opt_result: ChangeDetectionResult | None = None
        if request.optical_change_result_id:
            opt_result = self.change_service.get_result(request.optical_change_result_id)

        # 2. Check if SAR is available or missing
        has_sar = bool(
            request.sar_prepared_pair_id
            or (request.sar_before_asset_id and request.sar_after_asset_id)
        )

        # 3. Handle Optical-Only Partial Case
        if not has_sar:
            if not request.allow_partial:
                raise FusionCalculationError(
                    "SINGLE_MODALITY_AVAILABLE",
                    "SAR evidence was not provided and partial results are not allowed.",
                )
            if opt_result is None:
                raise FusionCalculationError(
                    "INSUFFICIENT_EVIDENCE",
                    "Neither valid optical change result nor SAR evidence was provided.",
                )
            return self._build_optical_only_result(
                result_id=result_id,
                request=request,
                opt_result=opt_result,
                rule_def=selected_rule,
                now=now,
                duration_ms=(time.perf_counter() - start_time) * 1000.0,
            )

        # 4. Resolve SAR assets
        sar_before_asset_id = request.sar_before_asset_id
        sar_after_asset_id = request.sar_after_asset_id

        if not sar_before_asset_id or not sar_after_asset_id:
            raise FusionCalculationError(
                "INSUFFICIENT_EVIDENCE",
                "SAR before and after asset IDs must be provided for SAR differencing.",
            )

        sar_before_record = self.asset_store.get_asset(sar_before_asset_id)
        sar_after_record = self.asset_store.get_asset(sar_after_asset_id)

        # Verify Data Origin
        if opt_result is not None and opt_result.data_origin != sar_before_record.asset.data_origin:
            raise FusionCalculationError(
                "MIXED_DATA_ORIGIN",
                f"Cannot fuse real and synthetic observations (Optical origin: {opt_result.data_origin}, SAR origin: {sar_before_record.asset.data_origin}).",
            )

        # Read SAR bytes and data
        sar_before_bytes, _, _ = self.asset_store.get_asset_bytes(sar_before_asset_id)
        sar_after_bytes, _, _ = self.asset_store.get_asset_bytes(sar_after_asset_id)

        with MemoryFile(sar_before_bytes) as mem_sb, MemoryFile(sar_after_bytes) as mem_sa:
            with mem_sb.open() as src_sb, mem_sa.open() as src_sa:
                sar_b_arr = src_sb.read(1)
                sar_a_arr = src_sa.read(1)
                sar_crs = src_sb.crs.to_string() if src_sb.crs else "EPSG:4326"
                sar_transform = list(src_sb.transform)[:6]
                sar_res_x = abs(src_sb.transform.a)
                sar_res_y = abs(src_sb.transform.e)

        # Inspect SAR metadata from assets
        sar_unit = SARPowerUnit.DECIBELS  # Default prepared SAR
        sar_pol = SARPolarization.VV
        sar_coeff = SARBackscatterCoefficient.SIGMA0
        sar_calib = SARCalibrationStatus.TERRAIN_CORRECTED
        sar_orbit = SAROrbitDirection.UNKNOWN

        proc_meta = sar_before_record.asset.processing_metadata or {}
        if "unit" in proc_meta:
            sar_unit = SARPowerUnit(proc_meta["unit"])
        if "polarization" in proc_meta:
            sar_pol = SARPolarization(proc_meta["polarization"])
        if "coefficient" in proc_meta:
            sar_coeff = SARBackscatterCoefficient(proc_meta["coefficient"])
        if "calibration_status" in proc_meta:
            sar_calib = SARCalibrationStatus(proc_meta["calibration_status"])

        # Validate SAR metadata
        sar_warnings = SAREngine.validate_sar_metadata(
            before_polarization=sar_pol,
            after_polarization=sar_pol,
            before_unit=sar_unit,
            after_unit=sar_unit,
            before_coefficient=sar_coeff,
            after_coefficient=sar_coeff,
        )

        # Compute SAR difference
        sar_delta_db, sar_valid_mask = SAREngine.compute_sar_difference(
            before_arr=sar_b_arr,
            after_arr=sar_a_arr,
            unit=sar_unit,
        )

        sar_stats = SAREngine.compute_sar_statistics(
            delta_db=sar_delta_db,
            valid_mask=sar_valid_mask,
            pixel_size_x=sar_res_x,
            pixel_size_y=sar_res_y,
        )

        sar_before_time = sar_before_record.asset.created_at
        sar_after_time = sar_after_record.asset.created_at

        # 5. Build SAR Change Evidence
        sar_diff_asset_id = f"sar-diff-{uuid4().hex[:8]}"
        sar_evidence = SARChangeEvidence(
            before_scene_id=sar_before_record.asset.scene_id or "SAR-Scene-Before",
            after_scene_id=sar_after_record.asset.scene_id or "SAR-Scene-After",
            before_asset_id=sar_before_asset_id,
            after_asset_id=sar_after_asset_id,
            difference_asset_id=sar_diff_asset_id,
            polarization=sar_pol,
            coefficient=sar_coeff,
            unit=SARPowerUnit.DECIBELS,
            calibration_status=sar_calib,
            orbit_direction=sar_orbit,
            before_timestamp=sar_before_time,
            after_timestamp=sar_after_time,
            increase_threshold_db=request.sar_threshold_config.increase_threshold_db,
            decrease_threshold_db=request.sar_threshold_config.decrease_threshold_db,
            mean_delta_db=sar_stats["mean_delta_db"],
            min_delta_db=sar_stats["min_delta_db"],
            max_delta_db=sar_stats["max_delta_db"],
            std_delta_db=sar_stats["std_delta_db"],
            valid_area_km2=sar_stats["valid_area_km2"],
            data_origin=sar_before_record.asset.data_origin,
            warnings=[w.message for w in sar_warnings],
        )

        # 6. Assess Temporal & Spatial Compatibility
        if opt_result is not None:
            # Retrieve optical timestamps from provenance/assets
            opt_before_time = opt_result.created_at
            opt_after_time = opt_result.created_at

            # Extract actual acquisition timestamps if recorded in provenance
            if "before_timestamp" in opt_result.provenance.parameters:
                try:
                    opt_before_time = datetime.fromisoformat(
                        opt_result.provenance.parameters["before_timestamp"]
                    )
                except Exception:
                    pass
            if "after_timestamp" in opt_result.provenance.parameters:
                try:
                    opt_after_time = datetime.fromisoformat(
                        opt_result.provenance.parameters["after_timestamp"]
                    )
                except Exception:
                    pass

            timing, blocking_issues, timing_warnings = FusionEngine.assess_temporal_compatibility(
                optical_before=opt_before_time,
                optical_after=opt_after_time,
                sar_before=sar_before_time,
                sar_after=sar_after_time,
                temporal_tolerance_days=request.temporal_tolerance_days,
                event_timestamp=request.event_timestamp,
            )

            # Read optical difference array from asset store
            opt_diff_bytes, _, _ = self.asset_store.get_asset_bytes(opt_result.difference_asset_id)
            with MemoryFile(opt_diff_bytes) as mem_od:
                with mem_od.open() as src_od:
                    opt_diff_arr = src_od.read(1)
                    opt_res_x = abs(src_od.transform.a)
                    opt_res_y = abs(src_od.transform.e)
                    opt_nodata = src_od.nodata

            opt_valid_mask = np.isfinite(opt_diff_arr)
            if opt_nodata is not None:
                opt_valid_mask &= opt_diff_arr != opt_nodata

            # Coverage Partitioning
            coverage, masks = FusionEngine.compute_coverage_partitions(
                optical_valid_mask=opt_valid_mask,
                sar_valid_mask=sar_valid_mask,
                aoi_mask=None,
                pixel_size_x=sar_res_x,
                pixel_size_y=sar_res_y,
            )

            # Classify Joint Observations within J
            opt_pos_th = opt_result.definition.default_threshold_config.positive_threshold
            opt_neg_th = opt_result.definition.default_threshold_config.negative_threshold

            joint_metrics, state_grid = FusionEngine.classify_joint_observations(
                optical_diff=opt_diff_arr,
                sar_delta_db=sar_delta_db,
                joint_mask=masks["joint"],
                optical_pos_threshold=opt_pos_th,
                optical_neg_threshold=opt_neg_th,
                sar_increase_threshold_db=request.sar_threshold_config.increase_threshold_db,
                sar_decrease_threshold_db=request.sar_threshold_config.decrease_threshold_db,
                pixel_size_x=sar_res_x,
                pixel_size_y=sar_res_y,
            )

            # Vectorize regions
            regions = FusionEngine.vectorize_fusion_regions(
                state_grid=state_grid,
                optical_diff=opt_diff_arr,
                sar_delta_db=sar_delta_db,
                transform=sar_transform,
                pixel_size_x=sar_res_x,
                pixel_size_y=sar_res_y,
                min_cluster_size_pixels=request.sar_threshold_config.min_cluster_size_pixels,
                simplify_tolerance_meters=request.sar_threshold_config.simplify_tolerance_meters,
                max_regions=request.max_regions,
            )

            # Quality scoring
            quality = FusionEngine.compute_quality_breakdown(
                timing=timing,
                temporal_tolerance_days=request.temporal_tolerance_days,
                optical_res_m=(opt_res_x + opt_res_y) / 2.0,
                sar_res_m=(sar_res_x + sar_res_y) / 2.0,
                sar_calibration=sar_calib,
                coverage=coverage,
            )

            status = (
                FusionCompatibilityStatus.VALID
                if not blocking_issues and not timing_warnings
                else (
                    FusionCompatibilityStatus.COMPATIBLE_WITH_WARNINGS
                    if not blocking_issues
                    else FusionCompatibilityStatus.INCOMPATIBLE
                )
            )

            compatibility = CompatibilityAssessment(
                status=status,
                timing=timing,
                optical_resolution_meters=round((opt_res_x + opt_res_y) / 2.0, 2),
                sar_resolution_meters=round((sar_res_x + sar_res_y) / 2.0, 2),
                common_crs=sar_crs,
                blocking_issues=blocking_issues,
                warnings=timing_warnings + sar_warnings,
            )

            # Observations 4-role listing
            observations = [
                TemporalObservationRole(
                    role="optical_before",
                    scene_id=opt_result.before_scene_id,
                    acquisition_timestamp=opt_before_time,
                    prepared_asset_id=opt_result.before_asset_id,
                    sensor="Optical",
                    data_origin=opt_result.data_origin,
                ),
                TemporalObservationRole(
                    role="optical_after",
                    scene_id=opt_result.after_scene_id,
                    acquisition_timestamp=opt_after_time,
                    prepared_asset_id=opt_result.after_asset_id,
                    sensor="Optical",
                    data_origin=opt_result.data_origin,
                ),
                TemporalObservationRole(
                    role="sar_before",
                    scene_id=sar_before_record.asset.scene_id or "SAR-Before",
                    acquisition_timestamp=sar_before_time,
                    prepared_asset_id=sar_before_asset_id,
                    sensor="Sentinel-1 SAR",
                    data_origin=sar_before_record.asset.data_origin,
                ),
                TemporalObservationRole(
                    role="sar_after",
                    scene_id=sar_after_record.asset.scene_id or "SAR-After",
                    acquisition_timestamp=sar_after_time,
                    prepared_asset_id=sar_after_asset_id,
                    sensor="Sentinel-1 SAR",
                    data_origin=sar_after_record.asset.data_origin,
                ),
            ]

            # Render classified overlay PNG
            classified_png_bytes = FusionEngine.render_fusion_classified_png(state_grid=state_grid)
            preview_asset_id = f"fusion-preview-{uuid4().hex[:8]}"
            self.asset_store.save_asset(
                asset_id=preview_asset_id,
                scene_id="multimodal_fusion",
                product_type=ImageryProductType.MAP_PREVIEW,
                format_type=ImageryFormat.PNG,
                content_type="image/png",
                width=state_grid.shape[1],
                height=state_grid.shape[0],
                resolution_meters=sar_res_x,
                bbox=(0.0, 0.0, 1.0, 1.0),
                crs=sar_crs,
                data=classified_png_bytes,
                data_origin=opt_result.data_origin,
                provider_id="satquery_fusion",
                bands=["R", "G", "B", "A"],
                ttl_seconds=self.settings.imagery_asset_cache_ttl_seconds,
            )

            # Build Overlay Features
            classified_overlay = OverlayFeature(
                id=f"overlay-{result_id}",
                type=OverlayType.MASK,
                title="Multimodal Evidence Fusion Mask",
                description="Discrete 5-state joint classification overlay (Orange = Both, Green = Optical only, Blue = SAR only)",
                geometry=request.aoi,
                mask_url=f"/api/v1/fusion/results/{result_id}/overlay",
                bounds=(0.0, 0.0, 1.0, 1.0),
                style=OverlayStyle(
                    fill_opacity=0.85,
                    color_ramp=["#e66101", "#2ca25f", "#2b83ba", "#a0a0a0", "#af8dc3"],
                    min_value=1.0,
                    max_value=5.0,
                ),
                visible_by_default=True,
                evidence_ids=[f"evd-fusion-{uuid4().hex[:8]}"],
            )

            # Build Evidence Items
            evidence_items = [
                EvidenceItem(
                    id=f"ev-joint-response-{uuid4().hex[:8]}",
                    type=EvidenceType.CHANGE_MEASUREMENT,
                    title="Co-Observed Response Change",
                    description=(
                        f"Both optical and SAR sensors detected response changes across "
                        f"{joint_metrics.both_detect_change_area_km2:.4f} km2 "
                        f"({joint_metrics.both_detect_change_percent or 0.0:.1f}% of jointly observable area)."
                    ),
                    source_scene_ids=[o.scene_id for o in observations],
                    geometry=request.aoi,
                    measurement=joint_metrics.model_dump(),
                    observed_at=now,
                    confidence=quality.score,
                    provenance=EvidenceProvenance(
                        computation="multimodal_evidence_fusion",
                        algorithm_name="co_observed_response_change",
                        version=FUSION_SCHEMA_VERSION,
                        processed_at=now,
                        parameters={
                            "rule_id": request.rule_id.value,
                            "temporal_tolerance_days": request.temporal_tolerance_days,
                        },
                    ),
                ),
                EvidenceItem(
                    id=f"ev-coverage-{uuid4().hex[:8]}",
                    type=EvidenceType.SPECTRAL_MEASUREMENT,
                    title="Multimodal Coverage Partitioning",
                    description=(
                        f"Joint observations cover {coverage.jointly_observable_area_km2:.4f} km2 "
                        f"({coverage.joint_percent_of_aoi:.1f}% of AOI). Optical-only: {coverage.optical_only_area_km2:.4f} km2; "
                        f"SAR-only: {coverage.sar_only_area_km2:.4f} km2."
                    ),
                    source_scene_ids=[o.scene_id for o in observations],
                    geometry=request.aoi,
                    measurement=coverage.model_dump(),
                    observed_at=now,
                    confidence=1.0,
                    provenance=EvidenceProvenance(
                        computation="coverage_partitioning",
                        algorithm_name="exact_grid_masking",
                        version=FUSION_SCHEMA_VERSION,
                        processed_at=now,
                    ),
                ),
            ]

            result = FusionResult(
                result_id=result_id,
                rule_id=request.rule_id,
                rule_definition=selected_rule,
                compatibility=compatibility,
                coverage=coverage,
                joint_metrics=joint_metrics,
                regions=regions,
                observations=observations,
                sar_evidence=sar_evidence,
                optical_change_result_id=request.optical_change_result_id,
                difference_overlay=classified_overlay,
                classified_overlay=classified_overlay,
                evidence=evidence_items,
                quality=quality,
                warnings=timing_warnings + sar_warnings,
                blocking_issues=blocking_issues,
                provenance=RasterProvenance(
                    pipeline_version=FUSION_SCHEMA_VERSION,
                    source_asset_ids=[
                        opt_result.difference_asset_id,
                        sar_before_asset_id,
                        sar_after_asset_id,
                    ],
                    source_scene_ids=[o.scene_id for o in observations],
                    operations=[
                        "sar_radiometric_differencing",
                        "temporal_compatibility_assessment",
                        "coverage_partitioning",
                        "joint_state_classification",
                        "vector_region_extraction",
                    ],
                    parameters={
                        "rule_id": request.rule_id.value,
                        "temporal_tolerance_days": request.temporal_tolerance_days,
                        "sar_threshold_config": request.sar_threshold_config.model_dump(),
                    },
                    software="SatQuery Multimodal Fusion Engine 1.0",
                    started_at=now,
                    completed_at=datetime.now(UTC),
                    duration_milliseconds=(time.perf_counter() - start_time) * 1000.0,
                    data_origin=opt_result.data_origin,
                ),
                data_origin=opt_result.data_origin,
                created_at=now,
                interpretation_readiness=True,
            )

        else:
            # SAR-only case
            result = self._build_sar_only_result(
                result_id=result_id,
                request=request,
                sar_evidence=sar_evidence,
                sar_transform=sar_transform,
                sar_res_x=sar_res_x,
                sar_res_y=sar_res_y,
                sar_valid_mask=sar_valid_mask,
                sar_delta_db=sar_delta_db,
                rule_def=selected_rule,
                now=now,
                duration_ms=(time.perf_counter() - start_time) * 1000.0,
            )

        self._results_cache[result_id] = result
        return result

    def _build_optical_only_result(
        self,
        result_id: str,
        request: FusionRequest,
        opt_result: ChangeDetectionResult,
        rule_def: FusionRuleDefinition,
        now: datetime,
        duration_ms: float,
    ) -> FusionResult:
        """Construct an honest partial optical-only result when SAR is absent."""
        total_aoi_km2 = opt_result.metrics.shared_valid_area_km2
        cov_pixels = CoveragePartitionPixelCounts(
            total_aoi_pixels=opt_result.metrics.pixel_counts.total_aoi_pixels,
            jointly_observable_pixels=0,
            optical_only_pixels=opt_result.metrics.pixel_counts.shared_valid_pixels,
            sar_only_pixels=0,
            neither_pixels=opt_result.metrics.pixel_counts.total_aoi_pixels
            - opt_result.metrics.pixel_counts.shared_valid_pixels,
        )
        coverage = CoveragePartitions(
            total_aoi_area_km2=total_aoi_km2,
            jointly_observable_area_km2=0.0,
            optical_only_area_km2=total_aoi_km2,
            sar_only_area_km2=0.0,
            neither_area_km2=0.0,
            joint_percent_of_aoi=0.0,
            optical_only_percent_of_aoi=100.0,
            sar_only_percent_of_aoi=0.0,
            neither_percent_of_aoi=0.0,
            pixel_counts=cov_pixels,
        )
        joint_metrics = JointStateMetrics(
            joint_area_km2=0.0,
            both_detect_change_area_km2=0.0,
            optical_response_only_area_km2=0.0,
            sar_response_only_area_km2=0.0,
            neither_above_threshold_area_km2=0.0,
            uncertain_area_km2=0.0,
            both_detect_change_percent=None,
            optical_response_only_percent=None,
            sar_response_only_percent=None,
            neither_above_threshold_percent=None,
            uncertain_percent=None,
            pixel_counts=JointStatePixelCounts(
                both_detect_change_pixels=0,
                optical_response_only_pixels=0,
                sar_response_only_pixels=0,
                neither_above_threshold_pixels=0,
                uncertain_pixels=0,
            ),
        )
        compat = CompatibilityAssessment(
            status=FusionCompatibilityStatus.INSUFFICIENT_EVIDENCE,
            blocking_issues=["SAR evidence is missing; single-modality optical result available."],
            warnings=[
                AnalysisWarning(
                    code="SINGLE_MODALITY_OPTICAL",
                    severity=WarningSeverity.INFO,
                    title="Single Modality Optical",
                    message="Multimodal fusion executed in optical-only partial mode.",
                )
            ],
        )
        quality = FusionQualityBreakdown(
            score=opt_result.confidence * 0.7,
            temporal_alignment_factor=0.0,
            spatial_resolution_factor=1.0,
            calibration_certainty_factor=0.5,
            valid_coverage_factor=1.0,
            factors={"optical_confidence": opt_result.confidence},
            limitations=["SAR observations unavailable. Joint fusion cannot be evaluated."],
        )
        return FusionResult(
            result_id=result_id,
            rule_id=request.rule_id,
            rule_definition=rule_def,
            compatibility=compat,
            coverage=coverage,
            joint_metrics=joint_metrics,
            regions=[],
            observations=[],
            sar_evidence=None,
            optical_change_result_id=request.optical_change_result_id,
            difference_overlay=opt_result.overlay,
            classified_overlay=opt_result.classified_overlay,
            evidence=opt_result.evidence,
            quality=quality,
            warnings=compat.warnings,
            blocking_issues=compat.blocking_issues,
            provenance=RasterProvenance(
                pipeline_version=FUSION_SCHEMA_VERSION,
                source_asset_ids=[opt_result.difference_asset_id],
                source_scene_ids=[opt_result.before_scene_id, opt_result.after_scene_id],
                operations=["single_modality_optical_fallback"],
                software="SatQuery Multimodal Fusion Engine 1.0",
                started_at=now,
                completed_at=datetime.now(UTC),
                duration_milliseconds=duration_ms,
                data_origin=opt_result.data_origin,
            ),
            data_origin=opt_result.data_origin,
            created_at=now,
            interpretation_readiness=False,
        )

    def _build_sar_only_result(
        self,
        result_id: str,
        request: FusionRequest,
        sar_evidence: SARChangeEvidence,
        sar_transform: list[float],
        sar_res_x: float,
        sar_res_y: float,
        sar_valid_mask: np.ndarray[Any, Any],
        sar_delta_db: np.ndarray[Any, Any],
        rule_def: FusionRuleDefinition,
        now: datetime,
        duration_ms: float,
    ) -> FusionResult:
        """Construct an honest partial SAR-only result when optical change is absent."""
        valid_px = int(np.sum(sar_valid_mask))
        total_px = sar_valid_mask.size
        cov_pixels = CoveragePartitionPixelCounts(
            total_aoi_pixels=total_px,
            jointly_observable_pixels=0,
            optical_only_pixels=0,
            sar_only_pixels=valid_px,
            neither_pixels=total_px - valid_px,
        )
        coverage = CoveragePartitions(
            total_aoi_area_km2=sar_evidence.valid_area_km2,
            jointly_observable_area_km2=0.0,
            optical_only_area_km2=0.0,
            sar_only_area_km2=sar_evidence.valid_area_km2,
            neither_area_km2=0.0,
            joint_percent_of_aoi=0.0,
            optical_only_percent_of_aoi=0.0,
            sar_only_percent_of_aoi=100.0,
            neither_percent_of_aoi=0.0,
            pixel_counts=cov_pixels,
        )
        joint_metrics = JointStateMetrics(
            joint_area_km2=0.0,
            both_detect_change_area_km2=0.0,
            optical_response_only_area_km2=0.0,
            sar_response_only_area_km2=0.0,
            neither_above_threshold_area_km2=0.0,
            uncertain_area_km2=0.0,
            both_detect_change_percent=None,
            optical_response_only_percent=None,
            sar_response_only_percent=None,
            neither_above_threshold_percent=None,
            uncertain_percent=None,
            pixel_counts=JointStatePixelCounts(
                both_detect_change_pixels=0,
                optical_response_only_pixels=0,
                sar_response_only_pixels=0,
                neither_above_threshold_pixels=0,
                uncertain_pixels=0,
            ),
        )
        compat = CompatibilityAssessment(
            status=FusionCompatibilityStatus.INSUFFICIENT_EVIDENCE,
            blocking_issues=["Optical evidence is missing; single-modality SAR result available."],
            warnings=[
                AnalysisWarning(
                    code="SINGLE_MODALITY_SAR",
                    severity=WarningSeverity.INFO,
                    title="Single Modality SAR",
                    message="Multimodal fusion executed in SAR-only partial mode.",
                )
            ],
        )
        quality = FusionQualityBreakdown(
            score=0.75,
            temporal_alignment_factor=0.0,
            spatial_resolution_factor=1.0,
            calibration_certainty_factor=1.0,
            valid_coverage_factor=1.0,
            factors={"sar_valid_area": sar_evidence.valid_area_km2},
            limitations=["Optical observations unavailable. Joint fusion cannot be evaluated."],
        )
        return FusionResult(
            result_id=result_id,
            rule_id=request.rule_id,
            rule_definition=rule_def,
            compatibility=compat,
            coverage=coverage,
            joint_metrics=joint_metrics,
            regions=[],
            observations=[],
            sar_evidence=sar_evidence,
            optical_change_result_id=None,
            difference_overlay=None,
            classified_overlay=None,
            evidence=[],
            quality=quality,
            warnings=compat.warnings,
            blocking_issues=compat.blocking_issues,
            provenance=RasterProvenance(
                pipeline_version=FUSION_SCHEMA_VERSION,
                source_asset_ids=[sar_evidence.before_asset_id, sar_evidence.after_asset_id],
                source_scene_ids=[sar_evidence.before_scene_id, sar_evidence.after_scene_id],
                operations=["single_modality_sar_fallback"],
                software="SatQuery Multimodal Fusion Engine 1.0",
                started_at=now,
                completed_at=datetime.now(UTC),
                duration_milliseconds=duration_ms,
                data_origin=sar_evidence.data_origin,
            ),
            data_origin=sar_evidence.data_origin,
            created_at=now,
            interpretation_readiness=False,
        )
