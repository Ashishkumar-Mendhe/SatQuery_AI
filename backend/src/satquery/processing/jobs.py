from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.io import MemoryFile
from rasterio.transform import Affine
from rasterio.warp import reproject
from rio_tiler.utils import render

from satquery import __version__
from satquery.api.schemas.asset_resolution import AssetResolutionRequest
from satquery.api.schemas.processing import (
    ArtifactAccess,
    ArtifactReference,
    JobProgress,
    PreparationRequest,
    ProcessingJobStatus,
)
from satquery.db.processing import (
    ArtifactKind,
    ArtifactRecord,
    JobRecord,
    ProcessingPersistenceError,
    ProcessingPrincipal,
    ProcessingRepository,
)
from satquery.processing.change import PairPreparationOutcome, PairPreparationService
from satquery.processing.change_detection import (
    OpticalChangeDetectionOutcome,
    OpticalChangeDetector,
)
from satquery.processing.change_summary import ChangeSummaryService, ComputedChangeSummary
from satquery.processing.grid import CommonGridResult, CommonGridService, ScenePreparationInput
from satquery.processing.quality import QualityMaskService
from satquery.processing.raster import RasterInputService
from satquery.processing.registration import RegistrationResult, RegistrationService
from satquery.processing.validity import (
    SceneAcquisitionEvidence,
    ScientificValidityContext,
    ScientificValidityEngine,
    ScientificValidityReport,
)
from satquery.providers.catalog import CatalogueProvider
from satquery.storage import AtomicArtifactStore, StorageLimitError

PROCESSING_CODE_VERSION = f"satquery-{__version__}-phase-8f-v1"
PROCESSING_CONFIG_VERSION = "preparation-and-change-job-v1"


def _render_mask_tile(stream: Any, mask: str, z: int, x: int, y: int) -> bytes:
    world = 20_037_508.342789244
    tile_span = 2 * world / (2**z)
    west = -world + x * tile_span
    east = west + tile_span
    north = world - y * tile_span
    south = north - tile_span
    destination_transform = rasterio.transform.from_bounds(west, south, east, north, 256, 256)
    with rasterio.open(stream) as source:
        if source.crs is None:
            raise MaskTileError("MISSING_GEOREFERENCING", "The quality mask has no CRS.", 422)
        descriptions = {
            description: index
            for index, description in enumerate(source.descriptions, 1)
            if description
        }
        names = (
            ["usable"]
            if mask == "usable"
            else [
                "missing_or_invalid",
                "clouds_or_cirrus",
                "cloud_shadows",
                "cast_shadows",
                "snow_or_ice",
                "unknown_quality",
            ]
        )
        if any(name not in descriptions for name in names):
            raise MaskTileError(
                "INVALID_MASK_ARTIFACT",
                "The quality mask is missing required labelled bands.",
                422,
            )
        selected = np.zeros((256, 256), dtype=np.uint8)
        for name in names:
            band = np.zeros((256, 256), dtype=np.uint8)
            reproject(
                source=rasterio.band(source, descriptions[name]),
                destination=band,
                src_transform=source.transform,
                src_crs=source.crs,
                dst_transform=destination_transform,
                dst_crs="EPSG:3857",
                src_nodata=0,
                dst_nodata=0,
                resampling=Resampling.nearest,
            )
            selected |= band > 0
    alpha = selected.astype(np.uint8) * 255
    color = (55, 211, 145) if mask == "usable" else (255, 132, 84)
    rgb = np.stack([selected.astype(np.uint8) * channel for channel in color])
    return render(rgb, mask=alpha, img_format="PNG")


def _render_change_tile(stream: Any, z: int, x: int, y: int) -> bytes:
    world = 20_037_508.342789244
    tile_span = 2 * world / (2**z)
    west, north = -world + x * tile_span, world - y * tile_span
    transform = rasterio.transform.from_bounds(
        west, north - tile_span, west + tile_span, north, 256, 256
    )
    with rasterio.open(stream) as source:
        if source.crs is None:
            raise MaskTileError("MISSING_GEOREFERENCING", "The change raster has no CRS.", 422)
        descriptions = {name: index for index, name in enumerate(source.descriptions, 1) if name}
        if "change_class" not in descriptions or "inside_aoi" not in descriptions:
            raise MaskTileError(
                "INVALID_CHANGE_ARTIFACT", "The change raster is missing labelled bands.", 422
            )
        classification = np.full((256, 256), 255, dtype=np.uint8)
        inside = np.zeros((256, 256), dtype=np.uint8)
        for destination, name, nodata in (
            (classification, "change_class", 255),
            (inside, "inside_aoi", 0),
        ):
            reproject(
                source=rasterio.band(source, descriptions[name]),
                destination=destination,
                src_transform=source.transform,
                src_crs=source.crs,
                dst_transform=transform,
                dst_crs="EPSG:3857",
                src_nodata=nodata,
                dst_nodata=nodata,
                resampling=Resampling.nearest,
            )
    changed = (classification == 1) & (inside > 0)
    unknown = (classification == 255) & (inside > 0)
    rgb = np.zeros((3, 256, 256), dtype=np.uint8)
    rgb[:, changed] = np.array([239, 68, 68], dtype=np.uint8)[:, None]
    rgb[:, unknown] = np.array([148, 163, 184], dtype=np.uint8)[:, None]
    alpha = np.zeros((256, 256), dtype=np.uint8)
    alpha[changed] = 230
    alpha[unknown] = 150
    return render(rgb, mask=alpha, img_format="PNG")


