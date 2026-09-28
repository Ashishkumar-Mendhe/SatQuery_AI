from __future__ import annotations

from typing import Annotated, Any, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Response, status
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from satquery.api.dependencies import get_processing_job_service, get_processing_principal
from satquery.api.schemas.change import ChangeAnalysisApiResult
from satquery.api.schemas.processing import PreparationRequest, ProcessingJobStatus
from satquery.core.errors import ApiError
from satquery.db.processing import (
    IdempotencyConflictError,
    ProcessingPersistenceError,
    ProcessingPrincipal,
)
from satquery.processing.jobs import (
    JobNotFoundError,
    MaskTileError,
    PreparationJobError,
    PreparationJobService,
    QualityReportUnavailableError,
)

router = APIRouter()
ServiceDependency = Annotated[PreparationJobService, Depends(get_processing_job_service)]
PrincipalDependency = Annotated[ProcessingPrincipal, Depends(get_processing_principal)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$"),
]


def _raise_job_error(error: Exception) -> NoReturn:
    if isinstance(error, JobNotFoundError):
        raise ApiError(status_code=404, code="NOT_FOUND", message="Resource not found.") from error
    if isinstance(error, IdempotencyConflictError):
        raise ApiError(status_code=409, code="IDEMPOTENCY_CONFLICT", message=str(error)) from error
    if isinstance(error, PreparationJobError):
        raise ApiError(status_code=422, code=error.code, message=str(error)) from error
    if isinstance(error, ProcessingPersistenceError):
        raise ApiError(
            status_code=503,
            code="DEPENDENCY_UNAVAILABLE",
            message=str(error),
            retryable=True,
        ) from error
    raise error


@router.post(
    "/preparations",
    response_model=ProcessingJobStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start or reuse one authorized bounded preparation job",
)
async def start_preparation(
    request: PreparationRequest,
    idempotency_key: IdempotencyKey,
    principal: PrincipalDependency,
    service: ServiceDependency,
) -> ProcessingJobStatus:
    try:
        job = await service.submit(principal, request, idempotency_key=idempotency_key)
        return await service.status(principal, job.job_id)
    except (PreparationJobError, IdempotencyConflictError, ProcessingPersistenceError) as error:
        _raise_job_error(error)


@router.get(
    "/jobs/{job_id}",
    response_model=ProcessingJobStatus,
    summary="Get authorized durable preparation status",
)
async def get_preparation_status(
    job_id: UUID, principal: PrincipalDependency, service: ServiceDependency
) -> ProcessingJobStatus:
    try:
        return await service.status(principal, job_id)
    except (JobNotFoundError, ProcessingPersistenceError) as error:
        _raise_job_error(error)


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=ProcessingJobStatus,
    summary="Request cooperative cancellation of an authorized preparation",
)
async def cancel_preparation(
    job_id: UUID, principal: PrincipalDependency, service: ServiceDependency
) -> ProcessingJobStatus:
    try:
        return await service.cancel(principal, job_id)
    except (JobNotFoundError, ProcessingPersistenceError) as error:
        _raise_job_error(error)


@router.get(
    "/jobs/{job_id}/quality-report",
    response_model=dict[str, Any],
    summary="Get the persisted scientific validity report for a completed preparation",
)
async def get_quality_report(
    job_id: UUID, principal: PrincipalDependency, service: ServiceDependency
) -> dict[str, Any]:
    try:
        return await service.quality_report(principal, job_id)
    except QualityReportUnavailableError as error:
        raise ApiError(
            status_code=409,
            code="RESULT_NOT_AVAILABLE",
            message="The quality report is available only after successful completion.",
        ) from error
    except (JobNotFoundError, ProcessingPersistenceError) as error:
        _raise_job_error(error)


@router.get(
    "/artifacts/{artifact_id}",
    response_class=Response,
    summary="Stream one authorized committed preparation artifact",
)
async def get_preparation_artifact(
    artifact_id: UUID, principal: PrincipalDependency, service: ServiceDependency
) -> Response:
    try:
        artifact, stream = await service.artifact(principal, artifact_id)
    except (JobNotFoundError, ProcessingPersistenceError) as error:
        _raise_job_error(error)
    return StreamingResponse(
        stream,
        media_type=artifact.media_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Checksum-SHA256": artifact.checksum_sha256,
        },
        background=BackgroundTask(stream.close),
    )


@router.get(
    "/artifacts/{artifact_id}/tiles/{mask}/{z}/{x}/{y}.png",
    response_class=Response,
    summary="Render an authorized committed quality mask on the map grid",
)
async def get_preparation_mask_tile(
    artifact_id: UUID,
    mask: Annotated[str, Path(pattern=r"^(usable|exclusions|change)$")],
    z: Annotated[int, Path(ge=0, le=16)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
    principal: PrincipalDependency,
    service: ServiceDependency,
) -> Response:
    try:
        body = (
            await service.change_tile(principal, artifact_id, z, x, y)
            if mask == "change"
            else await service.mask_tile(principal, artifact_id, mask, z, x, y)
        )
    except MaskTileError as error:
        raise ApiError(
            status_code=error.status_code, code=error.code, message=str(error)
        ) from error
    except (JobNotFoundError, ProcessingPersistenceError) as error:
        _raise_job_error(error)
    return Response(
        content=body,
        media_type="image/png",
        headers={"Cache-Control": "private, no-store"},
    )


@router.post(
    "/changes",
    response_model=ProcessingJobStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start or reuse one authorized two-date spectral change job",
)
async def start_change_analysis(
    request: PreparationRequest,
    idempotency_key: IdempotencyKey,
    principal: PrincipalDependency,
    service: ServiceDependency,
) -> ProcessingJobStatus:
    try:
        job = await service.submit_change(principal, request, idempotency_key=idempotency_key)
        return await service.change_status(principal, job.job_id)
    except (PreparationJobError, IdempotencyConflictError, ProcessingPersistenceError) as error:
        _raise_job_error(error)


@router.get(
    "/change-jobs/{job_id}",
    response_model=ProcessingJobStatus,
    summary="Get authorized durable change-analysis status",
)
async def get_change_status(
    job_id: UUID, principal: PrincipalDependency, service: ServiceDependency
) -> ProcessingJobStatus:
    try:
        return await service.change_status(principal, job_id)
    except (JobNotFoundError, ProcessingPersistenceError) as error:
        _raise_job_error(error)


@router.get(
    "/change-jobs/{job_id}/result",
    response_model=ChangeAnalysisApiResult,
    summary="Get a completed computed two-date change result",
)
async def get_change_result(
    job_id: UUID, principal: PrincipalDependency, service: ServiceDependency
) -> dict[str, Any]:
    try:
        return await service.change_result(principal, job_id)
    except QualityReportUnavailableError as error:
        raise ApiError(
            status_code=409,
            code="RESULT_NOT_AVAILABLE",
            message="The computed result is available only after successful completion.",
        ) from error
    except (JobNotFoundError, ProcessingPersistenceError) as error:
        _raise_job_error(error)


@router.post(
    "/change-jobs/{job_id}/cancel",
    response_model=ProcessingJobStatus,
    summary="Request cooperative cancellation of change analysis",
)
async def cancel_change(
    job_id: UUID, principal: PrincipalDependency, service: ServiceDependency
) -> ProcessingJobStatus:
    try:
        return await service.cancel_change(principal, job_id)
    except (JobNotFoundError, ProcessingPersistenceError) as error:
        _raise_job_error(error)
