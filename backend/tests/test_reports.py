"""Unit and integration tests for Phase 6A evidence-based reports and export."""

from __future__ import annotations

import base64
import json
import re
import zlib
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from conftest import ReadyDatabase
from fastapi.testclient import TestClient

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    AOIGeometry,
    ConfidenceBreakdown,
    ConfidenceFactor,
    EvidenceItem,
    EvidenceProvenance,
    EvidenceType,
    ReportFormat,
    SatelliteScene,
    SensorType,
    WarningSeverity,
)
from satquery.api.schemas.change import (
    ChangeDetectionDefinition,
    ChangeDetectionMethod,
    ChangeDetectionResult,
    ChangeDirectionality,
    ChangeMetrics,
    ChangePixelCounts,
    ChangeThresholdConfig,
    ThresholdStrategy,
)
from satquery.api.schemas.preparation import RasterProvenance
from satquery.api.schemas.providers import DataOrigin
from satquery.api.schemas.query import (
    AnswerClaim,
    ClaimKind,
    ClaimValidationStatus,
    GenerationMode,
    QueryAnswer,
    QueryIntent,
    QueryPlan,
    SufficiencyStatus,
)
from satquery.api.schemas.reports import (
    REPORT_SCHEMA_VERSION,
    ReportRequest,
    ReportStatus,
)
from satquery.api.schemas.visual import (
    CoordinateStatus,
    MapGroundingStatus,
    VisualObservation,
    VisualQueryResponse,
)
from satquery.core.config import Settings
from satquery.main import create_app
from satquery.services.asset_store import AssetStore
from satquery.services.pdf_renderer import SatQueryPdfRenderer
from satquery.services.report_builder import ReportSnapshotBuilder
from satquery.services.report_service import ReportService


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql+psycopg://test:test@localhost:5432/test_db",
        imagery_storage_dir="tmp/test_imagery_reports",
        imagery_asset_cache_ttl_seconds=3600,
    )


@pytest.fixture
def asset_store(test_settings: Settings) -> AssetStore:
    return AssetStore(
        storage_dir=test_settings.imagery_storage_dir,
        default_ttl_seconds=test_settings.imagery_asset_cache_ttl_seconds,
    )


@pytest.fixture
def report_builder(asset_store: AssetStore) -> ReportSnapshotBuilder:
    return ReportSnapshotBuilder(asset_store)


@pytest.fixture
def pdf_renderer(asset_store: AssetStore) -> SatQueryPdfRenderer:
    return SatQueryPdfRenderer(asset_store)


@pytest.fixture
def report_service(
    test_settings: Settings,
    asset_store: AssetStore,
    pdf_renderer: SatQueryPdfRenderer,
    report_builder: ReportSnapshotBuilder,
) -> ReportService:
    return ReportService(
        settings=test_settings,
        asset_store=asset_store,
        pdf_renderer=pdf_renderer,
        snapshot_builder=report_builder,
    )


