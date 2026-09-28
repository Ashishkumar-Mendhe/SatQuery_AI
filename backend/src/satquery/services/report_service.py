"""Report service managing snapshot lifecycle, PDF/JSON export generation, and downloads."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta

from satquery.api.schemas.analysis import (
    AOIGeometry,
    APIError,
    APIErrorCode,
    ReportFormat,
)
from satquery.api.schemas.reports import (
    ReportFormatStatus,
    ReportRequest,
    ReportResponse,
    ReportSnapshot,
    ReportStatus,
)
from satquery.core.config import Settings
from satquery.services.asset_store import AssetStore
from satquery.services.change_service import ChangeService
from satquery.services.fusion_service import FusionService
from satquery.services.pdf_renderer import SatQueryPdfRenderer
from satquery.services.query_service import QueryService
from satquery.services.report_builder import ReportSnapshotBuilder
from satquery.services.spectral_service import SpectralService
from satquery.services.visual_query_service import VisualQueryService

logger = logging.getLogger(__name__)


class ReportServiceError(Exception):
    """Base exception for report service operations."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ReportService:
    """Orchestrates report snapshot creation, multi-format rendering, and secure downloads."""

    def __init__(
        self,
        settings: Settings,
        asset_store: AssetStore | None = None,
        change_service: ChangeService | None = None,
        spectral_service: SpectralService | None = None,
        fusion_service: FusionService | None = None,
        query_service: QueryService | None = None,
        visual_query_service: VisualQueryService | None = None,
        pdf_renderer: SatQueryPdfRenderer | None = None,
        snapshot_builder: ReportSnapshotBuilder | None = None,
    ) -> None:
        self.settings = settings
        self.asset_store = asset_store or AssetStore(
            storage_dir=settings.imagery_storage_dir,
            default_ttl_seconds=settings.imagery_asset_cache_ttl_seconds,
        )
        self.change_service = change_service
        self.spectral_service = spectral_service
        self.fusion_service = fusion_service
        self.query_service = query_service
        self.visual_query_service = visual_query_service
        self.pdf_renderer = pdf_renderer or SatQueryPdfRenderer(self.asset_store)
        self.snapshot_builder = snapshot_builder or ReportSnapshotBuilder(self.asset_store)

        # In-memory session caches for generated exports
        self._snapshots: dict[str, ReportSnapshot] = {}
        self._pdf_cache: dict[str, bytes] = {}
        self._json_cache: dict[str, bytes] = {}
        self._responses: dict[str, ReportResponse] = {}

    def create_report(
        self,
        request: ReportRequest,
        snapshot: ReportSnapshot | None = None,
    ) -> ReportResponse:
        """Create an immutable snapshot, render requested export formats, and return response metadata."""
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self.settings.imagery_asset_cache_ttl_seconds)

        # 1. Resolve or validate snapshot
        resolved_snapshot: ReportSnapshot
        if snapshot is not None:
            resolved_snapshot = snapshot
        else:
            resolved_snapshot = self._resolve_snapshot_from_request(request)

        report_id = resolved_snapshot.report_id
        self._snapshots[report_id] = resolved_snapshot

        # 2. Determine target formats
        target_formats: list[ReportFormat] = []
        if request.formats:
            target_formats.extend(request.formats)
        elif request.format:
            target_formats.append(request.format)
        else:
            target_formats = [ReportFormat.PDF, ReportFormat.JSON]

        format_statuses: dict[str, ReportFormatStatus] = {}
        primary_download_url: str | None = None
        primary_size: int | None = None

        for fmt in target_formats:
            fmt_str = fmt.value.lower()
            try:
                if fmt_str == "pdf":
                    pdf_bytes = self.pdf_renderer.render_pdf(resolved_snapshot)
                    self._pdf_cache[report_id] = pdf_bytes
                    file_size = len(pdf_bytes)
                    download_url = f"/api/v1/reports/{report_id}/download/pdf"
                    format_statuses[fmt.value] = ReportFormatStatus(
                        format=ReportFormat.PDF,
                        status=ReportStatus.COMPLETED,
                        download_url=download_url,
                        file_size_bytes=file_size,
                        generated_at=now,
                    )
                    if not primary_download_url:
                        primary_download_url = download_url
                        primary_size = file_size

                elif fmt_str == "json":
                    json_str = resolved_snapshot.model_dump_json(indent=2)
                    json_bytes = json_str.encode("utf-8")
                    self._json_cache[report_id] = json_bytes
                    file_size = len(json_bytes)
                    download_url = f"/api/v1/reports/{report_id}/download/json"
                    format_statuses[fmt.value] = ReportFormatStatus(
                        format=ReportFormat.JSON,
                        status=ReportStatus.COMPLETED,
                        download_url=download_url,
                        file_size_bytes=file_size,
                        generated_at=now,
                    )
                    if not primary_download_url:
                        primary_download_url = download_url
                        primary_size = file_size

            except Exception as e:
                logger.error(f"Failed to generate format '{fmt_str}' for report '{report_id}': {e}")
                format_statuses[fmt.value] = ReportFormatStatus(
                    format=fmt,
                    status=ReportStatus.FAILED,
                    error=APIError(
                        code=APIErrorCode.INTERNAL_ERROR,
                        message=f"Export failed: {e}",
                        status=500,
                    ),
                    generated_at=now,
                )

        # 3. Compute overall status
        all_completed = all(s.status == ReportStatus.COMPLETED for s in format_statuses.values())
        any_completed = any(s.status == ReportStatus.COMPLETED for s in format_statuses.values())

        if all_completed and format_statuses:
            overall_status = ReportStatus.COMPLETED
        elif any_completed:
            overall_status = ReportStatus.PARTIALLY_COMPLETED
        else:
            overall_status = ReportStatus.FAILED

        # 4. Assemble response envelope
        response = ReportResponse(
            report_id=report_id,
            status=overall_status,
            format=target_formats[0] if target_formats else ReportFormat.PDF,
            download_url=primary_download_url,
            created_at=resolved_snapshot.created_at,
            expires_at=expires_at,
            file_size_bytes=primary_size,
            title=resolved_snapshot.title,
            data_origin=resolved_snapshot.data_origin,
            formats=format_statuses,
            snapshot_checksum=resolved_snapshot.checksum_sha256,
        )

        self._responses[report_id] = response
        return response

    def get_report(self, report_id: str) -> ReportResponse:
        """Retrieve the current report metadata and format statuses."""
        if report_id not in self._responses:
            raise ReportServiceError("REPORT_NOT_FOUND", f"Report '{report_id}' not found.", 404)
        return self._responses[report_id]

    def get_snapshot(self, report_id: str) -> ReportSnapshot:
        """Retrieve the full immutable ReportSnapshot."""
        if report_id not in self._snapshots:
            raise ReportServiceError("REPORT_NOT_FOUND", f"Report '{report_id}' not found.", 404)
        return self._snapshots[report_id]

    def get_export_file(self, report_id: str, format_str: str) -> tuple[bytes, str, str]:
        """Retrieve raw export bytes, Content-Type, and sanitized attachment filename."""
        fmt_lower = format_str.lower()
        snapshot = self.get_snapshot(report_id)

        if fmt_lower == "pdf":
            if report_id not in self._pdf_cache:
                # Attempt on-demand render
                try:
                    pdf_bytes = self.pdf_renderer.render_pdf(snapshot)
                    self._pdf_cache[report_id] = pdf_bytes
                except Exception as e:
                    raise ReportServiceError(
                        "PDF_RENDER_FAILED",
                        f"Could not render PDF for report '{report_id}': {e}",
                        500,
                    ) from e
            raw_bytes = self._pdf_cache[report_id]
            media_type = "application/pdf"
            filename = self.generate_safe_filename(snapshot.title, report_id, "pdf")
            return raw_bytes, media_type, filename

        if fmt_lower == "json":
            if report_id not in self._json_cache:
                json_str = snapshot.model_dump_json(indent=2)
                self._json_cache[report_id] = json_str.encode("utf-8")
            raw_bytes = self._json_cache[report_id]
            media_type = "application/json"
            filename = self.generate_safe_filename(snapshot.title, report_id, "json")
            return raw_bytes, media_type, filename

        raise ReportServiceError(
            "UNSUPPORTED_FORMAT", f"Format '{format_str}' is not supported.", 400
        )

    def generate_safe_filename(self, title: str, report_id: str, extension: str) -> str:
        """Sanitize title into a safe, ASCII-compatible filename."""
        clean = re.sub(r"[^\w\s-]", "", title).strip().lower()
        clean = re.sub(r"[\s_-]+", "-", clean)
        clean = clean[:40] if clean else "satquery-report"
        return f"{clean}-{report_id[:8]}.{extension}"

    def _resolve_snapshot_from_request(self, request: ReportRequest) -> ReportSnapshot:
        """Resolve upstream analysis components when a raw result_id is provided."""
        target_id = request.result_id or request.analysis_job_id
        if not target_id:
            raise ReportServiceError(
                "MISSING_RESULT_ID",
                "Report request requires either result_id or analysis_job_id.",
                400,
            )

        # Check ChangeService
        if self.change_service and target_id in self.change_service._results_cache:
            chg_res = self.change_service._results_cache[target_id]
            aoi_geom = (
                chg_res.regions[0].geometry
                if chg_res.regions
                else AOIGeometry(
                    type="Polygon",
                    coordinates=[[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
                    crs="EPSG:4326",
                )
            )
            return self.snapshot_builder.build_snapshot(
                title=request.title,
                aoi=aoi_geom,
                change_result=chg_res,
                data_origin=chg_res.data_origin,
            )

        # Check FusionService
        if self.fusion_service and target_id in self.fusion_service._results_cache:
            fus_res = self.fusion_service._results_cache[target_id]
            aoi_geom = (
                fus_res.regions[0].geometry
                if fus_res.regions
                else AOIGeometry(
                    type="Polygon",
                    coordinates=[[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
                    crs="EPSG:4326",
                )
            )
            return self.snapshot_builder.build_snapshot(
                title=request.title,
                aoi=aoi_geom,
                fusion_result=fus_res,
                data_origin=fus_res.data_origin,
            )

        raise ReportServiceError(
            "RESULT_NOT_FOUND",
            f"Analysis result '{target_id}' could not be resolved from server storage.",
            404,
        )
