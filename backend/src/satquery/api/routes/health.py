from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from satquery import __version__
from satquery.api.dependencies import get_database
from satquery.api.schemas.health import (
    DatabaseHealth,
    LivenessResponse,
    ReadinessChecks,
    ReadinessResponse,
)
from satquery.core.errors import ApiError
from satquery.db.session import DatabaseUnavailableError, ReadinessDatabase

router = APIRouter()
NO_STORE_HEADERS = {"Cache-Control": "no-store"}


@router.get(
    "/live",
    response_model=LivenessResponse,
    response_model_exclude_none=True,
    summary="Application liveness",
)
async def liveness(response: Response) -> LivenessResponse:
    response.headers.update(NO_STORE_HEADERS)
    return LivenessResponse(status="live", service="satquery-api", version=__version__)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Database unavailable"}},
    summary="Required dependency readiness",
)
async def readiness(
    request: Request,
    response: Response,
    database: Annotated[ReadinessDatabase, Depends(get_database)],
) -> ReadinessResponse:
    response.headers.update(NO_STORE_HEADERS)
    try:
        database_status = await database.check_readiness()
    except DatabaseUnavailableError as exc:
        raise ApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DEPENDENCY_UNAVAILABLE",
            message="A required service dependency is unavailable.",
            details={"dependency": "database"},
            retryable=True,
            headers={"Cache-Control": "no-store", "Retry-After": "5"},
        ) from exc

    return ReadinessResponse(
        status="ready",
        service="satquery-api",
        version=__version__,
        request_id=request.state.request_id,
        checks=ReadinessChecks(
            database=DatabaseHealth(
                status="up",
                postgis="available",
                migration="current",
                server_version=database_status.server_version,
                postgis_version=database_status.postgis_version,
                migration_revision=database_status.migration_revision,
            )
        ),
    )