@pytest.fixture
def client(test_settings: Settings, report_service: ReportService) -> Iterator[TestClient]:
    app = create_app(
        settings=test_settings, database=ReadyDatabase(), report_service=report_service
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def known_answer_fixture() -> dict[str, Any]:
    """Authoritative known-answer geometry and accounting fixture per Phase 6A specification.

    * AOI total area: 2.00 km²
    * Valid comparison area: 1.00 km² (50% coverage of AOI)
    * Increase / Gain: 0.20 km² (20% of valid comparison area)
    * Decrease / Loss: 0.10 km² (10% of valid comparison area)
    * Stable: 0.65 km² (65% of valid comparison area)
    * Uncertain: 0.05 km² (5% of valid comparison area)
    * Excluded / outside valid domain: 1.00 km² (50% of AOI)
    * Model-predicted box: 0.03 km² illustrative area (verified strictly NOT added to measured change totals)
    """
    aoi = AOIGeometry(
        type="Polygon",
        coordinates=[
            [
                [77.58, 12.96],
                [77.60, 12.96],
                [77.60, 12.98],
                [77.58, 12.98],
                [77.58, 12.96],
            ]
        ],
        area_km2=2.00,
        bbox=(77.58, 12.96, 77.60, 12.98),
    )

    pixel_counts = ChangePixelCounts(
        total_aoi_pixels=20000,
        shared_valid_pixels=10000,
        gain_pixels=2000,
        loss_pixels=1000,
        stable_pixels=6500,
        uncertain_pixels=500,
        gain_percent=20.0,
        loss_percent=10.0,
        stable_percent=65.0,
        uncertain_percent=5.0,
    )

    metrics = ChangeMetrics(
        gain_area_km2=0.20,
        loss_area_km2=0.10,
        stable_area_km2=0.65,
        net_change_area_km2=0.10,
        shared_valid_area_km2=1.00,
        pixel_counts=pixel_counts,
        positive_threshold_applied=0.15,
        negative_threshold_applied=-0.15,
        threshold_strategy=ThresholdStrategy.FIXED,
    )

    confidence = ConfidenceBreakdown(
        overall=0.88,
        data_quality=0.95,
        temporal_quality=0.90,
        spatial_quality=0.85,
        model_confidence=0.85,
        evidence_agreement=0.85,
        factors=[
            ConfidenceFactor(
                code="data_quality",
                label="Sensor Radiometric Quality",
                score=0.95,
                weight=0.35,
                explanation="Sentinel-2 L2A Surface Reflectance with clear atmospheric conditions",
            ),
            ConfidenceFactor(
                code="spatial_alignment",
                label="Grid Co-Registration",
                score=0.90,
                weight=0.35,
                explanation="Strict sub-pixel grid alignment across mutual AOI footprint",
            ),
            ConfidenceFactor(
                code="temporal_suitability",
                label="Temporal Window Pairing",
                score=0.80,
                weight=0.30,
                explanation="Acquisitions separated by 14 days; minimal seasonal distortion",
            ),
        ],
        methodology="Multi-factor weighted geometric and radiometric assessment",
        limitations=["Sub-10m features below native sensor resolution ceiling"],
    )

    definition = ChangeDetectionDefinition(
        method=ChangeDetectionMethod.NDVI_DIFFERENCE,
        display_name="Normalized Difference Vegetation Index Differencing",
        formula="(NIR - Red) / (NIR + Red)",
        input_type="spectral_index",
        directionality=ChangeDirectionality.BIDIRECTIONAL,
        expected_range=(-2.0, 2.0),
        default_threshold_config=ChangeThresholdConfig(),
        description="Standardized bi-temporal vegetation vigor differencing",
        limitations="Sensitive to cloud shadows and seasonal phenology",
    )

    evidence_item = EvidenceItem(
        id="evd-chg-001",
        type=EvidenceType.CHANGE_MEASUREMENT,
        title="NDVI Surface Difference Measurement",
        description="Measured 0.20 km² gain and 0.10 km² loss across 1.00 km² valid comparison area",
        source_scene_ids=["S2A_T43PGQ_20260101", "S2B_T43PGQ_20260115"],
        observed_at=datetime(2026, 1, 15, 10, 30, tzinfo=UTC),
        confidence=0.88,
        provenance=EvidenceProvenance(
            computation="ndvi_difference",
            algorithm_name="bi_temporal_differencing",
            version="1.0.0",
            processed_at=datetime(2026, 1, 15, 11, 0, tzinfo=UTC),
            parameters={"positive_threshold": 0.15, "negative_threshold": -0.15},
        ),
    )

    provenance = RasterProvenance(
        pipeline_version="1.0.0",
        source_asset_ids=["ast-prep-before", "ast-prep-after"],
        source_scene_ids=["S2A_T43PGQ_20260101", "S2B_T43PGQ_20260115"],
        operations=["reproject", "grid_align", "diff"],
        parameters={"positive_threshold": 0.15, "negative_threshold": -0.15},
        started_at=datetime(2026, 1, 15, 11, 0, tzinfo=UTC),
        completed_at=datetime(2026, 1, 15, 11, 5, tzinfo=UTC),
        duration_milliseconds=300.0,
        data_origin=DataOrigin.REAL,
    )

    change_result = ChangeDetectionResult(
        result_id="chg-res-known-001",
        pair_id="pair-s2-202601",
        method=ChangeDetectionMethod.NDVI_DIFFERENCE,
        definition=definition,
        before_scene_id="S2A_T43PGQ_20260101",
        after_scene_id="S2B_T43PGQ_20260115",
        before_asset_id="ast-prep-before",
        after_asset_id="ast-prep-after",
        difference_asset_id="ast-chg-diff",
        preview_asset_id="ast-chgprv-diff",
        classified_preview_asset_id="ast-chgcls-mask",
        metrics=metrics,
        regions=[],
        evidence=[evidence_item],
        confidence_breakdown=confidence,
        confidence=0.88,
        warnings=[
            AnalysisWarning(
                code="RESOLUTION_LIMIT_WARNING",
                severity=WarningSeverity.INFO,
                title="Sensor Resolution Limit",
                message="Features smaller than 10m x 10m pixel dimension cannot be reliably separated.",
            )
        ],
        provenance=provenance,
        data_origin=DataOrigin.REAL,
        created_at=datetime(2026, 1, 15, 11, 5, tzinfo=UTC),
    )

    scenes = [
        SatelliteScene(
            id="S2A_T43PGQ_20260101",
            provider="earth-search",
            collection="sentinel-2-c1-l2a",
            acquisition_time=datetime(2026, 1, 1, 5, 20, tzinfo=UTC),
            sensor_type=SensorType.OPTICAL,
            platform="Sentinel-2A",
            cloud_cover=2.5,
            bbox=(77.55, 12.90, 77.65, 13.05),
            resolution_meters=10.0,
        ),
        SatelliteScene(
            id="S2B_T43PGQ_20260115",
            provider="earth-search",
            collection="sentinel-2-c1-l2a",
            acquisition_time=datetime(2026, 1, 15, 5, 25, tzinfo=UTC),
            sensor_type=SensorType.OPTICAL,
            platform="Sentinel-2B",
            cloud_cover=1.8,
            bbox=(77.55, 12.90, 77.65, 13.05),
            resolution_meters=10.0,
        ),
    ]

    plan = QueryPlan(
        intent=QueryIntent.CHANGE_SUMMARY,
        scope="temporal_comparison",
        required_evidence=["change_measurement"],
        missing_inputs=[],
        approved_operations=["change_detection"],
        routing_reason="Bi-temporal change evaluation",
        context_fingerprint="fp-known-001",
    )

    answer = QueryAnswer(
        answer_id="ans-known-001",
        request_id="req-known-001",
        context_fingerprint="fp-known-001",
        answer_status=SufficiencyStatus.ANSWERABLE,
        generation_mode=GenerationMode.DETERMINISTIC_SUMMARY,
        plan=plan,
        summary="Analysis detected 0.20 km² vegetation increase (20%) and 0.10 km² decrease (10%) within the 1.00 km² valid comparison area.",
        claims=[
            AnswerClaim(
                claim_id="clm-1",
                kind=ClaimKind.MEASUREMENT,
                display_text="Vegetation-related spectral gain of 0.20 km² observed over 20% of valid comparison area.",
                evidence_ids=["evd-chg-001"],
                region_ids=[],
                validation_status=ClaimValidationStatus.VALID,
                resolved_measurement={"gain_km2": 0.20, "gain_pct_of_valid_comp": 20.0},
            )
        ],
        evidence_references=["evd-chg-001"],
        spatial_references=[],
        quality_factors=confidence.factors,
        warnings=[],
        limitations=["Sub-10m details cannot be resolved."],
        suggested_actions=[],
        data_origin=DataOrigin.REAL,
        created_at=datetime(2026, 1, 15, 11, 10, tzinfo=UTC),
    )

    # Model prediction with illustrative area of 0.03 km²
    visual_response = VisualQueryResponse(
        answer_id="vqa-ans-known-001",
        request_id="req-known-001",
        context_fingerprint="fp-known-001",
        generation_mode=GenerationMode.MOCK_DEMO,
        data_origin=DataOrigin.REAL,
        answer="Identified 1 candidate feature cluster in northern quadrant.",
        observations=[
            VisualObservation(
                observation_id="obs-001",
                input_image_id="img-s2b",
                label="Candidate Construction Feature",
                description="Model detected bright rectangular spectral cluster (area approx 0.03 km²).",
                canonical_box=[0.20, 0.30, 0.40, 0.55],
                coordinate_status=CoordinateStatus.VALID,
                map_grounding_status=MapGroundingStatus.AVAILABLE,
                associated_evidence_ids=["evd-chg-001"],
            )
        ],
        manifests=[],
        grounded_regions=[],
        evidence_references=["evd-chg-001"],
        limitations=["Visual bounding boxes are AI predictions and not measured ground truth."],
    )

    return {
        "aoi": aoi,
        "metrics": metrics,
        "change_result": change_result,
        "scenes": scenes,
        "answer": answer,
        "visual_response": visual_response,
    }


def test_known_answer_fixture_accounting(
    report_builder: ReportSnapshotBuilder, known_answer_fixture: dict[str, Any]
) -> None:
    """Verify strict mathematical accounting and denominator rules on known-answer fixture."""
    fx = known_answer_fixture
    snapshot = report_builder.build_snapshot(
        title="Known-Answer Verification Report",
        aoi=fx["aoi"],
        query="What changed between Jan 1 and Jan 15?",
        scenes=fx["scenes"],
        query_answer=fx["answer"],
        visual_response=fx["visual_response"],
        change_result=fx["change_result"],
        data_origin=DataOrigin.REAL,
    )

    summary = snapshot.quantitative_summary
    # 1. Total AOI area: 2.00 km²
    assert summary["aoi_total_area_km2"] == 2.00
    # 2. Valid comparison area: 1.00 km²
    assert summary["valid_comparison_area_km2"] == 1.00
    # 3. Valid comparison coverage is 50% of the AOI
    assert summary["valid_comparison_coverage_percent"] == 50.0
    # 4. Class percentages use valid comparison area as denominator (1.00 km²)
    # Gain: 0.20 km² -> 20%
    assert summary["gain_area_km2"] == 0.20
    assert summary["gain_percent_of_valid_comparison"] == 20.0
    # Loss: 0.10 km² -> 10%
    assert summary["loss_area_km2"] == 0.10
    assert summary["loss_percent_of_valid_comparison"] == 10.0
    # Stable: 0.65 km² -> 65%
    assert summary["stable_area_km2"] == 0.65
    assert summary["stable_percent_of_valid_comparison"] == 65.0
    # Uncertain: 0.05 km² -> 5%
    assert summary["uncertain_area_km2"] == 0.05
    assert summary["uncertain_percent_of_valid_comparison"] == 5.0
    # 5. Excluded area: 1.00 km² (50% of AOI) - NOT added to stable
    assert summary["excluded_area_km2"] == 1.00
    assert summary["excluded_percent_of_aoi"] == 50.0

    # 6. Model predicted box (0.03 km²) is segregated in observations and NEVER added to measured change totals
    assert len(snapshot.observations) == 1
    assert snapshot.observations[0].observation_id == "obs-001"
    # Verify measured gain + loss + stable equals valid comparison domain
    total_measured_valid = (
        summary["gain_area_km2"]
        + summary["loss_area_km2"]
        + summary["stable_area_km2"]
        + summary["uncertain_area_km2"]
    )
    assert pytest.approx(total_measured_valid, 0.0001) == 1.00


def test_snapshot_immutability_and_checksum(
    report_builder: ReportSnapshotBuilder, known_answer_fixture: dict[str, Any]
) -> None:
    """Verify that ReportSnapshot produces deterministic SHA-256 checksums and immutable properties."""
    fx = known_answer_fixture
    snapshot1 = report_builder.build_snapshot(
        report_id="rep-fixed-001",
        title="Immutability Verification",
        aoi=fx["aoi"],
        scenes=fx["scenes"],
        change_result=fx["change_result"],
        analysis_timestamp=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
    )

    assert snapshot1.checksum_sha256 is not None
    assert len(snapshot1.checksum_sha256) == 64
    assert snapshot1.schema_version == REPORT_SCHEMA_VERSION

    # Re-calculating checksum matches
    recomputed = report_builder.calculate_checksum(snapshot1)
    assert recomputed == snapshot1.checksum_sha256


def test_pdf_rendering_validity(
    pdf_renderer: SatQueryPdfRenderer,
    report_builder: ReportSnapshotBuilder,
    known_answer_fixture: dict[str, Any],
) -> None:
    """Verify that ReportLab produces valid, readable PDF byte streams from a snapshot."""
    fx = known_answer_fixture
    snapshot = report_builder.build_snapshot(
        title="PDF Generation Test",
        aoi=fx["aoi"],
        scenes=fx["scenes"],
        query_answer=fx["answer"],
        visual_response=fx["visual_response"],
        change_result=fx["change_result"],
    )

    pdf_bytes = pdf_renderer.render_pdf(snapshot)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    # PDF magic bytes header
    assert pdf_bytes.startswith(b"%PDF-")


def test_json_export_structure(
    report_service: ReportService,
    report_builder: ReportSnapshotBuilder,
    known_answer_fixture: dict[str, Any],
) -> None:
    """Verify that JSON export produces strict, standards-compliant JSON matching the schema."""
    fx = known_answer_fixture
    snapshot = report_builder.build_snapshot(
        report_id="rep-json-001",
        title="JSON Structure Test",
        aoi=fx["aoi"],
        scenes=fx["scenes"],
        query_answer=fx["answer"],
        change_result=fx["change_result"],
    )

    response = report_service.create_report(
        ReportRequest(
            result_id="rep-json-001",
            title="JSON Structure Test",
            format=ReportFormat.JSON,
            formats=[ReportFormat.JSON],
        ),
        snapshot=snapshot,
    )
    assert response.status == ReportStatus.COMPLETED

    raw_bytes, media_type, filename = report_service.get_export_file("rep-json-001", "json")
    assert media_type == "application/json"
    assert filename.endswith(".json")

    parsed = json.loads(raw_bytes.decode("utf-8"))
    assert parsed["report_id"] == "rep-json-001"
    assert parsed["schema_version"] == REPORT_SCHEMA_VERSION
    assert parsed["quantitative_summary"]["gain_area_km2"] == 0.20
    assert parsed["quantitative_summary"]["valid_comparison_area_km2"] == 1.00
    assert "checksum_sha256" in parsed


def _extract_pdf_text_streams(pdf_bytes: bytes) -> bytes:
    """Helper to decode and decompress all ASCII85/Flate streams in a PDF."""
    streams = re.findall(rb"stream\r?\n(.*?)~>endstream", pdf_bytes, re.DOTALL)
    decompressed: list[bytes] = []
    for st in streams:
        try:
            raw = base64.a85decode(st.strip() + b"~>", adobe=True)
            decompressed.append(zlib.decompress(raw))
        except Exception:
            continue
    return b"\n".join(decompressed)


def test_mock_and_fallback_data_labelling(
    report_builder: ReportSnapshotBuilder,
    known_answer_fixture: dict[str, Any],
    pdf_renderer: SatQueryPdfRenderer,
) -> None:
    """Verify that mock or fallback data is prominently labelled in both PDF and JSON."""
    fx = known_answer_fixture
    snapshot = report_builder.build_snapshot(
        report_id="rep-mock-001",
        title="Mock Data Label Test",
        aoi=fx["aoi"],
        scenes=fx["scenes"],
        change_result=fx["change_result"],
        data_origin=DataOrigin.MOCK,
    )

    assert snapshot.is_mock_data is True
    assert snapshot.data_origin == DataOrigin.MOCK

    # In JSON
    json_dump = snapshot.model_dump(mode="json")
    assert json_dump["is_mock_data"] is True
    assert json_dump["data_origin"] == "mock"

    # In PDF
    pdf_bytes = pdf_renderer.render_pdf(snapshot)
    decompressed_text = _extract_pdf_text_streams(pdf_bytes)
    assert b"SYNTHETIC DEMO DATA" in decompressed_text


def test_html_xss_escaping(
    report_builder: ReportSnapshotBuilder,
    known_answer_fixture: dict[str, Any],
    pdf_renderer: SatQueryPdfRenderer,
) -> None:
    """Verify that malicious text and scripts are escaped safely in PDF and JSON."""
    fx = known_answer_fixture
    malicious_title = "<script>alert('xss')</script> & <b>Bold</b>"
    malicious_query = "<img src=x onerror=alert(1)> & special characters"

    snapshot = report_builder.build_snapshot(
        report_id="rep-xss-001",
        title=malicious_title,
        query=malicious_query,
        aoi=fx["aoi"],
        scenes=fx["scenes"],
        change_result=fx["change_result"],
    )

    # PDF rendering should succeed without XML parse errors
    pdf_bytes = pdf_renderer.render_pdf(snapshot)
    assert len(pdf_bytes) > 1000

    # JSON retains literal characters safely
    json_str = snapshot.model_dump_json()
    assert "<script>" in json_str


def test_api_report_workflow(
    client: TestClient, report_builder: ReportSnapshotBuilder, known_answer_fixture: dict[str, Any]
) -> None:
    """Verify full end-to-end REST API report export workflow."""
    fx = known_answer_fixture
    snapshot = report_builder.build_snapshot(
        report_id="rep-api-001",
        title="API End-to-End Test",
        aoi=fx["aoi"],
        scenes=fx["scenes"],
        query_answer=fx["answer"],
        visual_response=fx["visual_response"],
        change_result=fx["change_result"],
    )

    # 1. POST /snapshot-export
    post_resp = client.post(
        "/api/v1/reports/snapshot-export", json=snapshot.model_dump(mode="json")
    )
    assert post_resp.status_code == 200
    data = post_resp.json()
    assert data["report_id"] == "rep-api-001"
    assert data["status"] == "completed"
    assert "pdf" in data["formats"]
    assert "json" in data["formats"]

    # 2. GET /reports/{report_id}
    status_resp = client.get("/api/v1/reports/rep-api-001")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "completed"

    # 3. GET /reports/{report_id}/snapshot
    snap_resp = client.get("/api/v1/reports/rep-api-001/snapshot")
    assert snap_resp.status_code == 200
    assert snap_resp.json()["title"] == "API End-to-End Test"

    # 4. GET /reports/{report_id}/download/pdf
    pdf_resp = client.get("/api/v1/reports/rep-api-001/download/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert "attachment" in pdf_resp.headers["content-disposition"]
    assert pdf_resp.content.startswith(b"%PDF-")

    # 5. GET /reports/{report_id}/download/json
    json_resp = client.get("/api/v1/reports/rep-api-001/download/json")
    assert json_resp.status_code == 200
    assert json_resp.headers["content-type"] == "application/json"
    assert "attachment" in json_resp.headers["content-disposition"]
    assert json_resp.json()["report_id"] == "rep-api-001"


def test_api_404_handling(client: TestClient) -> None:
    """Verify that nonexistent reports return structured 404 responses."""
    resp = client.get("/api/v1/reports/rep-nonexistent-999")
    assert resp.status_code == 404
    data = resp.json()
    error_msg = (
        data.get("error", {}).get("message", "")
        or data.get("message", "")
        or data.get("detail", "")
    )
    assert "not found" in error_msg.lower()
