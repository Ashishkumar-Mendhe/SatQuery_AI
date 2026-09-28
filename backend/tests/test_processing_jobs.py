from __future__ import annotations

import asyncio
import shutil
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

import numpy as np
import pytest
from rasterio.transform import array_bounds, from_origin

import satquery.processing.jobs as jobs_module
from satquery.api.schemas.processing import PreparationRequest
from satquery.api.schemas.viewer import ResolvedImageryAssetIdentity, ViewerSceneIdentity
from satquery.db.processing import (
    ArtifactRecord,
    IdempotencyConflictError,
    JobRecord,
    ProcessingPersistenceError,
    ProcessingPrincipal,
)
from satquery.processing.area import projected_pixel_area_square_metres
from satquery.processing.change import (
    PairObservedCoverage,
    PairPreparationOutcome,
    PairPreparationParameters,
    PairPreparationService,
)
from satquery.processing.change_detection import (
    ChangeClassMeasurement,
    ChangeDetectionParameters,
    OpticalChangeDetectionOutcome,
    OpticalChangeDetector,
)
from satquery.processing.jobs import PreparationJobService, _canonical_request
from satquery.processing.quality import (
    SCL_CLASS_LABELS,
    CoverageStatistic,
    OpticalQualityMasks,
    QualityMaskService,
)
from satquery.processing.raster import (
    BandCalibration,
    CalibratedRasterInput,
    RasterInputError,
    RasterInputService,
)
from satquery.processing.registration import (
    EstimateAgreement,
    PatchDistribution,
    RegistrationAssessment,
    RegistrationResult,
    RegistrationService,
    ResidualAlignmentEvidence,
)
from satquery.storage import AtomicArtifactStore, StorageLimitError

SCENE = ViewerSceneIdentity(
    provider="earth-search", collection="sentinel-2-c1-l2a", item="S2A_synthetic-scene"
)
SCENE_B = ViewerSceneIdentity(
    provider="earth-search", collection="sentinel-2-c1-l2a", item="S2A_synthetic-scene-b"
)
AOI = {
    "type": "Polygon",
    "coordinates": [
        [
            [3.0001, 0.9975],
            [3.007, 0.9975],
            [3.007, 1.004],
            [3.0001, 1.004],
            [3.0001, 0.9975],
        ],
        [[3.002, 1.002], [3.0025, 1.002], [3.0025, 1.0025], [3.002, 1.0025], [3.002, 1.002]],
    ],
}


def _request(*, resolution: float = 10.0) -> PreparationRequest:
    return PreparationRequest.model_validate(
        {
            "scenes": [SCENE.model_dump(mode="json")],
            "aoi": AOI,
            "required_bands": [
                {"role": role, "common_name": role} for role in ("red", "green", "blue")
            ],
            "intended_task": "optical_single_scene",
            "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
            "options": {
                "grid_policy": "common_utm",
                "target_resolution_metres": resolution,
                "continuous_resampling": "bilinear",
                "max_output_pixels": 100_000,
            },
        }
    )


def _pair_request() -> PreparationRequest:
    payload = _request().model_dump(mode="json")
    payload["scenes"] = [
        SCENE.model_dump(mode="json"),
        SCENE_B.model_dump(mode="json"),
    ]
    payload["intended_task"] = "optical_pair"
    return PreparationRequest.model_validate(payload)


def _raster() -> CalibratedRasterInput:
    transform = from_origin(500_000.0, 111_000.0, 10.0, 10.0)
    height = 80
    width = 80
    identity = ResolvedImageryAssetIdentity(scene=SCENE, asset="synthetic", asset_version="v1")
    bands = tuple(
        BandCalibration(
            source=identity,
            role=role,
            band_name=role,
            band_index=index,
            units="1",
            native_resolution_metres=10.0,
            source_nodata=0.0,
            provider_scale=0.0001,
            provider_offset=-0.1,
            applied_scale=0.0001,
            applied_offset=-0.1,
            method="metadata_scale_offset",
        )
        for index, role in enumerate(("red", "green", "blue"), start=1)
    )
    raster_bounds = array_bounds(height, width, transform)
    return CalibratedRasterInput(
        scene=SCENE,
        data=np.full((3, height, width), 0.2, dtype=np.float32),
        inside_aoi_mask=np.ones((height, width), dtype=bool),
        band_validity=np.ones((3, height, width), dtype=bool),
        crs="EPSG:32631",
        transform=tuple(transform)[:6],
        bounds=(
            float(raster_bounds[0]),
            float(raster_bounds[1]),
            float(raster_bounds[2]),
            float(raster_bounds[3]),
        ),
        width=width,
        height=height,
        band_order=("red", "green", "blue"),
        bands=bands,
    )


