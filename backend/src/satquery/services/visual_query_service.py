"""Visual Query Service orchestrating Image VQA, image manifests, AI inference, and spatial grounding."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    WarningCode,
    WarningSeverity,
)
from satquery.api.schemas.providers import DataOrigin, ProviderMode
from satquery.api.schemas.query import GenerationMode
from satquery.api.schemas.visual import (
    CoordinateStatus,
    GroundedVisualRegion,
    ImageInputRole,
    ImageManifest,
    MapGroundingStatus,
    SemanticStatus,
    VisualCapabilitiesResponse,
    VisualObservation,
    VisualOperation,
    VisualQueryRequest,
    VisualQueryResponse,
)
from satquery.core.config import Settings
from satquery.providers.ai.base import (
    AIProvider,
    AIProviderError,
    AIProviderNotConfiguredError,
    VisualQARequest,
    VisualQAResponse,
)
from satquery.providers.ai.mock import MockAIProvider
from satquery.services.asset_store import AssetStore
from satquery.services.change_service import ChangeService
from satquery.services.evidence_retriever import EvidenceRetriever
from satquery.services.fusion_service import FusionService
from satquery.services.spatial_grounding import (
    compute_evidence_overlap,
    normalize_provider_box,
    transform_box_to_wgs84,
)
from satquery.services.spectral_service import SpectralService
from satquery.services.visual_image_preparer import (
    VisualImagePreparationError,
    VisualImagePreparer,
)

logger = logging.getLogger(__name__)


class VisualQueryServiceError(Exception):
    """Exception raised for visual query execution failures."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class VisualQueryService:
    """Orchestrator for visual question answering, image manifest creation, and map grounding."""

    def __init__(
        self,
        settings: Settings,
        asset_store: AssetStore,
        ai_provider: AIProvider,
        evidence_retriever: EvidenceRetriever | None = None,
        change_service: ChangeService | None = None,
        spectral_service: SpectralService | None = None,
        fusion_service: FusionService | None = None,
    ) -> None:
        self.settings = settings
        self.asset_store = asset_store
        self.ai_provider = ai_provider
        self.preparer = VisualImagePreparer(asset_store)
        self.evidence_retriever = evidence_retriever or EvidenceRetriever(
            change_service=change_service,
            spectral_service=spectral_service,
            fusion_service=fusion_service,
        )
        self._manifests_cache: dict[str, ImageManifest] = {}

    def get_capabilities(self) -> VisualCapabilitiesResponse:
        return VisualCapabilitiesResponse(
            supported_operations=[
                VisualOperation.DESCRIBE,
                VisualOperation.LOCATE,
                VisualOperation.COMPARE,
            ],
            supports_bounding_boxes=True,
            supports_temporal_comparison=True,
            max_images_per_query=2,
            example_questions=[
                "Describe the visible land-cover patterns.",
                "Highlight the prominent water-like region.",
                "Where is the largest visible built-up cluster?",
                "What visual differences are apparent between these dates?",
                "Which visual observations match the measured change regions?",
            ],
        )

    def get_manifest(self, manifest_id: str) -> ImageManifest | None:
        return self._manifests_cache.get(manifest_id)

    async def ask_visual_query(self, request: VisualQueryRequest) -> VisualQueryResponse:
        """Process a natural language visual query on selected image(s)."""
        answer_id = f"vans-{uuid4().hex[:12]}"
        req_id = request.request_id or f"vreq-{uuid4().hex[:8]}"

        if not request.selected_image_asset_ids:
            raise VisualQueryServiceError(
                "NO_IMAGE_SELECTED", "Visual query requires at least 1 selected image asset."
            )

        if len(request.selected_image_asset_ids) > 2:
            raise VisualQueryServiceError(
                "TOO_MANY_IMAGES", "Visual query supports at most 2 images in the MVP."
            )

        # 1. Prepare Image Manifests & PNG bytes
        manifests: list[ImageManifest] = []
        image_payloads: list[bytes] = []
        overall_origin = DataOrigin.REAL

        for idx, asset_id in enumerate(request.selected_image_asset_ids):
            role = ImageInputRole.SINGLE
            if len(request.selected_image_asset_ids) == 2:
                role = ImageInputRole.BEFORE if idx == 0 else ImageInputRole.AFTER

            try:
                manifest, img_bytes = self.preparer.prepare_manifest_for_asset(
                    asset_id=asset_id,
                    role=role,
                    aoi_fingerprint=request.context_snapshot.fingerprint,
                )
                manifests.append(manifest)
                image_payloads.append(img_bytes)
                self._manifests_cache[manifest.manifest_id] = manifest

                if manifest.data_origin in (DataOrigin.MOCK, DataOrigin.FALLBACK):
                    overall_origin = manifest.data_origin
            except VisualImagePreparationError as exc:
                raise VisualQueryServiceError(exc.code, exc.message) from exc

        # 2. Gather Computed Evidence for Cross-Referencing
        evidence_bundle = await self.evidence_retriever.retrieve_for_snapshot(
            request.context_snapshot
        )
        evidence_regions = evidence_bundle.spatial_regions

        # 3. Invoke Vision-Language Provider or Fallback
        provider_req = VisualQARequest(
            question=request.question,
            manifests=manifests,
            image_payloads=image_payloads,
            operation=request.operation,
            existing_evidence_ids=request.existing_evidence_ids,
            language=request.locale or "en",
        )

        generation_mode = GenerationMode.LLM_EXPLANATION
        warnings: list[AnalysisWarning] = []
        limitations: list[str] = [
            "Model visual observations are unverified predictions and do not confirm physical ground truth.",
            "Visual appearance is subject to atmospheric stretching, sun angle, and sensor resolution limits.",
        ]
        provider_resp: VisualQAResponse | None = None

        try:
            if self.ai_provider.is_configured():
                provider_resp = await self.ai_provider.generate_visual_qa(provider_req)
                generation_mode = (
                    GenerationMode.MOCK_DEMO
                    if self.ai_provider.mode == ProviderMode.MOCK
                    else GenerationMode.LLM_EXPLANATION
                )
            else:
                # Deterministic Mock Fallback when unconfigured
                mock_provider = MockAIProvider(model_id="mock-vlm-fallback")
                provider_resp = await mock_provider.generate_visual_qa(provider_req)
                generation_mode = GenerationMode.DETERMINISTIC_SUMMARY
                warnings.append(
                    AnalysisWarning(
                        code=WarningCode.MOCK_DATA_USED,
                        title="Offline Reasoning Used",
                        message="AI provider is not configured. Visual query used deterministic offline inspection.",
                        severity=WarningSeverity.INFO,
                    )
                )
        except (AIProviderNotConfiguredError, AIProviderError, Exception) as exc:
            logger.warning(f"AI provider failed during visual QA, falling back to mock: {exc}")
            mock_provider = MockAIProvider(model_id="mock-vlm-fallback")
            provider_resp = await mock_provider.generate_visual_qa(provider_req)
            generation_mode = GenerationMode.DETERMINISTIC_SUMMARY
            warnings.append(
                AnalysisWarning(
                    code=WarningCode.MOCK_DATA_USED,
                    title="Live Provider Fallback",
                    message=f"Live AI provider unavailable ({exc}). Used deterministic offline fallback.",
                    severity=WarningSeverity.MEDIUM,
                )
            )

        if not provider_resp:
            raise VisualQueryServiceError(
                "VQA_FAILED", "Failed to obtain a visual response from provider."
            )

        # 4. Spatially Ground Predictions and Compute Evidence Overlaps
        manifest_by_id = {m.input_image_id: m for m in manifests}
        grounded_regions: list[GroundedVisualRegion] = []
        valid_observations: list[VisualObservation] = []

        for obs in provider_resp.observations:
            target_manifest: ImageManifest | None = manifest_by_id.get(obs.input_image_id) or (
                manifests[0] if manifests else None
            )
            if target_manifest is None:
                continue

            # Validate canonical box if present
            if obs.canonical_box:
                try:
                    norm_box = normalize_provider_box(
                        obs.canonical_box, provider_convention="canonical"
                    )
                    obs.canonical_box = norm_box

                    grounded = transform_box_to_wgs84(
                        canonical_box=norm_box,
                        manifest=target_manifest,
                        observation_id=obs.observation_id,
                    )

                    # Compute overlap with computed evidence
                    matched_ids, overlap_km2 = compute_evidence_overlap(grounded, evidence_regions)
                    if matched_ids:
                        grounded.matched_evidence_ids = matched_ids
                        grounded.overlap_area_km2 = overlap_km2
                        obs.associated_evidence_ids = matched_ids
                        obs.semantic_status = SemanticStatus.EVIDENCE_SUPPORTED

                    grounded_regions.append(grounded)
                    obs.coordinate_status = grounded.clipping_status

                    if not target_manifest.crs:
                        obs.map_grounding_status = MapGroundingStatus.IMAGE_ONLY_NO_GEOREFERENCE
                except Exception as exc:
                    logger.warning(f"Failed to ground observation box {obs.canonical_box}: {exc}")
                    obs.coordinate_status = CoordinateStatus.OUT_OF_BOUNDS
                    obs.map_grounding_status = MapGroundingStatus.UNAVAILABLE_OUT_OF_BOUNDS

            valid_observations.append(obs)

        # Merge warnings & limitations
        warnings.extend(provider_resp.warnings)
        limitations.extend(provider_resp.limitations)
        evidence_refs = list(
            set(
                [ref for obs in valid_observations for ref in obs.associated_evidence_ids]
                + request.existing_evidence_ids
            )
        )

        return VisualQueryResponse(
            answer_id=answer_id,
            request_id=req_id,
            context_fingerprint=request.context_snapshot.fingerprint,
            answer=provider_resp.answer,
            observations=valid_observations,
            manifests=manifests,
            grounded_regions=grounded_regions,
            evidence_references=evidence_refs,
            generation_mode=generation_mode,
            data_origin=overall_origin,
            warnings=warnings,
            limitations=list(dict.fromkeys(limitations)),  # Deduplicate
            provider_execution=provider_resp.execution_metadata,
            created_at=datetime.now(UTC),
        )
