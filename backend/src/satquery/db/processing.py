from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import CursorResult, RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from satquery.db.session import Database

JobState = Literal["queued", "running", "cancelling", "succeeded", "failed", "cancelled"]
JobOperation = Literal[
    "prepare_optical", "infer_single_image", "analyze_change", "analyze_optical_sar"
]
ArtifactKind = Literal[
    "prepared_raster",
    "validity_mask",
    "quality_mask",
    "provenance_manifest",
    "inference_evidence",
    "inference_chip",
    "change_classification",
    "optical_sar_evidence",
]


class ProcessingPersistenceError(RuntimeError):
    """Safe durable-processing persistence failure."""


class IdempotencyConflictError(RuntimeError):
    """An idempotency key was reused for a different canonical request."""


@dataclass(frozen=True, slots=True)
class ProcessingPrincipal:
    owner_id: UUID
    access_scope: str


@dataclass(frozen=True, slots=True)
class JobRecord:
    job_id: UUID
    owner_id: UUID
    access_scope: str
    operation: JobOperation
    operation_version: str
    idempotency_key: str
    request_digest: str
    cache_key: str
    request_json: dict[str, Any]
    source_evidence_json: list[dict[str, Any]]
    state: JobState
    current_stage: str | None
    completed_units: int | None
    total_units: int | None
    attempt: int
    submitted_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    safe_error_message: str | None
    quality_report_json: dict[str, Any] | None
    manifest_json: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: UUID
    job_id: UUID
    owner_id: UUID
    kind: ArtifactKind
    media_type: str
    storage_key: str
    checksum_sha256: str
    byte_size: int
    state: Literal["available", "quarantined"]
    created_at: datetime


class ProcessingRepository(Protocol):
    async def submit(
        self,
        *,
        record: JobRecord,
    ) -> tuple[JobRecord, bool]: ...

    async def find_successful_cache(
        self, principal: ProcessingPrincipal, cache_key: str, operation: JobOperation
    ) -> JobRecord | None: ...

    async def get_job(self, principal: ProcessingPrincipal, job_id: UUID) -> JobRecord | None: ...

    async def queued_jobs(self, operation: JobOperation | None = None) -> tuple[JobRecord, ...]: ...

    async def reconcile_interrupted(self, occurred_at: datetime) -> int: ...

    async def start_job(self, job_id: UUID, started_at: datetime, total_units: int) -> bool: ...

    async def update_progress(
        self, job_id: UUID, *, stage: str, completed_units: int, occurred_at: datetime
    ) -> None: ...

    async def cancellation_requested(self, job_id: UUID) -> bool: ...

    async def request_cancel(
        self, principal: ProcessingPrincipal, job_id: UUID, occurred_at: datetime
    ) -> JobRecord | None: ...

    async def mark_cancelled(self, job_id: UUID, occurred_at: datetime) -> None: ...

    async def fail_job(
        self, job_id: UUID, *, code: str, message: str, occurred_at: datetime
    ) -> None: ...

    async def succeed_job(
        self,
        job_id: UUID,
        *,
        artifacts: tuple[ArtifactRecord, ...],
        quality_report: dict[str, Any],
        manifest: dict[str, Any],
        occurred_at: datetime,
    ) -> None: ...

    async def artifacts_for_job(
        self, principal: ProcessingPrincipal, job_id: UUID
    ) -> tuple[ArtifactRecord, ...]: ...

    async def get_artifact(
        self, principal: ProcessingPrincipal, artifact_id: UUID
    ) -> ArtifactRecord | None: ...