def _raster_for_scene(scene: ViewerSceneIdentity) -> CalibratedRasterInput:
    raster = _raster()
    bands = tuple(
        replace(band, source=band.source.model_copy(update={"scene": scene}))
        for band in raster.bands
    )
    return replace(raster, scene=scene, bands=bands)


def _textured_raster_for_scene(scene: ViewerSceneIdentity) -> CalibratedRasterInput:
    raster = _raster_for_scene(scene)
    rows, columns = np.indices((raster.height, raster.width))
    texture = (0.12 + ((rows * 17 + columns * 29) % 37) / 200.0).astype(np.float32)
    data = np.stack((texture, texture * 0.9, texture * 0.8)).astype(np.float32)
    if scene == SCENE_B:
        data[:, 30:45, 30:45] += 0.12
    return replace(raster, data=data)


def _quality(raster: CalibratedRasterInput) -> OpticalQualityMasks:
    shape = (raster.height, raster.width)
    false = np.zeros(shape, dtype=bool)
    true = np.ones(shape, dtype=bool)
    return OpticalQualityMasks(
        quality_information="available",
        unavailable_reason=None,
        source_asset="synthetic-scl-v1",
        processing_baseline="05.11",
        catalogue_scene_cloud_percent=0.0,
        scl_classes=np.full(shape, 4, dtype=np.uint8),
        class_labels=SCL_CLASS_LABELS,
        outside_aoi=false,
        missing_or_invalid=false,
        clouds_or_cirrus=false,
        cloud_shadows=false,
        cast_shadows=false,
        snow_or_ice=false,
        unknown_quality=false,
        usable=true,
        excluded_any=false,
        coverage=(
            CoverageStatistic(
                "usable", shape[0] * shape[1], "inside_aoi", shape[0] * shape[1], 100.0
            ),
        ),
    )


def _source_evidence() -> list[dict[str, Any]]:
    return [
        {
            "scene": SCENE.model_dump(mode="json"),
            "resolved_asset": {
                "scene": SCENE.model_dump(mode="json"),
                "asset": "synthetic",
                "asset_version": "v1",
            },
            "components": [
                {"identity": {"asset": role, "asset_version": "v1"}, "role": role}
                for role in ("red", "green", "blue")
            ],
            "acquisition": {
                "start": "2026-01-01T00:00:00Z",
                "end": "2026-01-01T00:00:00Z",
            },
        }
    ]


def _pair_source_evidence() -> list[dict[str, Any]]:
    evidence = _source_evidence()
    second = {
        **evidence[0],
        "scene": SCENE_B.model_dump(mode="json"),
        "resolved_asset": {
            **evidence[0]["resolved_asset"],
            "scene": SCENE_B.model_dump(mode="json"),
        },
        "acquisition": {
            "start": "2026-01-11T00:00:00Z",
            "end": "2026-01-11T00:00:00Z",
        },
    }
    return [evidence[0], second]


