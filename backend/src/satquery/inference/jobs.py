from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from satquery import __version__
from satquery.api.schemas.processing import (
    ArtifactAccess,
    ArtifactReference,
    JobProgress,
    PreparationRequest,
    ProcessingOptions,
    RequiredBand,
)
from satquery.api.schemas.vqa import (
    InferenceEvidenceRecord,
    InferenceJobStatus,
    InferenceQualityDecision,
    InferenceSubmissionRequest,
    ReferringGroundingRequest,
    UserSelectedPixelRegion,
    VqaCaptionRequest,
)
from satquery.db.processing import (
    ArtifactRecord,
    JobRecord,
    ProcessingPersistenceError,
    ProcessingPrincipal,
    ProcessingRepository,
)
from satquery.inference.chip import build_model_chip
from satquery.inference.grounding import GroundingError, ReferringGroundingService
from satquery.inference.service import InferenceError, SingleImageInferenceService
from satquery.processing.quality import QualityMaskService
from satquery.processing.raster import RasterInputService
from satquery.providers.catalog import CatalogueProvider, CatalogueProviderError
from satquery.storage import AtomicArtifactStore, StorageLimitError

INFERENCE_OPERATION_VERSION = "7d-v1"
INFERENCE_CODE_VERSION = f"satquery-{__version__}-phase-7d-v1"
INFERENCE_TOTAL_STAGES = 4
SUPPORTED_PROVIDER = "earth-search"
SUPPORTED_COLLECTION = "sentinel-2-c1-l2a"


class InferenceJobError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class InferenceJobNotFoundError(RuntimeError):
    pass


class InferenceResultUnavailableError(RuntimeError):
    pass