class PostgresProcessingRepository:
    """SQL-backed job state; every protected lookup is owner and scope constrained."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def submit(self, *, record: JobRecord) -> tuple[JobRecord, bool]:
        statement = text(
            """
            INSERT INTO processing_jobs (
                id, owner_id, access_scope, operation, operation_version, idempotency_key,
                request_digest, cache_key, request_json, source_evidence_json, state,
                current_stage, completed_units, total_units, attempt, submitted_at
            ) VALUES (
                :id, :owner_id, :access_scope, :operation, :operation_version, :idempotency_key,
                :request_digest, :cache_key, CAST(:request_json AS jsonb),
                CAST(:source_evidence_json AS jsonb), 'queued', NULL, NULL, NULL, 0, :submitted_at
            )
            """
        )
        import json

        try:
            async with self._database.session() as session:
                await session.execute(
                    statement,
                    {
                        "id": record.job_id,
                        "owner_id": record.owner_id,
                        "access_scope": record.access_scope,
                        "operation": record.operation,
                        "operation_version": record.operation_version,
                        "idempotency_key": record.idempotency_key,
                        "request_digest": record.request_digest,
                        "cache_key": record.cache_key,
                        "request_json": json.dumps(record.request_json, separators=(",", ":")),
                        "source_evidence_json": json.dumps(
                            record.source_evidence_json, separators=(",", ":")
                        ),
                        "submitted_at": record.submitted_at,
                    },
                )
                await session.commit()
            return record, True
        except IntegrityError:
            existing = await self._get_by_idempotency(
                record.owner_id, record.operation, record.idempotency_key
            )
            if existing is None:
                raise ProcessingPersistenceError("Processing job submission failed.") from None
            if existing.request_digest != record.request_digest:
                raise IdempotencyConflictError(
                    "The idempotency key was already used for a different processing request."
                ) from None
            return existing, False
        except SQLAlchemyError as exc:
            raise ProcessingPersistenceError("Processing job submission failed.") from exc

    async def find_successful_cache(
        self, principal: ProcessingPrincipal, cache_key: str, operation: JobOperation
    ) -> JobRecord | None:
        return await self._one(
            """
            SELECT * FROM processing_jobs
            WHERE owner_id=:owner_id AND access_scope=:access_scope AND cache_key=:cache_key
              AND operation=:operation
              AND state='succeeded' AND manifest_json IS NOT NULL
              AND EXISTS (
                SELECT 1 FROM processing_artifacts a
                WHERE a.job_id=processing_jobs.id AND a.state='available'
              )
            ORDER BY finished_at DESC LIMIT 1
            """,
            {
                "owner_id": principal.owner_id,
                "access_scope": principal.access_scope,
                "cache_key": cache_key,
                "operation": operation,
            },
        )

    async def get_job(self, principal: ProcessingPrincipal, job_id: UUID) -> JobRecord | None:
        return await self._one(
            "SELECT * FROM processing_jobs WHERE id=:id AND owner_id=:owner_id "
            "AND access_scope=:access_scope",
            {
                "id": job_id,
                "owner_id": principal.owner_id,
                "access_scope": principal.access_scope,
            },
        )

    async def queued_jobs(self, operation: JobOperation | None = None) -> tuple[JobRecord, ...]:
        if operation is None:
            return await self._many(
                "SELECT * FROM processing_jobs WHERE state='queued' ORDER BY submitted_at, id", {}
            )
        return await self._many(
            "SELECT * FROM processing_jobs WHERE state='queued' AND operation=:operation "
            "ORDER BY submitted_at, id",
            {"operation": operation},
        )

    async def reconcile_interrupted(self, occurred_at: datetime) -> int:
        try:
            async with self._database.session() as session:
                result = await session.execute(
                    text(
                        """
                        UPDATE processing_jobs SET state='failed', finished_at=:at,
                          error_code='process_interrupted',
                          safe_error_message='The server stopped during this processing attempt.',
                          current_stage='interrupted'
                        WHERE state IN ('running','cancelling')
                        """
                    ),
                    {"at": occurred_at},
                )
                await session.commit()
                return int(cast(CursorResult[Any], result).rowcount or 0)
        except SQLAlchemyError as exc:
            raise ProcessingPersistenceError("Interrupted job reconciliation failed.") from exc

    async def start_job(self, job_id: UUID, started_at: datetime, total_units: int) -> bool:
        return await self._transition(
            """
            UPDATE processing_jobs SET state='running', started_at=:at, attempt=attempt+1,
              current_stage='resolving_sources', completed_units=0, total_units=:total
            WHERE id=:id AND state='queued'
            """,
            {"id": job_id, "at": started_at, "total": total_units},
        )

    async def update_progress(
        self, job_id: UUID, *, stage: str, completed_units: int, occurred_at: datetime
    ) -> None:
        await self._execute(
            """
            UPDATE processing_jobs SET current_stage=:stage, completed_units=:completed
            WHERE id=:id AND state IN ('running','cancelling')
            """,
            {"id": job_id, "stage": stage, "completed": completed_units},
        )
        await self._event(
            job_id, "stage_completed", stage, {"completed_units": completed_units}, occurred_at
        )

    async def cancellation_requested(self, job_id: UUID) -> bool:
        row = await self._mapping("SELECT state FROM processing_jobs WHERE id=:id", {"id": job_id})
        return row is not None and row["state"] == "cancelling"

    async def request_cancel(
        self, principal: ProcessingPrincipal, job_id: UUID, occurred_at: datetime
    ) -> JobRecord | None:
        await self._execute(
            """
            UPDATE processing_jobs SET
              state=CASE WHEN state='queued' THEN 'cancelled' ELSE 'cancelling' END,
              finished_at=CASE WHEN state='queued' THEN :at ELSE finished_at END,
              current_stage=CASE WHEN state='queued' THEN 'cancelled' ELSE current_stage END
            WHERE id=:id AND owner_id=:owner_id AND access_scope=:access_scope
              AND state IN ('queued','running')
            """,
            {
                "id": job_id,
                "owner_id": principal.owner_id,
                "access_scope": principal.access_scope,
                "at": occurred_at,
            },
        )
        return await self.get_job(principal, job_id)

    async def mark_cancelled(self, job_id: UUID, occurred_at: datetime) -> None:
        await self._execute(
            """
            UPDATE processing_jobs SET state='cancelled', finished_at=:at,
              current_stage='cancelled' WHERE id=:id AND state='cancelling'
            """,
            {"id": job_id, "at": occurred_at},
        )

    async def fail_job(
        self, job_id: UUID, *, code: str, message: str, occurred_at: datetime
    ) -> None:
        await self._execute(
            """
            UPDATE processing_jobs SET state='failed', finished_at=:at, error_code=:code,
              safe_error_message=:message, current_stage='failed'
            WHERE id=:id AND state IN ('queued','running','cancelling')
            """,
            {"id": job_id, "at": occurred_at, "code": code, "message": message},
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
        import json

        try:
            async with self._database.session() as session:
                state = (
                    await session.execute(
                        text("SELECT state FROM processing_jobs WHERE id=:id FOR UPDATE"),
                        {"id": job_id},
                    )
                ).scalar_one_or_none()
                if state != "running":
                    raise ProcessingPersistenceError(
                        "Processing completion was rejected because the job is not running."
                    )
                for artifact in artifacts:
                    await session.execute(
                        text(
                            """
                            INSERT INTO processing_artifacts (
                              id, job_id, owner_id, kind, media_type, storage_key,
                              checksum_sha256, byte_size, state, created_at
                            ) VALUES (
                              :id, :job_id, :owner_id, :kind, :media_type, :storage_key,
                              :checksum, :byte_size, 'available', :created_at
                            )
                            """
                        ),
                        {
                            "id": artifact.artifact_id,
                            "job_id": job_id,
                            "owner_id": artifact.owner_id,
                            "kind": artifact.kind,
                            "media_type": artifact.media_type,
                            "storage_key": artifact.storage_key,
                            "checksum": artifact.checksum_sha256,
                            "byte_size": artifact.byte_size,
                            "created_at": artifact.created_at,
                        },
                    )
                await session.execute(
                    text(
                        """
                        UPDATE processing_jobs SET state='succeeded', finished_at=:at,
                          current_stage='complete', completed_units=total_units,
                          quality_report_json=CAST(:quality AS jsonb),
                          manifest_json=CAST(:manifest AS jsonb)
                        WHERE id=:id
                        """
                    ),
                    {
                        "id": job_id,
                        "at": occurred_at,
                        "quality": json.dumps(quality_report, separators=(",", ":")),
                        "manifest": json.dumps(manifest, separators=(",", ":")),
                    },
                )
                await session.commit()
        except ProcessingPersistenceError:
            raise
        except SQLAlchemyError as exc:
            raise ProcessingPersistenceError(
                "Processing completion could not be committed."
            ) from exc

    async def artifacts_for_job(
        self, principal: ProcessingPrincipal, job_id: UUID
    ) -> tuple[ArtifactRecord, ...]:
        rows = await self._artifact_many(
            """
            SELECT a.* FROM processing_artifacts a JOIN processing_jobs j ON j.id=a.job_id
            WHERE a.job_id=:job_id AND a.owner_id=:owner_id AND j.access_scope=:access_scope
              AND j.state='succeeded' AND a.state='available'
            ORDER BY a.created_at, a.id
            """,
            {
                "job_id": job_id,
                "owner_id": principal.owner_id,
                "access_scope": principal.access_scope,
            },
        )
        return rows

    async def get_artifact(
        self, principal: ProcessingPrincipal, artifact_id: UUID
    ) -> ArtifactRecord | None:
        rows = await self._artifact_many(
            """
            SELECT a.* FROM processing_artifacts a JOIN processing_jobs j ON j.id=a.job_id
            WHERE a.id=:id AND a.owner_id=:owner_id AND j.access_scope=:access_scope
              AND j.state='succeeded' AND a.state='available'
            """,
            {
                "id": artifact_id,
                "owner_id": principal.owner_id,
                "access_scope": principal.access_scope,
            },
        )
        return rows[0] if rows else None

    async def _get_by_idempotency(
        self, owner_id: UUID, operation: JobOperation, key: str
    ) -> JobRecord | None:
        return await self._one(
            "SELECT * FROM processing_jobs WHERE owner_id=:owner_id "
            "AND operation=:operation "
            "AND idempotency_key=:key",
            {"owner_id": owner_id, "operation": operation, "key": key},
        )

    async def _transition(self, sql: str, parameters: dict[str, Any]) -> bool:
        try:
            async with self._database.session() as session:
                result = await session.execute(text(sql), parameters)
                await session.commit()
                return bool(cast(CursorResult[Any], result).rowcount)
        except SQLAlchemyError as exc:
            raise ProcessingPersistenceError("Processing job state update failed.") from exc

    async def _execute(self, sql: str, parameters: dict[str, Any]) -> None:
        await self._transition(sql, parameters)

    async def _event(
        self,
        job_id: UUID,
        event_type: str,
        stage: str | None,
        details: dict[str, Any],
        occurred_at: datetime,
    ) -> None:
        import json

        await self._execute(
            """
            INSERT INTO processing_job_events (
              job_id, sequence, event_type, stage, details_json, occurred_at
            )
            SELECT :id, COALESCE(MAX(sequence),0)+1, :event_type, :stage,
              CAST(:details AS jsonb), :at FROM processing_job_events WHERE job_id=:id
            """,
            {
                "id": job_id,
                "event_type": event_type,
                "stage": stage,
                "details": json.dumps(details, separators=(",", ":")),
                "at": occurred_at,
            },
        )

    async def _mapping(self, sql: str, parameters: dict[str, Any]) -> RowMapping | None:
        try:
            async with self._database.session() as session:
                result = await session.execute(text(sql), parameters)
                return result.mappings().one_or_none()
        except SQLAlchemyError as exc:
            raise ProcessingPersistenceError("Processing job lookup failed.") from exc

    async def _one(self, sql: str, parameters: dict[str, Any]) -> JobRecord | None:
        row = await self._mapping(sql, parameters)
        return None if row is None else _job_record(row)

    async def _many(self, sql: str, parameters: dict[str, Any]) -> tuple[JobRecord, ...]:
        try:
            async with self._database.session() as session:
                result = await session.execute(text(sql), parameters)
                return tuple(_job_record(row) for row in result.mappings())
        except SQLAlchemyError as exc:
            raise ProcessingPersistenceError("Processing job lookup failed.") from exc

    async def _artifact_many(
        self, sql: str, parameters: dict[str, Any]
    ) -> tuple[ArtifactRecord, ...]:
        try:
            async with self._database.session() as session:
                result = await session.execute(text(sql), parameters)
                return tuple(_artifact_record(row) for row in result.mappings())
        except SQLAlchemyError as exc:
            raise ProcessingPersistenceError("Artifact lookup failed.") from exc


def _job_record(row: RowMapping) -> JobRecord:
    return JobRecord(
        job_id=row["id"],
        owner_id=row["owner_id"],
        access_scope=row["access_scope"],
        operation=row["operation"],
        operation_version=row["operation_version"],
        idempotency_key=row["idempotency_key"],
        request_digest=row["request_digest"],
        cache_key=row["cache_key"],
        request_json=dict(row["request_json"]),
        source_evidence_json=list(row["source_evidence_json"]),
        state=row["state"],
        current_stage=row["current_stage"],
        completed_units=row["completed_units"],
        total_units=row["total_units"],
        attempt=row["attempt"],
        submitted_at=row["submitted_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        error_code=row["error_code"],
        safe_error_message=row["safe_error_message"],
        quality_report_json=(
            dict(row["quality_report_json"]) if row["quality_report_json"] is not None else None
        ),
        manifest_json=(dict(row["manifest_json"]) if row["manifest_json"] is not None else None),
    )


def _artifact_record(row: RowMapping) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=row["id"],
        job_id=row["job_id"],
        owner_id=row["owner_id"],
        kind=row["kind"],
        media_type=row["media_type"],
        storage_key=row["storage_key"],
        checksum_sha256=row["checksum_sha256"],
        byte_size=row["byte_size"],
        state=row["state"],
        created_at=row["created_at"].astimezone(UTC),
    )