class MemoryRepository:
    def __init__(self) -> None:
        self.jobs: dict[UUID, JobRecord] = {}
        self.artifacts: dict[UUID, ArtifactRecord] = {}

    async def submit(self, *, record: JobRecord) -> tuple[JobRecord, bool]:
        for existing in self.jobs.values():
            if (
                existing.owner_id == record.owner_id
                and existing.operation == record.operation
                and existing.idempotency_key == record.idempotency_key
            ):
                if existing.request_digest != record.request_digest:
                    raise IdempotencyConflictError
                return existing, False
        self.jobs[record.job_id] = record
        return record, True

    async def find_successful_cache(
        self, principal: ProcessingPrincipal, cache_key: str, operation: str
    ) -> JobRecord | None:
        for record in self.jobs.values():
            has_artifact = any(item.job_id == record.job_id for item in self.artifacts.values())
            if (
                record.owner_id == principal.owner_id
                and record.access_scope == principal.access_scope
                and record.cache_key == cache_key
                and record.operation == operation
                and record.state == "succeeded"
                and record.manifest_json is not None
                and has_artifact
            ):
                return record
        return None

    async def get_job(self, principal: ProcessingPrincipal, job_id: UUID) -> JobRecord | None:
        record = self.jobs.get(job_id)
        if (
            record
            and record.owner_id == principal.owner_id
            and record.access_scope == principal.access_scope
        ):
            return record
        return None

    async def queued_jobs(self, operation: str | None = None) -> tuple[JobRecord, ...]:
        return tuple(
            item
            for item in self.jobs.values()
            if item.state == "queued" and (operation is None or item.operation == operation)
        )

    async def reconcile_interrupted(self, occurred_at: datetime) -> int:
        count = 0
        for identifier, record in tuple(self.jobs.items()):
            if record.state in {"running", "cancelling"}:
                self.jobs[identifier] = replace(
                    record,
                    state="failed",
                    finished_at=occurred_at,
                    error_code="process_interrupted",
                    safe_error_message="The server stopped during this processing attempt.",
                    current_stage="interrupted",
                )
                count += 1
        return count

    async def start_job(self, job_id: UUID, started_at: datetime, total_units: int) -> bool:
        record = self.jobs[job_id]
        if record.state != "queued":
            return False
        self.jobs[job_id] = replace(
            record,
            state="running",
            started_at=started_at,
            attempt=record.attempt + 1,
            current_stage="resolving_sources",
            completed_units=0,
            total_units=total_units,
        )
        return True

    async def update_progress(
        self, job_id: UUID, *, stage: str, completed_units: int, occurred_at: datetime
    ) -> None:
        self.jobs[job_id] = replace(
            self.jobs[job_id], current_stage=stage, completed_units=completed_units
        )

    async def cancellation_requested(self, job_id: UUID) -> bool:
        return self.jobs[job_id].state == "cancelling"

    async def request_cancel(
        self, principal: ProcessingPrincipal, job_id: UUID, occurred_at: datetime
    ) -> JobRecord | None:
        record = await self.get_job(principal, job_id)
        if record is None:
            return None
        if record.state == "queued":
            record = replace(
                record, state="cancelled", finished_at=occurred_at, current_stage="cancelled"
            )
        elif record.state == "running":
            record = replace(record, state="cancelling")
        self.jobs[job_id] = record
        return record

    async def mark_cancelled(self, job_id: UUID, occurred_at: datetime) -> None:
        self.jobs[job_id] = replace(
            self.jobs[job_id], state="cancelled", finished_at=occurred_at, current_stage="cancelled"
        )

    async def fail_job(
        self, job_id: UUID, *, code: str, message: str, occurred_at: datetime
    ) -> None:
        if self.jobs[job_id].state != "cancelled":
            self.jobs[job_id] = replace(
                self.jobs[job_id],
                state="failed",
                finished_at=occurred_at,
                current_stage="failed",
                error_code=code,
                safe_error_message=message,
            )

    async def succeed_job(
        self,
        job_id: UUID,
        *,
        artifacts: tuple[ArtifactRecord, ...],
        quality_report: dict[str, Any],
        manifest: dict[str, Any],
        occurred_at: datetime,
    ) -> None:
        if self.jobs[job_id].state != "running":
            raise RuntimeError
        self.artifacts.update({item.artifact_id: item for item in artifacts})
        self.jobs[job_id] = replace(
            self.jobs[job_id],
            state="succeeded",
            finished_at=occurred_at,
            current_stage="complete",
            completed_units=self.jobs[job_id].total_units,
            quality_report_json=quality_report,
            manifest_json=manifest,
        )

    async def artifacts_for_job(
        self, principal: ProcessingPrincipal, job_id: UUID
    ) -> tuple[ArtifactRecord, ...]:
        job = await self.get_job(principal, job_id)
        if job is None or job.state != "succeeded":
            return ()
        return tuple(item for item in self.artifacts.values() if item.job_id == job_id)

    async def get_artifact(
        self, principal: ProcessingPrincipal, artifact_id: UUID
    ) -> ArtifactRecord | None:
        artifact = self.artifacts.get(artifact_id)
        if artifact is None:
            return None
        return artifact if await self.get_job(principal, artifact.job_id) is not None else None