class InferenceJobService:
    """Durable, owner-scoped orchestration of trusted extraction and bounded inference."""

    def __init__(
        self,
        repository: ProcessingRepository,
        provider: CatalogueProvider,
        artifact_store: AtomicArtifactStore,
        *,
        answer_service: SingleImageInferenceService | None,
        grounding_service: ReferringGroundingService | None,
        max_concurrency: int = 1,
        timeout_seconds: float = 360.0,
        max_pixels: int = 4_000_000,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._artifact_store = artifact_store
        self._answer_service = answer_service
        self._grounding_service = grounding_service
        self._slots = asyncio.Semaphore(max_concurrency)
        self._timeout_seconds = timeout_seconds
        self._max_pixels = min(max_pixels, 4_000_000)
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    async def start(self) -> None:
        await self._repository.reconcile_interrupted(datetime.now(UTC))
        for job in await self._repository.queued_jobs("infer_single_image"):
            self._dispatch(job.job_id)

    async def stop(self) -> None:
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def submit(
        self,
        principal: ProcessingPrincipal,
        request: InferenceSubmissionRequest,
        *,
        idempotency_key: str,
    ) -> JobRecord:
        if (
            request.scene.provider != SUPPORTED_PROVIDER
            or request.scene.collection != SUPPORTED_COLLECTION
        ):
            raise InferenceJobError(
                "UNSUPPORTED_SCENE",
                "Single-image inference supports Earth Search Sentinel-2 L2A scenes only.",
            )
        try:
            scene = await self._provider.item(request.scene.collection, request.scene.item)
        except CatalogueProviderError as exc:
            raise InferenceJobError(
                "STALE_SCENE_REFERENCE",
                "The selected scene reference is no longer available from the trusted provider.",
            ) from exc
        if (
            scene.provider.id != request.scene.provider
            or scene.provider_asset_id != request.scene.item
        ):
            raise InferenceJobError("STALE_SCENE_REFERENCE", "The selected scene identity changed.")
        source_evidence = [
            {
                "scene": request.scene.model_dump(mode="json"),
                "provider_asset_version": scene.provider_asset_version,
                "acquisition": scene.acquisition.model_dump(mode="json"),
                "processing_level": scene.processing_level,
            }
        ]
        canonical = request.model_dump(mode="json")
        request_digest = _digest(canonical)
        cache_key = _digest(
            {
                "owner_id": str(principal.owner_id),
                "access_scope": principal.access_scope,
                "request": canonical,
                "source_evidence": source_evidence,
                "code_version": INFERENCE_CODE_VERSION,
                "operation_version": INFERENCE_OPERATION_VERSION,
                "answer_model": (
                    self._answer_service.cache_identity
                    if self._answer_service is not None
                    else None
                ),
            }
        )
        cached = await self._repository.find_successful_cache(
            principal, cache_key, "infer_single_image"
        )
        if cached is not None and await self._complete(cached, principal):
            return cached
        record = JobRecord(
            job_id=uuid4(),
            owner_id=principal.owner_id,
            access_scope=principal.access_scope,
            operation="infer_single_image",
            operation_version=INFERENCE_OPERATION_VERSION,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            cache_key=cache_key,
            request_json=canonical,
            source_evidence_json=source_evidence,
            state="queued",
            current_stage=None,
            completed_units=None,
            total_units=None,
            attempt=0,
            submitted_at=datetime.now(UTC),
            started_at=None,
            finished_at=None,
            error_code=None,
            safe_error_message=None,
            quality_report_json=None,
            manifest_json=None,
        )
        stored, created = await self._repository.submit(record=record)
        if created:
            self._dispatch(stored.job_id)
        return stored

    async def status(self, principal: ProcessingPrincipal, job_id: UUID) -> InferenceJobStatus:
        record = await self._repository.get_job(principal, job_id)
        if record is None or record.operation != "infer_single_image":
            raise InferenceJobNotFoundError
        artifacts = await self._artifact_references(principal, record)
        result = None
        if record.state == "succeeded" and record.manifest_json is not None:
            evidence = record.manifest_json.get("evidence")
            if isinstance(evidence, dict):
                result = InferenceEvidenceRecord.model_validate(evidence)
        request = InferenceSubmissionRequest.model_validate(record.request_json)
        progress = None
        if record.completed_units is not None and record.total_units is not None:
            progress = JobProgress(
                completed_units=record.completed_units,
                total_units=record.total_units,
                units="stages",
            )
        return InferenceJobStatus(
            job_id=record.job_id,
            request_id=request.request_id,
            operation=request.operation,
            state=record.state,
            submitted_at=record.submitted_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            attempt=record.attempt,
            current_stage=record.current_stage,
            progress=progress,
            artifacts=list(artifacts),
            result=result,
            error_code=record.error_code,
            safe_error_message=record.safe_error_message,
        )

    async def result(self, principal: ProcessingPrincipal, job_id: UUID) -> InferenceEvidenceRecord:
        status = await self.status(principal, job_id)
        if status.state != "succeeded" or status.result is None:
            raise InferenceResultUnavailableError
        return status.result

    async def cancel(self, principal: ProcessingPrincipal, job_id: UUID) -> InferenceJobStatus:
        existing = await self._repository.get_job(principal, job_id)
        if existing is None or existing.operation != "infer_single_image":
            raise InferenceJobNotFoundError
        record = await self._repository.request_cancel(principal, job_id, datetime.now(UTC))
        if record is None or record.operation != "infer_single_image":
            raise InferenceJobNotFoundError
        return await self.status(principal, job_id)

    async def artifact(
        self, principal: ProcessingPrincipal, artifact_id: UUID
    ) -> tuple[ArtifactRecord, Any]:
        record = await self._repository.get_artifact(principal, artifact_id)
        if (
            record is None
            or record.kind not in {"inference_evidence", "inference_chip"}
            or not self._artifact_store.exists(record.storage_key)
        ):
            raise InferenceJobNotFoundError
        return record, self._artifact_store.open(record.storage_key)

    def _dispatch(self, job_id: UUID) -> None:
        existing = self._tasks.get(job_id)
        if existing is not None and not existing.done():
            return
        task = asyncio.create_task(self._run(job_id), name=f"inference-{job_id}")
        self._tasks[job_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(job_id, None))

    async def _run(self, job_id: UUID) -> None:
        async with self._slots:
            try:
                record = next(
                    (
                        job
                        for job in await self._repository.queued_jobs("infer_single_image")
                        if job.job_id == job_id
                    ),
                    None,
                )
                if record is None or not await self._repository.start_job(
                    job_id, datetime.now(UTC), INFERENCE_TOTAL_STAGES
                ):
                    return
                async with asyncio.timeout(self._timeout_seconds):
                    await self._execute(
                        record, InferenceSubmissionRequest.model_validate(record.request_json)
                    )
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                await self._fail(job_id, "inference_timeout", "Inference exceeded its time limit.")
            except (InferenceError, GroundingError, InferenceJobError) as exc:
                await self._fail(job_id, getattr(exc, "code", "inference_failed"), str(exc))
            except (ProcessingPersistenceError, StorageLimitError) as exc:
                await self._fail(job_id, "dependency_unavailable", str(exc))
            except Exception:
                await self._fail(
                    job_id,
                    "inference_failed",
                    "Inference failed while processing the selected scientific input.",
                )

    async def _execute(self, record: JobRecord, request: InferenceSubmissionRequest) -> None:
        preparation = _preparation_request(request, self._max_pixels)
        catalogue_scene = await self._provider.item(request.scene.collection, request.scene.item)
        raster = await RasterInputService(self._provider, max_pixels=self._max_pixels).extract(
            preparation
        )
        await self._stage(record.job_id, "scientific_raster_extracted", 1)
        await self._cancelled(record.job_id)
        quality = await QualityMaskService(self._provider).decode(raster)
        chip = build_model_chip(
            raster=raster,
            quality=quality,
            request=preparation,
            catalogue_scene=catalogue_scene,
            preparation_job_id=record.job_id,
        )
        await self._stage(record.job_id, "quality_evaluated_and_chip_built", 2)
        await self._cancelled(record.job_id)
        decision = _quality_decision(
            chip.contract.phase6_quality.readiness.state,
            chip.contract.phase6_quality.readiness.quality_check_ids,
        )
        answer = None
        grounding = None
        execution_state: str
        execution_reason: str | None = None
        if decision.state in {"blocked", "unknown"}:
            execution_state = decision.state
            execution_reason = decision.reason
        elif request.operation == "referring_grounding":
            if self._grounding_service is None:
                execution_state = "unavailable"
                execution_reason = "The configured grounding model is unavailable."
            else:
                grounding_request = ReferringGroundingRequest(
                    request_id=request.request_id,
                    image_chip=chip.contract,
                    referring_text=request.text,
                    selected_region=_selected_region(
                        request, chip.contract.chip_id, chip.contract.width, chip.contract.height
                    ),
                    requested_geometry=request.requested_geometry,
                )
                grounding = await self._grounding_service.locate(grounding_request, chip)
                if grounding.status == "failed_inference":
                    raise GroundingError(
                        "GROUNDING_INFERENCE_FAILED",
                        grounding.reason or "The grounding model failed.",
                    )
                if grounding.status in {"unavailable", "unsupported_geometry"}:
                    execution_state = "unavailable"
                    execution_reason = grounding.reason
                else:
                    execution_state = "completed"
        elif self._answer_service is None:
            execution_state = "unavailable"
            execution_reason = "The configured vision-language model is unavailable."
        else:
            model_request = VqaCaptionRequest(
                request_id=request.request_id,
                task=request.operation,
                image_chip=chip.contract,
                question=request.text,
            )
            answer = (
                await self._answer_service.answer_question(model_request, chip)
                if request.operation == "visual_question_answering"
                else await self._answer_service.caption(model_request, chip)
            )
            execution_state = "completed"
        await self._stage(record.job_id, "inference_completed", 3)
        await self._cancelled(record.job_id)
        chip_artifact_id = uuid4()
        stored_chip = self._artifact_store.write_bytes(
            record.job_id,
            chip_artifact_id,
            ".png",
            chip.content,
            bytes_already_written=0,
        )
        chip_artifact = ArtifactRecord(
            artifact_id=chip_artifact_id,
            job_id=record.job_id,
            owner_id=record.owner_id,
            kind="inference_chip",
            media_type="image/png",
            storage_key=stored_chip.storage_key,
            checksum_sha256=stored_chip.checksum_sha256,
            byte_size=stored_chip.byte_size,
            state="available",
            created_at=datetime.now(UTC),
        )
        chip_reference = ArtifactReference(
            artifact_id=chip_artifact_id,
            kind="inference_chip",
            media_type="image/png",
            checksum_sha256=stored_chip.checksum_sha256,
            byte_size=stored_chip.byte_size,
            access=ArtifactAccess(state="available"),
        )
        evidence = InferenceEvidenceRecord(
            request=request,
            source_chip=chip.contract,
            input_chip_artifact=chip_reference,
            quality_decision=decision,
            execution_state=execution_state,
            execution_reason=execution_reason,
            answer=answer,
            grounding=grounding,
        )
        payload = json.dumps(
            evidence.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
        artifact_id = uuid4()
        stored = self._artifact_store.write_bytes(
            record.job_id,
            artifact_id,
            ".json",
            payload,
            bytes_already_written=stored_chip.byte_size,
        )
        artifact = ArtifactRecord(
            artifact_id=artifact_id,
            job_id=record.job_id,
            owner_id=record.owner_id,
            kind="inference_evidence",
            media_type="application/json",
            storage_key=stored.storage_key,
            checksum_sha256=stored.checksum_sha256,
            byte_size=stored.byte_size,
            state="available",
            created_at=datetime.now(UTC),
        )
        await self._stage(record.job_id, "evidence_committed", 4)
        await self._repository.succeed_job(
            record.job_id,
            artifacts=(chip_artifact, artifact),
            quality_report=chip.contract.phase6_quality.model_dump(mode="json"),
            manifest={
                "artifact_ids": [str(chip_artifact_id), str(artifact_id)],
                "evidence": evidence.model_dump(mode="json"),
            },
            occurred_at=datetime.now(UTC),
        )

    async def _stage(self, job_id: UUID, stage: str, completed: int) -> None:
        await self._repository.update_progress(
            job_id, stage=stage, completed_units=completed, occurred_at=datetime.now(UTC)
        )

    async def _cancelled(self, job_id: UUID) -> None:
        if await self._repository.cancellation_requested(job_id):
            await self._repository.mark_cancelled(job_id, datetime.now(UTC))
            raise InferenceJobError("job_cancelled", "The inference job was cancelled.")

    async def _fail(self, job_id: UUID, code: str, message: str) -> None:
        if code == "job_cancelled":
            return
        try:
            await self._repository.fail_job(
                job_id,
                code=code[:160].lower(),
                message=message[:1000],
                occurred_at=datetime.now(UTC),
            )
        except ProcessingPersistenceError:
            pass

    async def _artifact_references(
        self, principal: ProcessingPrincipal, record: JobRecord
    ) -> tuple[ArtifactReference, ...]:
        if record.state != "succeeded":
            return ()
        artifacts = await self._repository.artifacts_for_job(principal, record.job_id)
        if (
            len(artifacts) != 2
            or {item.kind for item in artifacts} != {"inference_chip", "inference_evidence"}
            or any(not self._artifact_store.exists(item.storage_key) for item in artifacts)
        ):
            raise ProcessingPersistenceError("Committed inference evidence is incomplete.")
        return tuple(
            ArtifactReference(
                artifact_id=item.artifact_id,
                kind=item.kind,
                media_type=item.media_type,
                checksum_sha256=item.checksum_sha256,
                byte_size=item.byte_size,
                access=ArtifactAccess(state="available"),
            )
            for item in artifacts
        )

    async def _complete(self, record: JobRecord, principal: ProcessingPrincipal) -> bool:
        try:
            return bool(await self._artifact_references(principal, record))
        except ProcessingPersistenceError:
            return False


def _preparation_request(
    request: InferenceSubmissionRequest, max_pixels: int
) -> PreparationRequest:
    return PreparationRequest(
        scenes=[request.scene],
        aoi=request.aoi,
        required_bands=[
            RequiredBand(role="red", common_name="red"),
            RequiredBand(role="green", common_name="green"),
            RequiredBand(role="blue", common_name="blue"),
        ],
        intended_task="optical_single_scene",
        processing_profile="sentinel-2-l2a-surface-reflectance-v1",
        options=ProcessingOptions(
            grid_policy="source_aligned",
            target_resolution_metres=10.0,
            continuous_resampling="nearest",
            max_output_pixels=max_pixels,
        ),
    )


def _quality_decision(state: str, check_ids: list[str]) -> InferenceQualityDecision:
    if state == "ready":
        return InferenceQualityDecision(
            state="proceed",
            reason="All required Phase 6 VQA input checks passed.",
            required_check_ids=check_ids,
        )
    if state == "limited":
        return InferenceQualityDecision(
            state="proceed_with_warning",
            reason="Inference may proceed, but the Phase 6 input is explicitly limited.",
            required_check_ids=check_ids,
        )
    if state == "not_ready":
        return InferenceQualityDecision(
            state="blocked",
            reason="A required Phase 6 VQA input check failed.",
            required_check_ids=check_ids,
        )
    return InferenceQualityDecision(
        state="unknown",
        reason="Required Phase 6 VQA quality evidence is unknown.",
        required_check_ids=check_ids,
    )


def _selected_region(
    request: InferenceSubmissionRequest, chip_id: UUID, width: int, height: int
) -> UserSelectedPixelRegion | None:
    region = request.selected_region
    if region is None:
        return None
    x_min = int(region.x_min * width)
    y_min = int(region.y_min * height)
    x_max = min(width, max(x_min + 1, int(region.x_max * width + 0.999999)))
    y_max = min(height, max(y_min + 1, int(region.y_max * height + 0.999999)))
    return UserSelectedPixelRegion(
        source_chip_id=chip_id,
        image_width=width,
        image_height=height,
        x_min=x_min,
        y_min=y_min,
        x_max=x_max,
        y_max=y_max,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
