"""API routes for generating, tracking, and downloading evidence-based reports."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from satquery.api.dependencies import get_report_service
from satquery.api.schemas.reports import (
    ReportRequest,
    ReportResponse,
    ReportSnapshot,
)
from satquery.services.report_service import ReportService, ReportServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post(
    "/request",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Request report export generation",
    description=(
        "Initiates server-side generation of an immutable analysis snapshot and "
        "renders requested PDF and JSON export files."
    ),
)
async def request_report_generation(
    request: ReportRequest,
    report_service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportResponse:
    """Generate exportable report from a server-resolved analysis result."""
    try:
        return report_service.create_report(request)
    except ReportServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except Exception as e:
        logger.exception(f"Unexpected error during report generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {e}",
        ) from e


@router.post(
    "/snapshot-export",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate export from direct ReportSnapshot",
    description=(
        "Accepts a validated ReportSnapshot directly and renders downloadable PDF and JSON formats."
    ),
)
async def export_direct_snapshot(
    snapshot: ReportSnapshot,
    report_service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportResponse:
    """Generate export formats from a provided ReportSnapshot."""
    try:
        request = ReportRequest(
            result_id=snapshot.report_id,
            title=snapshot.title,
            format="pdf",
            formats=["pdf", "json"],
        )
        return report_service.create_report(request, snapshot=snapshot)
    except Exception as e:
        logger.exception(f"Direct snapshot export failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {e}",
        ) from e


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get report export status and metadata",
    description="Retrieves the current status, format availability, and download links for a report.",
)
async def get_report_status(
    report_id: Annotated[str, Path(description="Opaque report identifier")],
    report_service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportResponse:
    """Retrieve report status and metadata."""
    try:
        return report_service.get_report(report_id)
    except ReportServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e


@router.get(
    "/{report_id}/snapshot",
    response_model=ReportSnapshot,
    summary="Get immutable analysis report snapshot",
    description="Returns the complete, frozen ReportSnapshot JSON object.",
)
async def get_report_snapshot(
    report_id: Annotated[str, Path(description="Opaque report identifier")],
    report_service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportSnapshot:
    """Retrieve the full immutable ReportSnapshot JSON."""
    try:
        return report_service.get_snapshot(report_id)
    except ReportServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e


@router.get(
    "/{report_id}/download/{format_str}",
    summary="Download rendered report file",
    description="Streams the rendered PDF or JSON report file as an attachment download.",
)
async def download_report_file(
    report_id: Annotated[str, Path(description="Opaque report identifier")],
    format_str: Annotated[str, Path(description="Export format: 'pdf' or 'json'")],
    report_service: Annotated[ReportService, Depends(get_report_service)],
) -> Response:
    """Download binary PDF or JSON report export."""
    try:
        raw_bytes, media_type, filename = report_service.get_export_file(report_id, format_str)
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-transform, max-age=3600",
            "X-Report-ID": report_id,
        }
        return Response(content=raw_bytes, media_type=media_type, headers=headers)
    except ReportServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