class UnusedProvider:
    pass


async def _wait_terminal(repository: MemoryRepository, job_id: UUID) -> JobRecord:
    for _ in range(100):
        record = repository.jobs[job_id]
        if record.state in {"succeeded", "failed", "cancelled"}:
            return record
        await asyncio.sleep(0.01)
    raise AssertionError("job did not reach a terminal state")


def _artifact_root() -> Path:
    root = Path.cwd() / ".test-processing-artifacts" / str(uuid4())
    root.mkdir(parents=True)
    return root


def test_job_runs_stages_writes_atomic_artifacts_and_reuses_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _artifact_root()
    try:
        asyncio.run(_run_success_case(monkeypatch, root))
    finally:
        shutil.rmtree(root)


async def _run_success_case(monkeypatch: pytest.MonkeyPatch, artifact_root: Path) -> None:
    async def evidence(*args: object, **kwargs: object) -> list[dict[str, Any]]:
        return _source_evidence()

    async def extract(*args: object, **kwargs: object) -> CalibratedRasterInput:
        return _raster()

    async def decode(_service: object, raster: CalibratedRasterInput) -> OpticalQualityMasks:
        return _quality(raster)

    monkeypatch.setattr(jobs_module, "_resolve_source_evidence", evidence)
    monkeypatch.setattr(RasterInputService, "extract", extract)
    monkeypatch.setattr(QualityMaskService, "decode", decode)
    repository = MemoryRepository()
    store = AtomicArtifactStore(artifact_root, max_job_bytes=16 * 1024 * 1024)
    service = PreparationJobService(repository, UnusedProvider(), store)  # type: ignore[arg-type]
    principal = ProcessingPrincipal(uuid4(), "owner:synthetic")

    submitted = await service.submit(principal, _request(), idempotency_key="repeat-1")
    terminal = await _wait_terminal(repository, submitted.job_id)
    assert terminal.state == "succeeded", (
        terminal.error_code,
        terminal.safe_error_message,
    )
    assert terminal.completed_units == terminal.total_units == 6
    status = await service.status(principal, submitted.job_id)
    assert status.current_stage == "complete"
    assert len(status.artifacts) == 4
    assert {item.kind for item in status.artifacts} == {
        "prepared_raster",
        "validity_mask",
        "quality_mask",
        "provenance_manifest",
    }
    assert all(
        (artifact_root / item.storage_key).is_file() for item in repository.artifacts.values()
    )
    report = await service.quality_report(principal, submitted.job_id)
    assert report["threshold_version"] == "provisional-engineering-v1"
    assert report["requested_spatial_scale_metres"] is None
    manifest = terminal.manifest_json
    assert manifest is not None
    assert manifest["normalization"] == {"applied": False, "parameters": None}
    assert manifest["scenes"][0]["calibration"][0]["applied_scale"] == 0.0001
    first_artifact = next(iter(repository.artifacts.values()))
    _, stream = await service.artifact(principal, first_artifact.artifact_id)
    try:
        assert stream.read(4) in {b"II*\x00", b"MM\x00*"}
    finally:
        stream.close()
    with pytest.raises(jobs_module.JobNotFoundError):
        await service.status(ProcessingPrincipal(uuid4(), "owner:other"), submitted.job_id)
    with pytest.raises(jobs_module.JobNotFoundError):
        await service.artifact(
            ProcessingPrincipal(uuid4(), "owner:other"), first_artifact.artifact_id
        )
    quality_artifact = next(
        item for item in repository.artifacts.values() if item.kind == "quality_mask"
    )
    usable_tile = await service.mask_tile(
        principal, quality_artifact.artifact_id, "usable", 0, 0, 0
    )
    exclusion_tile = await service.mask_tile(
        principal, quality_artifact.artifact_id, "exclusions", 0, 0, 0
    )
    assert usable_tile.startswith(b"\x89PNG\r\n\x1a\n")
    assert exclusion_tile.startswith(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(jobs_module.JobNotFoundError):
        await service.mask_tile(
            ProcessingPrincipal(uuid4(), "owner:other"),
            quality_artifact.artifact_id,
            "usable",
            0,
            0,
            0,
        )

    repeated = await service.submit(principal, _request(), idempotency_key="repeat-2")
    assert repeated.job_id == submitted.job_id
    changed = await service.submit(
        principal, _request(resolution=20.0), idempotency_key="changed-resolution"
    )
    assert changed.job_id != submitted.job_id
    (artifact_root / first_artifact.storage_key).unlink()
    with pytest.raises(ProcessingPersistenceError):
        await service.status(principal, submitted.job_id)
    await service.stop()


def test_pair_job_records_common_grid_masks_registration_and_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _artifact_root()
    try:
        asyncio.run(_run_pair_case(monkeypatch, root))
    finally:
        shutil.rmtree(root)


def test_change_job_commits_computed_result_and_authorized_tile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _artifact_root()
    try:
        asyncio.run(_run_change_case(monkeypatch, root))
    finally:
        shutil.rmtree(root)


async def _run_change_case(monkeypatch: pytest.MonkeyPatch, artifact_root: Path) -> None:
    async def evidence(*args: object, **kwargs: object) -> list[dict[str, Any]]:
        return _pair_source_evidence()

    async def extract(_service: object, request: PreparationRequest) -> CalibratedRasterInput:
        return _textured_raster_for_scene(request.scenes[0])

    async def decode(_service: object, raster: CalibratedRasterInput) -> OpticalQualityMasks:
        return _quality(raster)

    monkeypatch.setattr(jobs_module, "_resolve_source_evidence", evidence)
    monkeypatch.setattr(RasterInputService, "extract", extract)
    monkeypatch.setattr(QualityMaskService, "decode", decode)

    def reliable(_service: object, grid: Any) -> RegistrationResult:
        assessment = RegistrationAssessment(
            state="reliable",
            explanation="Synthetic distributed registration evidence.",
            method="distributed_masked_zncc_integer_translation",
            coordinate_convention="moving image to reference image",
            band_role="red",
            estimated_row_shift_pixels=0,
            estimated_column_shift_pixels=0,
            estimated_x_shift_map_units=0.0,
            estimated_y_shift_map_units=0.0,
            map_displacement_units="metres",
            patches=(),
            distribution=PatchDistribution(9, 9, 5, 4, 3, 3, (2 / 3, 2 / 3)),
            agreement=EstimateAgreement(5, 5, 1.0, 0.75, 0.0, 0.0, 0.0, True),
            residual=ResidualAlignmentEvidence(4, 1.0, 1.0, 0.0, 0, 0.03, False),
            correction_state="not_needed",
            correction=None,
        )
        return RegistrationResult(grid, assessment, None, None, None, ())

    monkeypatch.setattr(RegistrationService, "assess_and_correct", reliable)

    def comparable(
        _service: object,
        request: PreparationRequest,
        grid: Any,
        registration: RegistrationResult,
        acquisitions: tuple[Any, ...],
    ) -> PairPreparationOutcome:
        usable = grid.aoi_mask.copy()
        pixels = int(usable.sum())
        pixel_area = projected_pixel_area_square_metres(grid.grid)
        return PairPreparationOutcome(
            state="comparable",
            comparison_allowed=True,
            processing_version="8b-pair-preparation-v1",
            parameters=PairPreparationParameters(),
            sources=(request.scenes[0], request.scenes[1]),
            acquired_at=(acquisitions[0].acquired_at, acquisitions[1].acquired_at),
            band_order=("red", "green", "blue"),
            grid=grid.grid,
            registration_state=registration.assessment.state,
            correction_state=registration.assessment.correction_state,
            joint_valid=usable,
            joint_usable=usable,
            coverage=PairObservedCoverage(
                "inside_aoi",
                pixels,
                pixels,
                100.0,
                pixels,
                100.0,
                pixel_area,
                pixels * pixel_area,
                pixels * pixel_area,
            ),
            reasons=(),
        )

    monkeypatch.setattr(PairPreparationService, "prepare", comparable)

    def detect(
        _service: object,
        pair: PairPreparationOutcome,
        grid: Any,
        _registration: RegistrationResult,
    ) -> OpticalChangeDetectionOutcome:
        classification = np.full(grid.aoi_mask.shape, 255, dtype=np.uint8)
        classification[pair.joint_usable] = 0
        rows, columns = np.where(pair.joint_usable)
        changed_locations = (rows[: min(25, len(rows))], columns[: min(25, len(columns))])
        classification[changed_locations] = 1
        changed = int(np.count_nonzero(classification == 1))
        unchanged = int(np.count_nonzero(classification == 0))
        unknown = int(grid.aoi_mask.sum()) - changed - unchanged
        pixel_area = projected_pixel_area_square_metres(grid.grid)
        aoi_pixels = int(grid.aoi_mask.sum())
        usable_pixels = int(pair.joint_usable.sum())

        def measurement(
            name: Literal["unchanged", "changed", "unknown"], value: int, count: int
        ) -> ChangeClassMeasurement:
            return ChangeClassMeasurement(
                name,
                value,
                count,
                count * pixel_area,
                count / aoi_pixels,
                count / usable_pixels if name != "unknown" else None,
            )

        return OpticalChangeDetectionOutcome(
            state="completed",
            processing_version="8c-calibrated-rgb-rms-v1",
            parameters=ChangeDetectionParameters(),
            sources=pair.sources,
            acquired_at=pair.acquired_at,
            pair_processing_version=pair.processing_version,
            classification=classification,
            spectral_difference=np.zeros(classification.shape, dtype=np.float32),
            classes=(
                measurement("unchanged", 0, unchanged),
                measurement("changed", 1, changed),
                measurement("unknown", 255, unknown),
            ),
            reasons=(),
            interpretation="Synthetic integration classification.",
        )

    monkeypatch.setattr(OpticalChangeDetector, "detect", detect)
    repository = MemoryRepository()
    service = PreparationJobService(
        repository,
        UnusedProvider(),  # type: ignore[arg-type]
        AtomicArtifactStore(artifact_root, max_job_bytes=16 * 1024 * 1024),
    )
    principal = ProcessingPrincipal(uuid4(), "owner:synthetic-change")
    submitted = await service.submit_change(principal, _pair_request(), idempotency_key="change-1")
    terminal = await _wait_terminal(repository, submitted.job_id)
    assert terminal.state == "succeeded", (terminal.error_code, terminal.safe_error_message)
    assert terminal.completed_units == terminal.total_units == 11
    result = await service.change_result(principal, submitted.job_id)
    assert result["cause_or_land_cover_category"] == "not_determined"
    assert result["area"]["changed_area_square_metres"] > 0
    assert [item["scene"] for item in result["sources"]] == [
        SCENE.model_dump(mode="json"),
        SCENE_B.model_dump(mode="json"),
    ]
    assert result["aoi"] == _pair_request().aoi.model_dump(mode="json")
    assert result["method_version"] == "8c-calibrated-rgb-rms-v1"
    assert result["processing_version"] == jobs_module.PROCESSING_CODE_VERSION
    expected_percent = (
        100
        * result["area"]["changed_area_square_metres"]
        / result["area"]["joint_valid_observed_area_square_metres"]
    )
    assert result["area"]["changed_percent_of_joint_valid_observed_area"] == pytest.approx(
        expected_percent
    )
    artifact = next(
        item for item in repository.artifacts.values() if item.kind == "change_classification"
    )
    tile = await service.change_tile(principal, artifact.artifact_id, 0, 0, 0)
    assert tile.startswith(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(jobs_module.JobNotFoundError):
        await service.change_result(ProcessingPrincipal(uuid4(), "owner:other"), submitted.job_id)
    await service.stop()


async def _run_pair_case(monkeypatch: pytest.MonkeyPatch, artifact_root: Path) -> None:
    async def evidence(*args: object, **kwargs: object) -> list[dict[str, Any]]:
        return _pair_source_evidence()

    async def extract(_service: object, request: PreparationRequest) -> CalibratedRasterInput:
        return _raster_for_scene(request.scenes[0])

    async def decode(_service: object, raster: CalibratedRasterInput) -> OpticalQualityMasks:
        return _quality(raster)

    monkeypatch.setattr(jobs_module, "_resolve_source_evidence", evidence)
    monkeypatch.setattr(RasterInputService, "extract", extract)
    monkeypatch.setattr(QualityMaskService, "decode", decode)
    repository = MemoryRepository()
    service = PreparationJobService(
        repository,
        UnusedProvider(),  # type: ignore[arg-type]
        AtomicArtifactStore(artifact_root, max_job_bytes=16 * 1024 * 1024),
    )
    principal = ProcessingPrincipal(uuid4(), "owner:synthetic-pair")

    submitted = await service.submit(principal, _pair_request(), idempotency_key="pair-1")
    terminal = await _wait_terminal(repository, submitted.job_id)

    assert terminal.state == "succeeded", (
        terminal.error_code,
        terminal.safe_error_message,
    )
    assert terminal.completed_units == terminal.total_units == 9
    status = await service.status(principal, submitted.job_id)
    assert len(status.artifacts) == 8
    manifest = terminal.manifest_json
    assert manifest is not None
    assert manifest["request"]["intended_task"] == "optical_pair"
    assert len(manifest["scenes"]) == 2
    assert manifest["grid"]["crs"] == "EPSG:32631"
    assert manifest["pair_masks_artifact_id"] is not None
    assert manifest["registration"]["state"] == "inconclusive"
    assert manifest["registration"]["correction"] is None
    assert manifest["scientific_validity"]["readiness"] == "not_ready"
    assert "registration_evidence" in manifest["scientific_validity"]["blocking_check_ids"]
    assert manifest["comparison_preparation"]["state"] == "rejected"
    assert manifest["comparison_preparation"]["comparison_allowed"] is False
    assert {reason["code"] for reason in manifest["comparison_preparation"]["reasons"]} >= {
        "registration_unreliable"
    }
    assert (
        manifest["comparison_preparation"]["joint_masks_artifact_id"]
        == manifest["pair_masks_artifact_id"]
    )
    assert manifest["comparison_preparation"]["change_classification_artifact_id"] is None
    assert all(scene["calibration"][0]["applied_scale"] == 0.0001 for scene in manifest["scenes"])
    assert {item["name"] for item in manifest["pair_coverage"]} == {
        "joint_valid_overlap",
        "joint_usable_inside_aoi",
        "joint_usable_within_valid_overlap",
    }

    repeated = await service.submit(principal, _pair_request(), idempotency_key="pair-2")
    assert repeated.job_id == submitted.job_id
    await service.stop()


def test_failed_stage_is_terminal_without_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _artifact_root()
    try:
        asyncio.run(_run_failed_stage_case(monkeypatch, root))
    finally:
        shutil.rmtree(root)


async def _run_failed_stage_case(monkeypatch: pytest.MonkeyPatch, artifact_root: Path) -> None:
    async def evidence(*args: object, **kwargs: object) -> list[dict[str, Any]]:
        return _source_evidence()

    async def fail_extract(*args: object, **kwargs: object) -> CalibratedRasterInput:
        raise RasterInputError("RASTER_READ_FAILED", "Synthetic failed stage.")

    monkeypatch.setattr(jobs_module, "_resolve_source_evidence", evidence)
    monkeypatch.setattr(RasterInputService, "extract", fail_extract)
    repository = MemoryRepository()
    service = PreparationJobService(
        repository,
        UnusedProvider(),  # type: ignore[arg-type]
        AtomicArtifactStore(artifact_root, max_job_bytes=16 * 1024 * 1024),
    )
    principal = ProcessingPrincipal(uuid4(), "owner:synthetic")
    job = await service.submit(principal, _request(), idempotency_key="failed-stage")
    terminal = await _wait_terminal(repository, job.job_id)
    assert terminal.state == "failed"
    assert terminal.error_code == "raster_read_failed"
    assert not repository.artifacts


def test_restart_reconciles_interrupted_and_incomplete_cache_is_not_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _artifact_root()
    try:
        asyncio.run(_run_restart_case(monkeypatch, root))
    finally:
        shutil.rmtree(root)


async def _run_restart_case(monkeypatch: pytest.MonkeyPatch, artifact_root: Path) -> None:
    async def evidence(*args: object, **kwargs: object) -> list[dict[str, Any]]:
        return _source_evidence()

    monkeypatch.setattr(jobs_module, "_resolve_source_evidence", evidence)
    repository = MemoryRepository()
    principal = ProcessingPrincipal(uuid4(), "owner:synthetic")
    now = datetime.now(UTC)
    interrupted = JobRecord(
        job_id=uuid4(),
        owner_id=principal.owner_id,
        access_scope=principal.access_scope,
        operation="prepare_optical",
        operation_version="6g-v1",
        idempotency_key="old",
        request_digest="a" * 64,
        cache_key="b" * 64,
        request_json=_request().model_dump(mode="json"),
        source_evidence_json=_source_evidence(),
        state="running",
        current_stage="common_grid_prepared",
        completed_units=3,
        total_units=6,
        attempt=1,
        submitted_at=now,
        started_at=now,
        finished_at=None,
        error_code=None,
        safe_error_message=None,
        quality_report_json=None,
        manifest_json=None,
    )
    repository.jobs[interrupted.job_id] = interrupted
    service = PreparationJobService(
        repository,
        UnusedProvider(),  # type: ignore[arg-type]
        AtomicArtifactStore(artifact_root, max_job_bytes=16 * 1024 * 1024),
    )
    await service.start()
    assert repository.jobs[interrupted.job_id].state == "failed"
    assert repository.jobs[interrupted.job_id].error_code == "process_interrupted"

    queued = replace(
        interrupted,
        job_id=uuid4(),
        idempotency_key="cancel-me",
        state="queued",
        current_stage=None,
        completed_units=None,
        total_units=None,
        attempt=0,
        started_at=None,
    )
    repository.jobs[queued.job_id] = queued
    cancelled = await service.cancel(principal, queued.job_id)
    assert cancelled.state == "cancelled"
    assert cancelled.started_at is None

    incomplete = replace(
        interrupted,
        job_id=uuid4(),
        idempotency_key="incomplete",
        state="succeeded",
        finished_at=now,
        error_code=None,
        safe_error_message=None,
        manifest_json={"incomplete": True},
    )
    # An incomplete entry has no committed artifact rows, so it cannot satisfy cache lookup.
    repository.jobs[incomplete.job_id] = incomplete
    submitted = await service.submit(principal, _request(), idempotency_key="new-after-incomplete")
    assert submitted.job_id != incomplete.job_id
    await service.stop()


def test_canonical_aoi_identity_preserves_holes_and_ignores_ring_start_direction() -> None:
    original = _request()
    payload = original.model_dump(mode="json")
    exterior = payload["aoi"]["coordinates"][0]
    hole = payload["aoi"]["coordinates"][1]
    rotated_exterior = exterior[2:-1] + exterior[:2]
    rotated_hole = hole[1:-1] + hole[:1]
    payload["aoi"]["coordinates"] = [
        list(reversed(rotated_exterior)),
        list(reversed(rotated_hole)),
    ]
    for ring in payload["aoi"]["coordinates"]:
        ring.append(ring[0])
    equivalent = PreparationRequest.model_validate(payload)
    assert _canonical_request(original)["aoi"] == _canonical_request(equivalent)["aoi"]


def test_atomic_store_rejects_limit_without_publishing_partial_artifact() -> None:
    root = _artifact_root()
    try:
        store = AtomicArtifactStore(root, max_job_bytes=3)
        with pytest.raises(StorageLimitError):
            store.write_bytes(uuid4(), uuid4(), ".bin", b"four", bytes_already_written=0)
        assert not tuple(root.rglob("*"))
    finally:
        shutil.rmtree(root)
