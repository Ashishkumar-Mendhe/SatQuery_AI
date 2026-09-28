from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from satquery.api.dependencies import get_optical_sar_job_service, get_processing_principal
from satquery.api.schemas.optical_sar import (
    OpticalSarAnalysisRequest,
    OpticalSarAnalysisResult,
    OpticalSarJobStatus,
)
from satquery.core.errors import ApiError
from satquery.db.processing import (
    IdempotencyConflictError,
    ProcessingPersistenceError,
    ProcessingPrincipal,
)
from satquery.processing.optical_sar_jobs import (
    OpticalSarJobError,
    OpticalSarJobNotFoundError,
    OpticalSarJobService,
    OpticalSarResultUnavailableError,
)

router = APIRouter()
Service = Annotated[OpticalSarJobService, Depends(get_optical_sar_job_service)]
Principal = Annotated[ProcessingPrincipal, Depends(get_processing_principal)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$"),
]


def _raise(error: Exception) -> NoReturn:
    if isinstance(error, OpticalSarJobNotFoundError):
        raise ApiError(status_code=404, code="NOT_FOUND", message="Resource not found.") from error
    if isinstance(error, OpticalSarResultUnavailableError):
        raise ApiError(
            status_code=409,
            code="RESULT_NOT_AVAILABLE",
            message="The combined evidence is not committed yet.",
        ) from error
    if isinstance(error, IdempotencyConflictError):
        raise ApiError(status_code=409, code="IDEMPOTENCY_CONFLICT", message=str(error)) from error
    if isinstance(error, ProcessingPersistenceError):
        raise ApiError(
            status_code=503, code="DEPENDENCY_UNAVAILABLE", message=str(error), retryable=True
        ) from error
    if isinstance(error, OpticalSarJobError):
        raise ApiError(status_code=422, code=error.code, message=str(error)) from error
    raise error


@router.post("/jobs", response_model=OpticalSarJobStatus, status_code=status.HTTP_202_ACCEPTED)
async def start_optical_sar_job(
    request: OpticalSarAnalysisRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    service: Service,
) -> OpticalSarJobStatus:
    try:
        job = await service.submit(principal, request, idempotency_key=idempotency_key)
        return await service.status(principal, job.job_id)
    except (OpticalSarJobError, IdempotencyConflictError, ProcessingPersistenceError) as exc:
        _raise(exc)


@router.get("/jobs/{job_id}", response_model=OpticalSarJobStatus)
async def get_optical_sar_job(
    job_id: UUID, principal: Principal, service: Service
) -> OpticalSarJobStatus:
    try:
        return await service.status(principal, job_id)
    except (OpticalSarJobNotFoundError, ProcessingPersistenceError) as exc:
        _raise(exc)


@router.get("/jobs/{job_id}/result", response_model=OpticalSarAnalysisResult)
async def get_optical_sar_result(
    job_id: UUID, principal: Principal, service: Service
) -> OpticalSarAnalysisResult:
    try:
        return await service.result(principal, job_id)
    except (
        OpticalSarJobNotFoundError,
        OpticalSarResultUnavailableError,
        ProcessingPersistenceError,
    ) as exc:
        _raise(exc)


@router.post("/jobs/{job_id}/cancel", response_model=OpticalSarJobStatus)
async def cancel_optical_sar_job(
    job_id: UUID, principal: Principal, service: Service
) -> OpticalSarJobStatus:
    try:
        return await service.cancel(principal, job_id)
    except (OpticalSarJobNotFoundError, ProcessingPersistenceError) as exc:
        _raise(exc)


@router.get("/artifacts/{artifact_id}", response_class=Response)
async def get_optical_sar_artifact(
    artifact_id: UUID, principal: Principal, service: Service
) -> Response:
    try:
        artifact, stream = await service.artifact(principal, artifact_id)
    except OpticalSarJobNotFoundError as exc:
        _raise(exc)
    return StreamingResponse(
        stream,
        media_type=artifact.media_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Checksum-SHA256": artifact.checksum_sha256,
        },
        background=BackgroundTask(stream.close),
    )
