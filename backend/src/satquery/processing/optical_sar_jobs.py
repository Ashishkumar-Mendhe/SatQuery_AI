"""Owner-scoped, durable jobs for bounded separate optical/SAR observations."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import numpy as np
from rasterio.transform import Affine

from satquery.api.schemas.optical_sar import (
    OpticalSarAnalysisRequest,
    OpticalSarAnalysisResult,
    OpticalSarJobStatus,
    OpticalSarObservation,
    OpticalSarSourceEvidence,
)
from satquery.api.schemas.processing import (
    ArtifactAccess,
    ArtifactReference,
    JobProgress,
    PreparationRequest,
    ProcessingOptions,
    RequiredBand,
)
from satquery.api.schemas.sar import SarPreparationRequest
from satquery.db.processing import (
    ArtifactRecord,
    JobRecord,
    ProcessingPersistenceError,
    ProcessingPrincipal,
    ProcessingRepository,
)
from satquery.processing.grid import GridHarmonizationError
from satquery.processing.optical_sar_pair import OpticalSarPairOutcome, OpticalSarPairService
from satquery.processing.quality import QualityMaskError
from satquery.processing.raster import RasterInputError
from satquery.processing.sar import SarProcessingError, SarRasterService
from satquery.providers.catalog.base import CatalogueProvider, CatalogueProviderError
from satquery.providers.catalog.inpe_sar import InpeSarProvider
from satquery.storage import AtomicArtifactStore, StorageLimitError

OPTICAL_SAR_JOB_VERSION = "9e-observation-v1"
SUPPORTED_QUESTION = "Summarize the separate optical and SAR observations."


class OpticalSarJobError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class OpticalSarJobNotFoundError(RuntimeError):
    pass


class OpticalSarResultUnavailableError(RuntimeError):
    pass


class OpticalSarJobService:
    """Reuses processing_jobs and atomic private artifacts, never a public memory-only result."""

    def __init__(
        self,
        repository: ProcessingRepository,
        optical_provider: CatalogueProvider,
        sar_provider: InpeSarProvider,
        sar_service: SarRasterService,
        artifact_store: AtomicArtifactStore,
        *,
        timeout_seconds: float = 300.0,
        max_concurrency: int = 1,
    ) -> None:
        self._repository = repository
        self._optical_provider = optical_provider
        self._sar_provider = sar_provider
        self._sar_service = sar_service
        self._artifact_store = artifact_store
        self._timeout = timeout_seconds
        self._slots = asyncio.Semaphore(max_concurrency)
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    async def start(self) -> None:
        await self._repository.reconcile_interrupted(datetime.now(UTC))
        for job in await self._repository.queued_jobs("analyze_optical_sar"):
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
        request: OpticalSarAnalysisRequest,
        *,
        idempotency_key: str,
    ) -> JobRecord:
        try:
            optical = await self._optical_provider.item(
                request.optical_scene.collection, request.optical_scene.item
            )
            sar = await self._sar_provider.resolve(request.sar_scene, request.polarization)
        except CatalogueProviderError as exc:
            raise OpticalSarJobError(
                "SOURCE_UNAVAILABLE", "A selected source is unavailable from its trusted provider."
            ) from exc
        if (
            optical.provider.id != request.optical_scene.provider
            or optical.provider_asset_id != request.optical_scene.item
            or sar.scene.source != request.sar_scene
        ):
            raise OpticalSarJobError("STALE_SOURCE", "A selected scene identity has changed.")
        evidence = [
            {
                "source": request.optical_scene.model_dump(mode="json"),
                "acquired_at": optical.acquisition.start.isoformat(),
                "version": optical.provider_asset_version,
            },
            {
                "source": request.sar_scene.model_dump(mode="json"),
                "acquired_at": sar.scene.acquisition.start.isoformat(),
                "polarization": request.polarization,
                "checksum": sar.backscatter.checksum,
            },
        ]
        canonical = request.model_dump(mode="json")
        digest = _digest(canonical)
        key = _digest(
            {
                "owner_id": str(principal.owner_id),
                "access_scope": principal.access_scope,
                "request": canonical,
                "evidence": evidence,
                "version": OPTICAL_SAR_JOB_VERSION,
            }
        )
        cached = await self._repository.find_successful_cache(principal, key, "analyze_optical_sar")
        if cached is not None and await self._complete(principal, cached):
            return cached
        proposed = JobRecord(
            job_id=uuid4(),
            owner_id=principal.owner_id,
            access_scope=principal.access_scope,
            operation="analyze_optical_sar",
            operation_version=OPTICAL_SAR_JOB_VERSION,
            idempotency_key=idempotency_key,
            request_digest=digest,
            cache_key=key,
            request_json=canonical,
            source_evidence_json=evidence,
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
        stored, created = await self._repository.submit(record=proposed)
        if created:
            self._dispatch(stored.job_id)
        return stored

    async def status(self, principal: ProcessingPrincipal, job_id: UUID) -> OpticalSarJobStatus:
        record = await self._job(principal, job_id)
        artifacts = await self._repository.artifacts_for_job(principal, job_id)
        if record.state == "succeeded" and not await self._complete(principal, record):
            raise ProcessingPersistenceError("Committed optical/SAR evidence is incomplete.")
        return OpticalSarJobStatus(
            job_id=record.job_id,
            request_id=OpticalSarAnalysisRequest.model_validate(record.request_json).request_id,
            state=record.state,
            submitted_at=record.submitted_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            attempt=record.attempt,
            current_stage=record.current_stage,
            progress=(
                JobProgress(
                    completed_units=record.completed_units,
                    total_units=record.total_units,
                    units="stages",
                )
                if record.completed_units is not None and record.total_units is not None
                else None
            ),
            artifacts=[
                ArtifactReference(
                    artifact_id=item.artifact_id,
                    kind=item.kind,
                    media_type="application/json",
                    checksum_sha256=item.checksum_sha256,
                    byte_size=item.byte_size,
                    access=ArtifactAccess(state="available"),
                )
                for item in artifacts
            ]
            if record.state == "succeeded"
            else [],
            error_code=record.error_code,
            safe_error_message=record.safe_error_message,
        )

    async def result(
        self, principal: ProcessingPrincipal, job_id: UUID
    ) -> OpticalSarAnalysisResult:
        record = await self._job(principal, job_id)
        if record.state != "succeeded" or not await self._complete(principal, record):
            raise OpticalSarResultUnavailableError
        assert record.manifest_json is not None
        return OpticalSarAnalysisResult.model_validate(record.manifest_json["result"])

    async def cancel(self, principal: ProcessingPrincipal, job_id: UUID) -> OpticalSarJobStatus:
        await self._job(principal, job_id)
        await self._repository.request_cancel(principal, job_id, datetime.now(UTC))
        return await self.status(principal, job_id)

    async def artifact(
        self, principal: ProcessingPrincipal, artifact_id: UUID
    ) -> tuple[ArtifactRecord, Any]:
        record = await self._repository.get_artifact(principal, artifact_id)
        if (
            record is None
            or record.kind != "optical_sar_evidence"
            or not self._artifact_store.exists(record.storage_key)
        ):
            raise OpticalSarJobNotFoundError
        return record, self._artifact_store.open(record.storage_key)

    async def _job(self, principal: ProcessingPrincipal, job_id: UUID) -> JobRecord:
        record = await self._repository.get_job(principal, job_id)
        if record is None or record.operation != "analyze_optical_sar":
            raise OpticalSarJobNotFoundError
        return record

    async def _complete(self, principal: ProcessingPrincipal, record: JobRecord) -> bool:
        if record.state != "succeeded" or not isinstance(record.manifest_json, dict):
            return False
        artifacts = await self._repository.artifacts_for_job(principal, record.job_id)
        expected = record.manifest_json.get("artifact_ids")
        return (
            isinstance(expected, list)
            and len(expected) == 1
            and len(artifacts) == 1
            and str(artifacts[0].artifact_id) == expected[0]
            and artifacts[0].kind == "optical_sar_evidence"
            and artifacts[0].state == "available"
            and self._artifact_store.exists(artifacts[0].storage_key)
        )

    def _dispatch(self, job_id: UUID) -> None:
        if job_id in self._tasks and not self._tasks[job_id].done():
            return
        task = asyncio.create_task(self._run(job_id), name=f"optical-sar-{job_id}")
        self._tasks[job_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(job_id, None))

    async def _run(self, job_id: UUID) -> None:
        async with self._slots:
            try:
                record = next(
                    (
                        job
                        for job in await self._repository.queued_jobs("analyze_optical_sar")
                        if job.job_id == job_id
                    ),
                    None,
                )
                if record is None or not await self._repository.start_job(
                    job_id, datetime.now(UTC), 3
                ):
                    return
                async with asyncio.timeout(self._timeout):
                    await self._execute(
                        record, OpticalSarAnalysisRequest.model_validate(record.request_json)
                    )
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                await self._fail(job_id, "PROCESSING_TIMEOUT", "Optical/SAR preparation timed out.")
            except (CatalogueProviderError, SarProcessingError) as exc:
                await self._fail(
                    job_id,
                    getattr(exc, "code", "SOURCE_UNAVAILABLE"),
                    "The trusted optical or SAR raster is unavailable; "
                    "retry or choose another scene.",
                )
            except (RasterInputError, QualityMaskError, GridHarmonizationError) as exc:
                await self._fail(job_id, exc.code, str(exc))
            except (OpticalSarJobError, ProcessingPersistenceError, StorageLimitError) as exc:
                await self._fail(job_id, getattr(exc, "code", "DEPENDENCY_UNAVAILABLE"), str(exc))
            except Exception:
                await self._fail(job_id, "ANALYSIS_FAILED", "Optical/SAR processing failed safely.")

    async def _execute(self, record: JobRecord, request: OpticalSarAnalysisRequest) -> None:
        optical_request = PreparationRequest(
            scenes=[request.optical_scene],
            aoi=request.aoi,
            required_bands=[
                RequiredBand(role=role, common_name=role) for role in ("red", "green", "blue")
            ],
            intended_task="optical_single_scene",
            processing_profile="sentinel-2-l2a-surface-reflectance-v1",
            options=ProcessingOptions(
                grid_policy="common_utm",
                target_resolution_metres=request.target_resolution_metres,
                continuous_resampling="bilinear",
                max_output_pixels=1_000_000,
            ),
        )
        sar_request = SarPreparationRequest(
            scene=request.sar_scene,
            aoi=request.aoi,
            polarization=request.polarization,
            max_pixels=1_000_000,
        )
        pair = await OpticalSarPairService().prepare_real(
            optical_request, sar_request, self._optical_provider, self._sar_service
        )
        await self._stage(record.job_id, "trusted_pair_prepared", 1)
        await self._cancelled(record.job_id)
        artifact_id = uuid4()
        result = _result(pair, request, record.job_id, artifact_id, record.source_evidence_json)
        await self._stage(record.job_id, "separate_observations_measured", 2)
        await self._cancelled(record.job_id)
        payload = json.dumps(result.model_dump(mode="json"), sort_keys=True).encode("utf-8")
        stored = await asyncio.to_thread(
            self._artifact_store.write_bytes,
            record.job_id,
            artifact_id,
            ".json",
            payload,
            bytes_already_written=0,
        )
        artifact = ArtifactRecord(
            artifact_id=artifact_id,
            job_id=record.job_id,
            owner_id=record.owner_id,
            kind="optical_sar_evidence",
            media_type="application/json",
            storage_key=stored.storage_key,
            checksum_sha256=stored.checksum_sha256,
            byte_size=stored.byte_size,
            state="available",
            created_at=datetime.now(UTC),
        )
        await self._cancelled(record.job_id)
        await self._stage(record.job_id, "evidence_committed", 3)
        await self._repository.succeed_job(
            record.job_id,
            artifacts=(artifact,),
            quality_report={"pair_state": pair.state, "reasons": list(pair.reasons)},
            manifest={
                "artifact_ids": [str(artifact_id)],
                "result": result.model_dump(mode="json"),
                "source_evidence": record.source_evidence_json,
            },
            occurred_at=datetime.now(UTC),
        )

    async def _stage(self, job_id: UUID, name: str, completed: int) -> None:
        await self._repository.update_progress(
            job_id, stage=name, completed_units=completed, occurred_at=datetime.now(UTC)
        )

    async def _cancelled(self, job_id: UUID) -> None:
        if await self._repository.cancellation_requested(job_id):
            await self._repository.mark_cancelled(job_id, datetime.now(UTC))
            raise OpticalSarJobError("JOB_CANCELLED", "The job was cancelled.")

    async def _fail(self, job_id: UUID, code: str, message: str) -> None:
        if code == "JOB_CANCELLED":
            return
        try:
            await self._repository.fail_job(
                job_id,
                code=code[:160].lower().replace(" ", "_"),
                message=message[:1000],
                occurred_at=datetime.now(UTC),
            )
        except ProcessingPersistenceError:
            return


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _evidence_bounds(
    mask: np.ndarray, transform: tuple[float, ...]
) -> tuple[float, float, float, float] | None:
    rows, columns = np.where(mask)
    if len(rows) == 0:
        return None
    affine = Affine(*transform)
    west, north = affine @ (float(columns.min()), float(rows.min()))
    east, south = affine @ (float(columns.max() + 1), float(rows.max() + 1))
    return (min(west, east), min(south, north), max(west, east), max(south, north))


def _result(
    pair: OpticalSarPairOutcome,
    request: OpticalSarAnalysisRequest,
    job_id: UUID,
    artifact_id: UUID,
    source_evidence: list[dict[str, Any]] | None = None,
) -> OpticalSarAnalysisResult:
    optical = pair.grid.scenes[0]
    optical_mask = optical.quality.usable
    sar_mask = pair.sar_valid
    optical_count = int(np.count_nonzero(optical_mask))
    sar_count = int(np.count_nonzero(sar_mask))
    optical_median = float(np.median(optical.data[0][optical_mask])) if optical_count else None
    sar_median = float(np.median(pair.sar_resampled_values[sar_mask])) if sar_count else None
    optical_observation = OpticalSarObservation(
        modality="optical",
        source=pair.optical_source,
        acquired_at=pair.optical_acquired_at,
        layer="Sentinel-2 L2A red surface reflectance",
        measurement_name="median_red_reflectance",
        measured_value=optical_median,
        units="1",
        valid_pixels=optical_count,
        denominator_pixels=pair.coverage.aoi_pixels,
        evidence_bounds=_evidence_bounds(optical_mask, pair.grid.grid.transform),
        evidence_crs=pair.grid.grid.crs if optical_count else None,
        statement=(
            f"Optical SCL-usable pixels cover {optical_count} of "
            f"{pair.coverage.aoi_pixels} AOI cells; median calibrated red reflectance "
            f"is {optical_median:.6g} (unit 1)."
            if optical_median is not None
            else "No optical SCL-usable pixels were measured in the AOI."
        ),
    )
    sar_observation = OpticalSarObservation(
        modality="sar",
        source=pair.sar_source,
        acquired_at=pair.sar_acquired_at,
        layer=f"Sentinel-1 RTC {request.polarization} gamma-0 power",
        measurement_name="median_gamma0_power",
        measured_value=sar_median,
        units="gamma0_power",
        valid_pixels=sar_count,
        denominator_pixels=pair.coverage.aoi_pixels,
        evidence_bounds=_evidence_bounds(sar_mask, pair.grid.grid.transform),
        evidence_crs=pair.grid.grid.crs if sar_count else None,
        statement=(
            f"SAR terrain/nodata-valid pixels cover {sar_count} of "
            f"{pair.coverage.aoi_pixels} AOI cells; median calibrated "
            f"{request.polarization} gamma-0 power is {sar_median:.6g}."
            if sar_median is not None
            else "No valid SAR backscatter was measured in the AOI."
        ),
    )
    limitations = [*pair.reasons, *pair.warnings]
    supported_question = request.question.strip() == SUPPORTED_QUESTION
    if not supported_question:
        limitations.append(
            "The free-text question is not answered by this bounded computed-observation profile."
        )
    answer = (
        (
            f"Optical observation ({pair.optical_acquired_at.date()}, {pair.optical_source.item}): "
            f"{optical_observation.statement} SAR backscatter observation "
            f"({pair.sar_acquired_at.date()}, {pair.sar_source.item}): {sar_observation.statement} "
            f"Joint usable coverage is {pair.coverage.joint_usable_percent:.2f}% of the AOI "
            f"({pair.coverage.joint_usable_area_square_metres:.0f} m²). "
            "Cross-modal agreement, cause, flood extent, and building change are not determined."
        )
        if supported_question
        else (
            "This question is unsupported by the bounded optical/SAR observation profile. "
            "The separate source measurements and their locations are recorded below; "
            "no cross-modal interpretation is asserted."
        )
    )
    return OpticalSarAnalysisResult(
        request_id=request.request_id,
        job_id=job_id,
        state=(
            "limited"
            if supported_question
            and optical_count
            and sar_count
            and pair.coverage.joint_usable_pixels > 0
            and optical.quality.quality_information == "available"
            and pair.coverage.joint_usable_percent >= pair.parameters.min_joint_usable_aoi_percent
            else "insufficient_evidence"
        ),
        answer=answer,
        optical=optical_observation,
        sar=sar_observation,
        source_evidence=(
            OpticalSarSourceEvidence(
                source=pair.optical_source,
                acquired_at=pair.optical_acquired_at,
                source_version=(
                    source_evidence[0].get("version")
                    if source_evidence is not None
                    else optical.bands[0].source.asset_version
                ),
                preparation_version=None,
                checksum=None,
                polarization=None,
            ),
            OpticalSarSourceEvidence(
                source=pair.sar_source,
                acquired_at=pair.sar_acquired_at,
                source_version=None,
                preparation_version=pair.sar_preparation.processing_version,
                checksum=(
                    source_evidence[1].get("checksum")
                    if source_evidence is not None
                    else pair.sar_preparation.source_checksum
                ),
                polarization=request.polarization,
            ),
        ),
        aoi=request.aoi,
        grid=pair.grid.grid,
        joint_usable_pixels=pair.coverage.joint_usable_pixels,
        aoi_pixels=pair.coverage.aoi_pixels,
        joint_usable_percent_of_aoi=pair.coverage.joint_usable_percent,
        joint_usable_area_square_metres=pair.coverage.joint_usable_area_square_metres,
        time_gap_hours=pair.time_gap_hours,
        alignment_state=pair.alignment.state,
        limitations=limitations,
        processing_version=OPTICAL_SAR_JOB_VERSION,
        evidence_artifact_id=artifact_id,
    )
