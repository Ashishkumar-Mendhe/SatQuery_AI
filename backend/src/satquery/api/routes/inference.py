from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from satquery.api.dependencies import get_inference_job_service, get_processing_principal
from satquery.api.schemas.vqa import (
    InferenceEvidenceRecord,
    InferenceJobStatus,
    InferenceSubmissionRequest,
)
from satquery.core.errors import ApiError
from satquery.db.processing import (
    IdempotencyConflictError,
    ProcessingPersistenceError,
    ProcessingPrincipal,
)
from satquery.inference.jobs import (
    InferenceJobError,
    InferenceJobNotFoundError,
    InferenceJobService,
    InferenceResultUnavailableError,
)

router = APIRouter()
Service = Annotated[InferenceJobService, Depends(get_inference_job_service)]
Principal = Annotated[ProcessingPrincipal, Depends(get_processing_principal)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$"),
]


def _raise(error: Exception) -> NoReturn:
    if isinstance(error, InferenceJobNotFoundError):
        raise ApiError(status_code=404, code="NOT_FOUND", message="Resource not found.") from error
    if isinstance(error, IdempotencyConflictError):
        raise ApiError(status_code=409, code="IDEMPOTENCY_CONFLICT", message=str(error)) from error
    if isinstance(error, InferenceJobError):
        raise ApiError(status_code=422, code=error.code, message=str(error)) from error
    if isinstance(error, ProcessingPersistenceError):
        raise ApiError(
            status_code=503, code="DEPENDENCY_UNAVAILABLE", message=str(error), retryable=True
        ) from error
    raise error


@router.post(
    "/jobs",
    response_model=InferenceJobStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start or reuse an authorized single-image inference job",
)
async def start_inference(
    request: InferenceSubmissionRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    service: Service,
) -> InferenceJobStatus:
    try:
        job = await service.submit(principal, request, idempotency_key=idempotency_key)
        return await service.status(principal, job.job_id)
    except (InferenceJobError, IdempotencyConflictError, ProcessingPersistenceError) as error:
        _raise(error)


@router.get("/jobs/{job_id}", response_model=InferenceJobStatus)
async def get_inference_status(
    job_id: UUID, principal: Principal, service: Service
) -> InferenceJobStatus:
    try:
        return await service.status(principal, job_id)
    except (InferenceJobNotFoundError, ProcessingPersistenceError) as error:
        _raise(error)


@router.get("/jobs/{job_id}/result", response_model=InferenceEvidenceRecord)
async def get_inference_result(
    job_id: UUID, principal: Principal, service: Service
) -> InferenceEvidenceRecord:
    try:
        return await service.result(principal, job_id)
    except InferenceResultUnavailableError as error:
        raise ApiError(
            status_code=409,
            code="RESULT_NOT_AVAILABLE",
            message="Inference evidence is available only after successful completion.",
        ) from error
    except (InferenceJobNotFoundError, ProcessingPersistenceError) as error:
        _raise(error)


@router.post("/jobs/{job_id}/cancel", response_model=InferenceJobStatus)
async def cancel_inference(
    job_id: UUID, principal: Principal, service: Service
) -> InferenceJobStatus:
    try:
        return await service.cancel(principal, job_id)
    except (InferenceJobNotFoundError, ProcessingPersistenceError) as error:
        _raise(error)


@router.get("/artifacts/{artifact_id}", response_class=Response)
async def get_inference_artifact(
    artifact_id: UUID, principal: Principal, service: Service
) -> Response:
    try:
        artifact, stream = await service.artifact(principal, artifact_id)
    except (InferenceJobNotFoundError, ProcessingPersistenceError) as error:
        _raise(error)
    return StreamingResponse(
        stream,
        media_type=artifact.media_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Checksum-SHA256": artifact.checksum_sha256,
        },
        background=BackgroundTask(stream.close),
    )