class PreparationJobError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class JobNotFoundError(RuntimeError):
    pass


class QualityReportUnavailableError(RuntimeError):
    pass


class MaskTileError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class PreparationJobService:
    """Durable bounded orchestration around the Phase 6B-6F preparation stages."""

    def __init__(
        self,
        repository: ProcessingRepository,
        provider: CatalogueProvider,
        artifact_store: AtomicArtifactStore,
        *,
        max_concurrency: int = 1,
        timeout_seconds: float = 300.0,
        max_pixels: int = 4_000_000,
        max_memory_bytes: int = 512 * 1024 * 1024,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._artifact_store = artifact_store
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._timeout_seconds = timeout_seconds
        self._max_pixels = max_pixels
        self._max_memory_bytes = max_memory_bytes
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    async def start(self) -> None:
        await self._repository.reconcile_interrupted(datetime.now(UTC))
        for operation in ("prepare_optical", "analyze_change"):
            for job in await self._repository.queued_jobs(operation):
                self._dispatch(job.job_id, operation)

    async def stop(self) -> None:
        tasks = tuple(self._tasks.values())
        if not tasks:
            return
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def submit(
        self,
        principal: ProcessingPrincipal,
        request: PreparationRequest,
        *,
        idempotency_key: str,
    ) -> JobRecord:
        _validate_submission_limits(request, self._max_pixels, self._max_memory_bytes)
        source_evidence = await _resolve_source_evidence(self._provider, request)
        request_json = request.model_dump(mode="json")
        request_digest = _sha256_json({"request": _canonical_request(request)})
        cache_key = _sha256_json(
            {
                "access_scope": principal.access_scope,
                "owner_id": str(principal.owner_id),
                "source_evidence": source_evidence,
                "request": _canonical_request(request),
                "required_bands": request_json["required_bands"],
                "target_grid": request_json["options"],
                "task_profile": {
                    "intended_task": request.intended_task,
                    "processing_profile": request.processing_profile,
                },
                "code_version": PROCESSING_CODE_VERSION,
                "configuration_version": PROCESSING_CONFIG_VERSION,
            }
        )
        cached = await self._repository.find_successful_cache(
            principal, cache_key, "prepare_optical"
        )
        if cached is not None:
            cached_artifacts = await self._repository.artifacts_for_job(principal, cached.job_id)
            if _artifact_set_complete(cached, cached_artifacts, self._artifact_store):
                return cached
        submitted_at = datetime.now(UTC)
        proposed = JobRecord(
            job_id=uuid4(),
            owner_id=principal.owner_id,
            access_scope=principal.access_scope,
            operation="prepare_optical",
            operation_version="8b-pair-preparation-v1",
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            cache_key=cache_key,
            request_json=request_json,
            source_evidence_json=source_evidence,
            state="queued",
            current_stage=None,
            completed_units=None,
            total_units=None,
            attempt=0,
            submitted_at=submitted_at,
            started_at=None,
            finished_at=None,
            error_code=None,
            safe_error_message=None,
            quality_report_json=None,
            manifest_json=None,
        )
        record, created = await self._repository.submit(record=proposed)
        if created:
            self._dispatch(record.job_id)
        return record

    async def submit_change(
        self, principal: ProcessingPrincipal, request: PreparationRequest, *, idempotency_key: str
    ) -> JobRecord:
        if request.intended_task != "optical_pair" or len(request.scenes) != 2:
            raise PreparationJobError(
                "CHANGE_PAIR_REQUIRED", "Change analysis requires exactly two optical scenes."
            )
        _validate_submission_limits(request, self._max_pixels, self._max_memory_bytes)
        source_evidence = await _resolve_source_evidence(self._provider, request)
        canonical = _canonical_request(request)
        request_digest = _sha256_json({"request": canonical, "operation": "analyze_change"})
        cache_key = _sha256_json(
            {
                "access_scope": principal.access_scope,
                "owner_id": str(principal.owner_id),
                "source_evidence": source_evidence,
                "request": canonical,
                "operation": "analyze_change",
                "detector": "8c-calibrated-rgb-rms-v1",
                "summary": "8d-computed-summary-v1",
                "code_version": PROCESSING_CODE_VERSION,
                "configuration_version": PROCESSING_CONFIG_VERSION,
            }
        )
        cached = await self._repository.find_successful_cache(
            principal, cache_key, "analyze_change"
        )
        if cached is not None:
            artifacts = await self._repository.artifacts_for_job(principal, cached.job_id)
            if _artifact_set_complete(cached, artifacts, self._artifact_store):
                return cached
        proposed = JobRecord(
            job_id=uuid4(),
            owner_id=principal.owner_id,
            access_scope=principal.access_scope,
            operation="analyze_change",
            operation_version="8e-change-analysis-v1",
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            cache_key=cache_key,
            request_json=request.model_dump(mode="json"),
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
        record, created = await self._repository.submit(record=proposed)
        if created:
            self._dispatch(record.job_id, "analyze_change")
        return record

    async def status(self, principal: ProcessingPrincipal, job_id: UUID) -> ProcessingJobStatus:
        record = await self._repository.get_job(principal, job_id)
        if record is None or record.operation != "prepare_optical":
            raise JobNotFoundError
        artifacts = await self._artifact_references(principal, record)
        progress = None
        if record.completed_units is not None and record.total_units is not None:
            progress = JobProgress(
                completed_units=record.completed_units,
                total_units=record.total_units,
                units="stages",
            )
        return ProcessingJobStatus(
            job_id=record.job_id,
            state=record.state,
            submitted_at=record.submitted_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            attempt=record.attempt,
            current_stage=record.current_stage,
            progress=progress,
            artifacts=list(artifacts),
            error_code=record.error_code,
            safe_error_message=record.safe_error_message,
        )

    async def change_status(
        self, principal: ProcessingPrincipal, job_id: UUID
    ) -> ProcessingJobStatus:
        record = await self._repository.get_job(principal, job_id)
        if record is None or record.operation != "analyze_change":
            raise JobNotFoundError
        artifacts = await self._artifact_references(principal, record)
        progress = (
            JobProgress(
                completed_units=record.completed_units,
                total_units=record.total_units,
                units="stages",
            )
            if record.completed_units is not None and record.total_units is not None
            else None
        )
        return ProcessingJobStatus(
            job_id=record.job_id,
            state=record.state,
            submitted_at=record.submitted_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            attempt=record.attempt,
            current_stage=record.current_stage,
            progress=progress,
            artifacts=list(artifacts),
            error_code=record.error_code,
            safe_error_message=record.safe_error_message,
        )

    async def change_result(self, principal: ProcessingPrincipal, job_id: UUID) -> dict[str, Any]:
        record = await self._repository.get_job(principal, job_id)
        if record is None or record.operation != "analyze_change":
            raise JobNotFoundError
        if record.state != "succeeded" or record.manifest_json is None:
            raise QualityReportUnavailableError
        result = record.manifest_json.get("change_result")
        if not isinstance(result, dict):
            raise ProcessingPersistenceError("Committed change result is missing.")
        return result

    async def cancel_change(
        self, principal: ProcessingPrincipal, job_id: UUID
    ) -> ProcessingJobStatus:
        record = await self._repository.get_job(principal, job_id)
        if record is None or record.operation != "analyze_change":
            raise JobNotFoundError
        await self._repository.request_cancel(principal, job_id, datetime.now(UTC))
        return await self.change_status(principal, job_id)

    async def change_tile(
        self, principal: ProcessingPrincipal, artifact_id: UUID, z: int, x: int, y: int
    ) -> bytes:
        if z < 0 or z > 16 or x < 0 or y < 0 or x >= 2**z or y >= 2**z:
            raise MaskTileError("INVALID_TILE_COORDINATES", "Tile coordinates are invalid.", 422)
        record = await self._repository.get_artifact(principal, artifact_id)
        if (
            record is None
            or record.kind != "change_classification"
            or not self._artifact_store.exists(record.storage_key)
        ):
            raise JobNotFoundError
        stream = self._artifact_store.open(record.storage_key)
        try:
            return await asyncio.to_thread(_render_change_tile, stream, z, x, y)
        except Exception as exc:
            raise MaskTileError(
                "CHANGE_TILE_RENDER_FAILED", "The change overlay could not be rendered.", 500
            ) from exc
        finally:
            stream.close()

    async def quality_report(self, principal: ProcessingPrincipal, job_id: UUID) -> dict[str, Any]:
        record = await self._repository.get_job(principal, job_id)
        if record is None or record.operation != "prepare_optical":
            raise JobNotFoundError
        if record.state != "succeeded" or record.quality_report_json is None:
            raise QualityReportUnavailableError
        return record.quality_report_json

    async def cancel(self, principal: ProcessingPrincipal, job_id: UUID) -> ProcessingJobStatus:
        existing = await self._repository.get_job(principal, job_id)
        if existing is None or existing.operation != "prepare_optical":
            raise JobNotFoundError
        record = await self._repository.request_cancel(principal, job_id, datetime.now(UTC))
        if record is None:
            raise JobNotFoundError
        return await self.status(principal, job_id)

    async def artifact(
        self, principal: ProcessingPrincipal, artifact_id: UUID
    ) -> tuple[ArtifactRecord, Any]:
        record = await self._repository.get_artifact(principal, artifact_id)
        if (
            record is None
            or record.kind in {"inference_evidence", "inference_chip"}
            or not self._artifact_store.exists(record.storage_key)
        ):
            raise JobNotFoundError
        return record, self._artifact_store.open(record.storage_key)

    async def mask_tile(
        self,
        principal: ProcessingPrincipal,
        artifact_id: UUID,
        mask: str,
        z: int,
        x: int,
        y: int,
    ) -> bytes:
        if mask not in {"usable", "exclusions"}:
            raise MaskTileError("INVALID_MASK", "The requested mask overlay is unsupported.", 422)
        if z < 0 or z > 16 or x < 0 or y < 0 or x >= 2**z or y >= 2**z:
            raise MaskTileError("INVALID_TILE_COORDINATES", "Tile coordinates are invalid.", 422)
        record = await self._repository.get_artifact(principal, artifact_id)
        if record is None or record.kind != "quality_mask":
            raise JobNotFoundError
        if not self._artifact_store.exists(record.storage_key):
            raise JobNotFoundError
        stream = self._artifact_store.open(record.storage_key)
        try:
            return await asyncio.to_thread(_render_mask_tile, stream, mask, z, x, y)
        except MaskTileError:
            raise
        except Exception as exc:
            raise MaskTileError(
                "MASK_TILE_RENDER_FAILED",
                "The committed quality mask could not be rendered.",
                500,
            ) from exc
        finally:
            stream.close()

    def _dispatch(self, job_id: UUID, operation: str = "prepare_optical") -> None:
        existing = self._tasks.get(job_id)
        if existing is not None and not existing.done():
            return
        task = asyncio.create_task(self._run(job_id, operation), name=f"{operation}-{job_id}")
        self._tasks[job_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(job_id, None))

    async def _run(self, job_id: UUID, operation: str = "prepare_optical") -> None:
        async with self._semaphore:
            try:
                record = next(
                    (
                        item
                        for item in await self._repository.queued_jobs(cast(Any, operation))
                        if item.job_id == job_id
                    ),
                    None,
                )
                if record is None:
                    return
                request = PreparationRequest.model_validate(record.request_json)
                total_units = len(request.scenes) * 2 + 4
                if request.intended_task == "optical_pair":
                    total_units += 1
                if operation == "analyze_change":
                    total_units += 2
                if not await self._repository.start_job(job_id, datetime.now(UTC), total_units):
                    return
                async with asyncio.timeout(self._timeout_seconds):
                    await self._execute(
                        record, request, total_units, analyze_change=operation == "analyze_change"
                    )
            except asyncio.CancelledError:
                # Startup reconciliation records this running attempt as interrupted next time.
                raise
            except TimeoutError:
                await self._safe_fail(
                    job_id, "PROCESSING_TIMEOUT", "The preparation exceeded its time limit."
                )
            except PreparationJobError as exc:
                await self._safe_fail(job_id, exc.code, str(exc))
            except (ProcessingPersistenceError, StorageLimitError) as exc:
                await self._safe_fail(job_id, "PROCESSING_DEPENDENCY_FAILED", str(exc))
            except Exception as exc:  # defensive boundary: never persist internal exception text
                code = getattr(exc, "code", "PROCESSING_FAILED")
                await self._safe_fail(
                    job_id,
                    str(code),
                    "Preparation failed while processing the selected scientific inputs.",
                )

    async def _execute(
        self,
        record: JobRecord,
        request: PreparationRequest,
        total_units: int,
        *,
        analyze_change: bool = False,
    ) -> None:
        completed = 0
        inputs: list[ScenePreparationInput] = []
        raster_service = RasterInputService(self._provider, max_pixels=self._max_pixels)
        quality_service = QualityMaskService(self._provider)
        for index, _scene in enumerate(request.scenes):
            await self._check_cancel(record.job_id)
            source_request = _source_request(request, index)
            raster = await raster_service.extract(source_request)
            completed += 1
            await self._repository.update_progress(
                record.job_id,
                stage=f"scene_{index + 1}_raster_extracted",
                completed_units=completed,
                occurred_at=datetime.now(UTC),
            )
            await self._check_cancel(record.job_id)
            quality = await quality_service.decode(raster)
            inputs.append(ScenePreparationInput(raster=raster, quality=quality))
            completed += 1
            await self._repository.update_progress(
                record.job_id,
                stage=f"scene_{index + 1}_quality_decoded",
                completed_units=completed,
                occurred_at=datetime.now(UTC),
            )

        common_request = _common_grid_request(request)
        grid = await asyncio.to_thread(
            CommonGridService(max_pixels=self._max_pixels).prepare, common_request, tuple(inputs)
        )
        completed += 1
        await self._repository.update_progress(
            record.job_id,
            stage="common_grid_prepared",
            completed_units=completed,
            occurred_at=datetime.now(UTC),
        )
        await self._check_cancel(record.job_id)

        registration: RegistrationResult | None = None
        if request.intended_task == "optical_pair":
            registration = await asyncio.to_thread(RegistrationService().assess_and_correct, grid)
        completed += 1
        await self._repository.update_progress(
            record.job_id,
            stage="registration_assessed" if registration else "registration_not_applicable",
            completed_units=completed,
            occurred_at=datetime.now(UTC),
        )
        await self._check_cancel(record.job_id)

        acquisitions = _acquisition_evidence(request, record.source_evidence_json)
        validity = await asyncio.to_thread(
            ScientificValidityEngine().evaluate,
            ScientificValidityContext(
                request=common_request,
                common_grid=grid,
                registration=registration,
                acquisition_evidence=acquisitions,
                requested_spatial_scale_metres=None,
            ),
        )
        completed += 1
        await self._repository.update_progress(
            record.job_id,
            stage="scientific_validity_evaluated",
            completed_units=completed,
            occurred_at=datetime.now(UTC),
        )
        await self._check_cancel(record.job_id)

        pair_preparation: PairPreparationOutcome | None = None
        if request.intended_task == "optical_pair":
            if registration is None:
                raise PreparationJobError(
                    "REGISTRATION_UNAVAILABLE",
                    "Pair comparability requires a registration assessment.",
                )
            pair_preparation = await asyncio.to_thread(
                PairPreparationService().prepare,
                common_request,
                grid,
                registration,
                acquisitions,
            )
            completed += 1
            await self._repository.update_progress(
                record.job_id,
                stage="pair_comparability_assessed",
                completed_units=completed,
                occurred_at=datetime.now(UTC),
            )
            await self._check_cancel(record.job_id)

        detection: OpticalChangeDetectionOutcome | None = None
        summary: ComputedChangeSummary | None = None
        if analyze_change:
            if pair_preparation is None or registration is None:
                raise PreparationJobError(
                    "CHANGE_PAIR_UNAVAILABLE", "Change analysis requires a prepared pair."
                )
            if not pair_preparation.comparison_allowed:
                reason = pair_preparation.reasons[0] if pair_preparation.reasons else None
                raise PreparationJobError(
                    reason.code if reason else "PAIR_NOT_COMPARABLE",
                    reason.explanation if reason else "The selected pair cannot be compared.",
                )
            detection = await asyncio.to_thread(
                OpticalChangeDetector().detect, pair_preparation, grid, registration
            )
            if detection.state != "completed":
                detection_reason = detection.reasons[0] if detection.reasons else None
                raise PreparationJobError(
                    detection_reason.code if detection_reason else "CHANGE_INSUFFICIENT_EVIDENCE",
                    detection_reason.explanation
                    if detection_reason
                    else "Change could not be measured.",
                )
            completed += 1
            await self._repository.update_progress(
                record.job_id,
                stage="spectral_change_detected",
                completed_units=completed,
                occurred_at=datetime.now(UTC),
            )
            summary = await asyncio.to_thread(
                ChangeSummaryService().summarize,
                common_request,
                pair_preparation,
                detection,
                grid,
                registration,
            )
            completed += 1
            await self._repository.update_progress(
                record.job_id,
                stage="change_summary_computed",
                completed_units=completed,
                occurred_at=datetime.now(UTC),
            )

        artifacts, manifest = await asyncio.to_thread(
            _write_artifacts,
            self._artifact_store,
            record,
            common_request,
            grid,
            registration,
            validity,
            pair_preparation,
            detection,
            summary,
        )
        await self._check_cancel(record.job_id)
        quality_report = _validity_json(validity)
        completed += 1
        if completed != total_units:
            raise PreparationJobError(
                "PROGRESS_INCONSISTENT", "Processing stage accounting failed."
            )
        await self._repository.succeed_job(
            record.job_id,
            artifacts=artifacts,
            quality_report=quality_report,
            manifest=manifest,
            occurred_at=datetime.now(UTC),
        )

    async def _check_cancel(self, job_id: UUID) -> None:
        if await self._repository.cancellation_requested(job_id):
            await self._repository.mark_cancelled(job_id, datetime.now(UTC))
            raise PreparationJobError("JOB_CANCELLED", "The preparation was cancelled.")

    async def _safe_fail(self, job_id: UUID, code: str, message: str) -> None:
        try:
            if code == "JOB_CANCELLED":
                return
            await self._repository.fail_job(
                job_id,
                code=code[:160].lower().replace(" ", "_"),
                message=message[:1000],
                occurred_at=datetime.now(UTC),
            )
        except ProcessingPersistenceError:
            return

    async def _artifact_references(
        self, principal: ProcessingPrincipal, record: JobRecord
    ) -> tuple[ArtifactReference, ...]:
        if record.state != "succeeded":
            return ()
        artifacts = await self._repository.artifacts_for_job(principal, record.job_id)
        if not _artifact_set_complete(record, artifacts, self._artifact_store):
            raise ProcessingPersistenceError("Committed preparation artifacts are incomplete.")
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


def _artifact_set_complete(
    record: JobRecord,
    artifacts: tuple[ArtifactRecord, ...],
    store: AtomicArtifactStore,
) -> bool:
    if record.manifest_json is None:
        return False
    listed = record.manifest_json.get("artifacts")
    manifest_id = record.manifest_json.get("manifest_artifact_id")
    if not isinstance(listed, list) or not isinstance(manifest_id, str):
        return False
    expected_ids = {manifest_id}
    for item in listed:
        if not isinstance(item, dict) or not isinstance(item.get("artifact_id"), str):
            return False
        expected_ids.add(item["artifact_id"])
    actual_ids = {str(item.artifact_id) for item in artifacts}
    return (
        actual_ids == expected_ids
        and any(item.kind == "provenance_manifest" for item in artifacts)
        and all(store.exists(item.storage_key) for item in artifacts)
    )


async def _resolve_source_evidence(
    provider: CatalogueProvider, request: PreparationRequest
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for scene in request.scenes:
        resolved = await provider.resolve_imagery_sources(AssetResolutionRequest(scene=scene))
        if (
            resolved.resolution.status.state != "supported"
            or resolved.resolution.resolved_asset is None
        ):
            raise PreparationJobError(
                "RASTER_SOURCE_UNAVAILABLE",
                resolved.resolution.status.reason or "A selected scene is unavailable.",
            )
        asset = resolved.resolution.resolved_asset
        evidence.append(
            {
                "scene": scene.model_dump(mode="json"),
                "resolved_asset": asset.identity.model_dump(mode="json"),
                "components": [
                    {
                        "identity": item.component.identity.model_dump(mode="json"),
                        "role": item.component.common_name,
                        "resolution_metres": item.component.resolution_metres,
                        "scale": item.component.scale,
                        "offset": item.component.offset,
                        "crs": item.component.crs,
                        "shape": item.component.shape,
                        "transform": item.component.transform,
                        "checksum_sha256": None,
                        "checksum_unavailable_reason": (
                            "The trusted provider metadata did not supply a source checksum."
                        ),
                    }
                    for item in resolved.sources
                ],
                "acquisition": asset.acquisition.model_dump(mode="json"),
            }
        )
    return evidence


def _validate_submission_limits(
    request: PreparationRequest, max_pixels: int, max_memory_bytes: int
) -> None:
    if request.options.max_output_pixels > max_pixels:
        raise PreparationJobError(
            "PIXEL_LIMIT_EXCEEDED", f"The request exceeds the {max_pixels}-pixel service limit."
        )
    estimated = (
        request.options.max_output_pixels
        * len(request.scenes)
        * (len(request.required_bands) * 8 + 20)
    )
    if estimated > max_memory_bytes:
        raise PreparationJobError(
            "MEMORY_LIMIT_EXCEEDED",
            "The bounded worst-case preparation memory estimate exceeds the service limit.",
        )


def _source_request(request: PreparationRequest, index: int) -> PreparationRequest:
    payload = request.model_dump(mode="json")
    payload["scenes"] = [payload["scenes"][index]]
    payload["intended_task"] = "optical_single_scene"
    payload["options"]["grid_policy"] = "source_aligned"
    payload["options"]["target_resolution_metres"] = 10.0
    payload["options"]["continuous_resampling"] = "nearest"
    return PreparationRequest.model_validate(payload)


def _common_grid_request(request: PreparationRequest) -> PreparationRequest:
    if request.options.grid_policy == "common_utm":
        return request
    payload = request.model_dump(mode="json")
    payload["options"]["grid_policy"] = "common_utm"
    return PreparationRequest.model_validate(payload)


def _canonical_request(request: PreparationRequest) -> dict[str, Any]:
    payload = request.model_dump(mode="json")
    payload["aoi"] = _canonical_geometry(payload["aoi"])
    return payload


def _canonical_geometry(geometry: dict[str, Any]) -> dict[str, Any]:
    polygons = (
        geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    )
    canonical_polygons = []
    for polygon in polygons:
        exterior = _canonical_ring(polygon[0])
        holes = sorted((_canonical_ring(ring) for ring in polygon[1:]), key=_json_key)
        canonical_polygons.append([exterior, *holes])
    canonical_polygons.sort(key=_json_key)
    return {
        "type": geometry["type"],
        "coordinates": canonical_polygons
        if geometry["type"] == "MultiPolygon"
        else canonical_polygons[0],
    }


def _canonical_ring(ring: list[list[float]]) -> list[list[float]]:
    vertices: list[tuple[float, float]] = [
        (float(point[0]), float(point[1])) for point in ring[:-1]
    ]
    candidates: list[tuple[tuple[float, float], ...]] = []
    for ordered in (vertices, list(reversed(vertices))):
        for index in range(len(ordered)):
            candidates.append(tuple(ordered[index:] + ordered[:index]))
    selected = min(candidates)
    return [list(point) for point in (*selected, selected[0])]


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_json_key(value).encode()).hexdigest()


def _acquisition_evidence(
    request: PreparationRequest, evidence: list[dict[str, Any]]
) -> tuple[SceneAcquisitionEvidence, ...]:
    items = []
    for scene, source in zip(request.scenes, evidence, strict=True):
        acquisition = source["acquisition"]
        items.append(
            SceneAcquisitionEvidence(
                scene=scene,
                acquired_at=datetime.fromisoformat(acquisition["start"].replace("Z", "+00:00")),
                sensor="MSI",
                platform=scene.item.split("_", 1)[0],
                processing_level="L2A",
            )
        )
    return tuple(items)


def _effective_scenes(
    grid: CommonGridResult, registration: RegistrationResult | None
) -> tuple[Any, ...]:
    if registration is None or registration.corrected_moving_scene is None:
        return grid.scenes
    return (grid.scenes[0], registration.corrected_moving_scene)


def _write_artifacts(
    store: AtomicArtifactStore,
    record: JobRecord,
    request: PreparationRequest,
    grid: CommonGridResult,
    registration: RegistrationResult | None,
    validity: ScientificValidityReport,
    pair_preparation: PairPreparationOutcome | None,
    detection: OpticalChangeDetectionOutcome | None = None,
    summary: ComputedChangeSummary | None = None,
) -> tuple[tuple[ArtifactRecord, ...], dict[str, Any]]:
    now = datetime.now(UTC)
    written: list[ArtifactRecord] = []
    total_bytes = 0
    scene_entries: list[dict[str, Any]] = []
    for scene in _effective_scenes(grid, registration):
        raster = _geotiff_bytes(
            scene.data.astype(np.float32), grid, nodata=np.nan, descriptions=scene.band_order
        )
        raster_record = _store_record(
            store,
            record,
            uuid4(),
            "prepared_raster",
            "image/tiff",
            ".tif",
            raster,
            total_bytes,
            now,
        )
        written.append(raster_record)
        total_bytes += raster_record.byte_size
        validity_arrays = np.concatenate(
            (
                scene.band_validity.astype(np.uint8),
                scene.valid_data.astype(np.uint8)[None, ...],
                grid.aoi_mask.astype(np.uint8)[None, ...],
            )
        )
        validity_names = (
            *(f"{role}_valid" for role in scene.band_order),
            "all_bands_valid",
            "inside_aoi",
        )
        validity_bytes = _geotiff_bytes(
            validity_arrays, grid, nodata=None, descriptions=validity_names
        )
        validity_record = _store_record(
            store,
            record,
            uuid4(),
            "validity_mask",
            "image/tiff",
            ".tif",
            validity_bytes,
            total_bytes,
            now,
        )
        written.append(validity_record)
        total_bytes += validity_record.byte_size
        quality_arrays = np.stack(
            [
                scene.quality.scl_classes,
                scene.quality.outside_aoi,
                scene.quality.missing_or_invalid,
                scene.quality.clouds_or_cirrus,
                scene.quality.cloud_shadows,
                scene.quality.cast_shadows,
                scene.quality.snow_or_ice,
                scene.quality.unknown_quality,
                scene.quality.usable,
            ]
        ).astype(np.uint8)
        quality_names = (
            "scl_class",
            "outside_aoi",
            "missing_or_invalid",
            "clouds_or_cirrus",
            "cloud_shadows",
            "cast_shadows",
            "snow_or_ice",
            "unknown_quality",
            "usable",
        )
        quality_bytes = _geotiff_bytes(
            quality_arrays, grid, nodata=None, descriptions=quality_names
        )
        quality_record = _store_record(
            store,
            record,
            uuid4(),
            "quality_mask",
            "image/tiff",
            ".tif",
            quality_bytes,
            total_bytes,
            now,
        )
        written.append(quality_record)
        total_bytes += quality_record.byte_size
        scene_entries.append(
            {
                "scene": scene.scene.model_dump(mode="json"),
                "raster_artifact_id": str(raster_record.artifact_id),
                "validity_artifact_id": str(validity_record.artifact_id),
                "quality_artifact_id": str(quality_record.artifact_id),
                "band_order": list(scene.band_order),
                "units": [band.units for band in scene.bands],
                "native_resolutions_metres": list(scene.native_resolutions_metres),
                "output_resolution_metres": scene.output_resolution_metres,
                "continuous_resampling": scene.continuous_resampling,
                "categorical_resampling": "nearest",
                "upsampled": scene.upsampled,
                "upsampling_explanation": scene.upsampling_explanation,
                "calibration": [
                    {
                        "source": band.source.model_dump(mode="json"),
                        "role": band.role,
                        "method": band.method,
                        "provider_scale": band.provider_scale,
                        "provider_offset": band.provider_offset,
                        "applied_scale": band.applied_scale,
                        "applied_offset": band.applied_offset,
                    }
                    for band in scene.bands
                ],
                "quality_information": scene.quality.quality_information,
                "quality_source_asset": scene.quality.source_asset,
                "scl_class_labels": scene.quality.class_labels,
                "coverage": [asdict(item) for item in scene.coverage],
                "validity_bands": list(validity_names),
                "quality_bands": list(quality_names),
            }
        )
    pair_masks_artifact_id: str | None = None
    if len(grid.scenes) == 2:
        joint_valid = pair_preparation.joint_valid if pair_preparation else grid.joint_valid_data
        joint_usable = pair_preparation.joint_usable if pair_preparation else grid.joint_usable
        if joint_valid is None or joint_usable is None:
            raise PreparationJobError(
                "PAIR_MASKS_UNAVAILABLE", "A pair preparation requires joint masks."
            )
        pair_mask_id = uuid4()
        pair_mask_bytes = _geotiff_bytes(
            np.stack((joint_valid, joint_usable)).astype(np.uint8),
            grid,
            nodata=None,
            descriptions=("joint_valid", "joint_usable"),
        )
        pair_record = _store_record(
            store,
            record,
            pair_mask_id,
            "quality_mask",
            "image/tiff",
            ".tif",
            pair_mask_bytes,
            total_bytes,
            now,
        )
        written.append(pair_record)
        total_bytes += pair_record.byte_size
        pair_masks_artifact_id = str(pair_mask_id)
    change_artifact_id: str | None = None
    if detection is not None:
        if detection.classification is None or summary is None:
            raise PreparationJobError(
                "CHANGE_RESULT_INCOMPLETE", "Change classification or summary is missing."
            )
        change_id = uuid4()
        change_bytes = _geotiff_bytes(
            np.stack((detection.classification, grid.aoi_mask.astype(np.uint8))).astype(np.uint8),
            grid,
            nodata=None,
            descriptions=("change_class", "inside_aoi"),
        )
        change_record = _store_record(
            store,
            record,
            change_id,
            "change_classification",
            "image/tiff",
            ".tif",
            change_bytes,
            total_bytes,
            now,
        )
        written.append(change_record)
        total_bytes += change_record.byte_size
        change_artifact_id = str(change_id)
    manifest_id = uuid4()
    manifest = {
        "schema_version": "1.0",
        "job_id": str(record.job_id),
        "cache_key_sha256": record.cache_key,
        "request_digest_sha256": record.request_digest,
        "code_version": PROCESSING_CODE_VERSION,
        "configuration_version": PROCESSING_CONFIG_VERSION,
        "request": _canonical_request(request),
        "source_provenance": record.source_evidence_json,
        "grid": grid.grid.model_dump(mode="json"),
        "area_method": grid.area_method,
        "radiometric_harmonization": grid.radiometric_harmonization,
        "registration": _registration_json(registration),
        "comparison_preparation": _pair_preparation_json(
            pair_preparation, pair_masks_artifact_id, change_artifact_id
        ),
        "pair_masks_artifact_id": pair_masks_artifact_id,
        "pair_coverage": [asdict(item) for item in grid.pair_coverage],
        "processing_parameters": {
            "calibration": request.options.calibration,
            "clip_to_aoi": request.options.clip_to_aoi,
            "continuous_resampling": request.options.continuous_resampling,
            "mask_resampling": request.options.mask_resampling,
            "preserve_originals": request.options.preserve_originals,
            "max_output_pixels": request.options.max_output_pixels,
        },
        "normalization": {"applied": False, "parameters": None},
        "scientific_validity": _validity_json(validity),
        "scenes": scene_entries,
        "artifacts": [
            {
                "artifact_id": str(item.artifact_id),
                "kind": item.kind,
                "media_type": item.media_type,
                "checksum_sha256": item.checksum_sha256,
                "byte_size": item.byte_size,
            }
            for item in written
        ],
        "completed_at": now.isoformat(),
        "manifest_artifact_id": str(manifest_id),
    }
    if summary is not None and change_artifact_id is not None:
        area = asdict(summary.area)
        manifest["change_result"] = {
            "schema_version": "1.0",
            "job_id": str(record.job_id),
            "sources": [
                {
                    "temporal_role": role,
                    "scene": scene.model_dump(mode="json"),
                    "acquired_at": acquired.isoformat(),
                }
                for role, scene, acquired in zip(
                    ("before", "after"), summary.sources, summary.acquired_at, strict=True
                )
            ],
            "aoi": summary.aoi.model_dump(mode="json"),
            "grid": grid.grid.model_dump(mode="json"),
            "method": summary.method,
            "method_version": summary.method_version,
            "threshold": summary.threshold,
            "threshold_units": summary.threshold_units,
            "area": area,
            "alignment_statement": summary.alignment_statement,
            "warnings": [asdict(item) for item in summary.warnings],
            "statements": list(summary.statements),
            "cause_or_land_cover_category": summary.cause_or_land_cover_category,
            "classification_artifact_id": change_artifact_id,
            "processing_version": PROCESSING_CODE_VERSION,
        }
    manifest_payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    manifest_record = _store_record(
        store,
        record,
        manifest_id,
        "provenance_manifest",
        "application/json",
        ".json",
        manifest_payload,
        total_bytes,
        now,
    )
    written.append(manifest_record)
    return tuple(written), manifest


def _geotiff_bytes(
    data: np.ndarray,
    grid: CommonGridResult,
    *,
    nodata: float | int | None,
    descriptions: tuple[str, ...],
) -> bytes:
    profile = {
        "driver": "GTiff",
        "height": grid.grid.height,
        "width": grid.grid.width,
        "count": data.shape[0],
        "dtype": data.dtype,
        "crs": grid.grid.crs,
        "transform": Affine(*grid.grid.transform),
        "nodata": nodata,
        "compress": "deflate",
    }
    with MemoryFile() as memory:
        with memory.open(**profile) as dataset:
            dataset.write(data)
            for index, description in enumerate(descriptions, start=1):
                dataset.set_band_description(index, description)
        return cast(bytes, memory.read())


def _store_record(
    store: AtomicArtifactStore,
    job: JobRecord,
    artifact_id: UUID,
    kind: ArtifactKind,
    media_type: str,
    suffix: str,
    payload: bytes,
    total_bytes: int,
    created_at: datetime,
) -> ArtifactRecord:
    stored = store.write_bytes(
        job.job_id,
        artifact_id,
        suffix,
        payload,
        bytes_already_written=total_bytes,
    )
    return ArtifactRecord(
        artifact_id=artifact_id,
        job_id=job.job_id,
        owner_id=job.owner_id,
        kind=kind,
        media_type=media_type,
        storage_key=stored.storage_key,
        checksum_sha256=stored.checksum_sha256,
        byte_size=stored.byte_size,
        state="available",
        created_at=created_at,
    )


def _registration_json(registration: RegistrationResult | None) -> dict[str, Any]:
    if registration is None:
        return {"state": "not_applicable", "correction": None}
    assessment = registration.assessment
    return {
        "state": assessment.state,
        "explanation": assessment.explanation,
        "method": assessment.method,
        "coordinate_convention": assessment.coordinate_convention,
        "pixel_displacement": [
            assessment.estimated_row_shift_pixels,
            assessment.estimated_column_shift_pixels,
        ],
        "map_displacement_metres": [
            assessment.estimated_x_shift_map_units,
            assessment.estimated_y_shift_map_units,
        ],
        "distribution": asdict(assessment.distribution),
        "agreement": asdict(assessment.agreement),
        "residual": asdict(assessment.residual),
        "correction_state": assessment.correction_state,
        "correction": asdict(assessment.correction) if assessment.correction else None,
        "patches": [asdict(item) for item in assessment.patches],
    }


def _pair_preparation_json(
    outcome: PairPreparationOutcome | None,
    pair_masks_artifact_id: str | None,
    change_artifact_id: str | None = None,
) -> dict[str, Any]:
    if outcome is None:
        return {"state": "not_applicable", "comparison_allowed": False}
    return {
        "state": outcome.state,
        "comparison_allowed": outcome.comparison_allowed,
        "processing_version": outcome.processing_version,
        "parameters": asdict(outcome.parameters),
        "sources": [source.model_dump(mode="json") for source in outcome.sources],
        "acquired_at": [
            value.isoformat() if value is not None else None for value in outcome.acquired_at
        ],
        "band_order": list(outcome.band_order),
        "grid": outcome.grid.model_dump(mode="json"),
        "registration_state": outcome.registration_state,
        "correction_state": outcome.correction_state,
        "coverage": asdict(outcome.coverage),
        "joint_masks_artifact_id": pair_masks_artifact_id,
        "joint_mask_bands": ["joint_valid", "joint_usable"],
        "reasons": [asdict(reason) for reason in outcome.reasons],
        "change_classification_artifact_id": change_artifact_id,
    }


def _validity_json(report: ScientificValidityReport) -> dict[str, Any]:
    return {
        "profile": asdict(report.profile),
        "threshold_version": report.threshold_version,
        "thresholds_are_provisional_engineering_limits": True,
        "readiness": report.readiness,
        "readiness_reason": report.readiness_reason,
        "blocking_check_ids": list(report.blocking_check_ids),
        "warning_check_ids": list(report.warning_check_ids),
        "minimum_supported_spatial_scale_metres": report.minimum_supported_spatial_scale_metres,
        "requested_spatial_scale_metres": report.requested_spatial_scale_metres,
        "map_viewing_affected": False,
        "catalogue_search_affected": False,
        "checks": [asdict(item) for item in report.checks],
    }
