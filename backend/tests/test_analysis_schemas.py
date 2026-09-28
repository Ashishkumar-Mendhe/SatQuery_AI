"""Comprehensive unit and contract-parity tests for SatQuery analysis schemas."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from satquery.api.schemas.analysis import (
    AnalysisJobStatus,
    AnalysisMode,
    AnalysisRequest,
    AnalysisResponse,
    AOIGeometry,
    APIError,
    APIErrorCode,
    CloudCoverFilter,
    DateRange,
    Finding,
    GeometryType,
    OverlayFeature,
    OverlayType,
    ReportFormat,
)
from satquery.api.schemas.reports import ReportRequest, ReportResponse

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_polygon_aoi() -> dict[str, Any]:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [77.58, 12.96],
                [77.62, 12.96],
                [77.62, 13.01],
                [77.58, 13.01],
                [77.58, 12.96],
            ]
        ],
        "bbox": [77.58, 12.96, 77.62, 13.01],
        "crs": "EPSG:4326",
        "area_km2": 21.45,
    }


@pytest.fixture
def valid_satellite_scene(valid_polygon_aoi: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "S2B_T43PGQ_20251223T051848_L2A",
        "provider": "earth-search",
        "collection": "sentinel-2-c1-l2a",
        "acquisition_time": "2025-12-23T05:25:18.674Z",
        "sensor_type": "multispectral",
        "platform": "Sentinel-2B",
        "cloud_cover": 4.3,
        "geometry": valid_polygon_aoi,
        "bbox": [77.58, 12.96, 77.62, 13.01],
        "thumbnail_url": "https://example.com/thumb.jpg",
        "preview_url": "https://example.com/preview.jpg",
        "available_bands": ["B02", "B03", "B04", "B08", "B11"],
        "resolution_meters": 10.0,
        "quality_score": 0.95,
        "metadata": {"sun_elevation": 45.2},
    }


@pytest.fixture
def valid_confidence_breakdown() -> dict[str, Any]:
    return {
        "overall": 0.87,
        "data_quality": 1.00,
        "temporal_quality": 0.90,
        "spatial_quality": 0.85,
        "model_confidence": 0.80,
        "evidence_agreement": 0.85,
        "factors": [
            {
                "code": "DATA_QUALITY",
                "label": "Level-2A Surface Reflectance",
                "score": 1.0,
                "weight": 0.35,
                "explanation": "High quality bottom-of-atmosphere reflectance data.",
                "evidence_ids": ["evd_01"],
            }
        ],
        "methodology": "Multi-factor weighted geometric index assessment.",
        "limitations": ["Cloud shadow may affect small portions of eastern sector."],
    }


@pytest.fixture
def valid_evidence_item(valid_polygon_aoi: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "evd_01",
        "type": "spectral_measurement",
        "title": "Mean NDVI in AOI",
        "description": "Calculated mean NDVI over active vegetation zones.",
        "source_scene_ids": ["S2B_T43PGQ_20251223T051848_L2A"],
        "geometry": valid_polygon_aoi,
        "measurement": {"ndvi_mean": 0.54, "valid_pixels": 45000},
        "observed_at": "2025-12-23T05:25:18.674Z",
        "confidence": 0.92,
        "provenance": {
            "computation": "numpy_band_math",
            "algorithm_name": "NDVI_B08_B04",
            "version": "1.0.0",
            "processed_at": "2026-09-18T13:00:00Z",
            "parameters": {"scale": 0.0001},
        },
    }


@pytest.fixture
def valid_finding() -> dict[str, Any]:
    return {
        "id": "fnd_01",
        "title": "Healthy Vegetation Concentration",
        "description": "Dense, healthy canopy detected across 65% of the AOI.",
        "severity": "informational",
        "category": "vegetation",
        "evidence_ids": ["evd_01"],
        "confidence": 0.88,
        "interpretation": "Vegetation index indicates robust post-monsoon foliage.",
        "limitations": ["Sensor 10m ground resolution limits individual tree detection."],
        "recommended_follow_up": ["Monitor again in late dry season (March)."],
    }


# ---------------------------------------------------------------------------
# Tests: AOIGeometry
# ---------------------------------------------------------------------------


def test_valid_polygon_aoi(valid_polygon_aoi: dict[str, Any]) -> None:
    aoi = AOIGeometry.model_validate(valid_polygon_aoi)
    assert aoi.type == GeometryType.POLYGON
    assert aoi.crs == "EPSG:4326"
    assert aoi.area_km2 == 21.45


def test_invalid_aoi_unclosed_polygon(valid_polygon_aoi: dict[str, Any]) -> None:
    invalid = valid_polygon_aoi.copy()
    invalid["coordinates"] = [
        [
            [77.58, 12.96],
            [77.62, 12.96],
            [77.62, 13.01],
            [77.58, 13.01],
            # missing closing vertex [77.58, 12.96]
            [77.59, 12.99],
        ]
    ]
    with pytest.raises(ValidationError) as exc:
        AOIGeometry.model_validate(invalid)
    assert "must be closed" in str(exc.value)


def test_invalid_aoi_out_of_bounds_coordinate() -> None:
    with pytest.raises(ValidationError) as exc:
        AOIGeometry.model_validate(
            {
                "type": "Point",
                "coordinates": [195.0, 12.96],  # Lon > 180
            }
        )
    assert "longitude" in str(exc.value)


# ---------------------------------------------------------------------------
# Tests: DateRange & CloudCoverFilter
# ---------------------------------------------------------------------------


def test_valid_date_range() -> None:
    dr = DateRange.model_validate({"start_date": "2025-01-01", "end_date": "2025-12-31"})
    assert dr.start_date == "2025-01-01"


def test_invalid_date_range_inverted() -> None:
    with pytest.raises(ValidationError) as exc:
        DateRange.model_validate({"start_date": "2025-12-31", "end_date": "2025-01-01"})
    assert "start_date must not be after end_date" in str(exc.value)


def test_cloud_cover_filter() -> None:
    cc = CloudCoverFilter.model_validate(
        {
            "maximum_percent": 30.0,
            "preferred_maximum_percent": 10.0,
        }
    )
    assert cc.maximum_percent == 30.0
    assert cc.preferred_maximum_percent == 10.0

    with pytest.raises(ValidationError) as exc:
        CloudCoverFilter.model_validate(
            {
                "maximum_percent": 20.0,
                "preferred_maximum_percent": 40.0,
            }
        )
    assert "preferred_maximum_percent must not exceed maximum_percent" in str(exc.value)


# ---------------------------------------------------------------------------
# Tests: AnalysisRequest & Mode Validation
# ---------------------------------------------------------------------------


def test_valid_single_scene_analysis_request(valid_polygon_aoi: dict[str, Any]) -> None:
    req = AnalysisRequest.model_validate(
        {
            "question": "What is the vegetation health in this area?",
            "mode": "visual_question_answering",
            "aoi": valid_polygon_aoi,
        }
    )
    assert req.mode == AnalysisMode.VISUAL_QUESTION_ANSWERING
    assert req.question == "What is the vegetation health in this area?"
    assert req.options.include_overlays is True


def test_blank_question_rejected(valid_polygon_aoi: dict[str, Any]) -> None:
    with pytest.raises(ValidationError) as exc:
        AnalysisRequest.model_validate(
            {
                "question": "   ",
                "mode": "visual_question_answering",
                "aoi": valid_polygon_aoi,
            }
        )
    assert "at least 3" in str(exc.value)


def test_change_detection_requires_two_scenes_or_date_range(
    valid_polygon_aoi: dict[str, Any],
) -> None:
    # Missing both scenes and date_range
    with pytest.raises(ValidationError) as exc:
        AnalysisRequest.model_validate(
            {
                "question": "What changed between these scenes?",
                "mode": "change_detection",
                "aoi": valid_polygon_aoi,
            }
        )
    assert "Change detection requires" in str(exc.value)

    # Identical before and after scene IDs rejected
    with pytest.raises(ValidationError) as exc:
        AnalysisRequest.model_validate(
            {
                "question": "What changed between these scenes?",
                "mode": "change_detection",
                "aoi": valid_polygon_aoi,
                "scene_selection": {
                    "before_scene_id": "scene_01",
                    "after_scene_id": "scene_01",
                },
            }
        )
    assert "distinct" in str(exc.value)

    # Valid change detection request
    valid_req = AnalysisRequest.model_validate(
        {
            "question": "What changed between these scenes?",
            "mode": "change_detection",
            "aoi": valid_polygon_aoi,
            "scene_selection": {
                "before_scene_id": "scene_01",
                "after_scene_id": "scene_02",
            },
        }
    )
    assert valid_req.mode == AnalysisMode.CHANGE_DETECTION


# ---------------------------------------------------------------------------
# Tests: Overlays & Conditional Validation
# ---------------------------------------------------------------------------


def test_overlay_feature_validation(valid_polygon_aoi: dict[str, Any]) -> None:
    # Valid vector overlay
    vec_overlay = OverlayFeature.model_validate(
        {
            "id": "ovl_01",
            "type": "polygon",
            "title": "Vegetation Mask",
            "geometry": valid_polygon_aoi,
            "style": {"fill_color": "#10b981", "fill_opacity": 0.6},
        }
    )
    assert vec_overlay.type == OverlayType.POLYGON

    # Vector overlay missing geometry
    with pytest.raises(ValidationError) as exc:
        OverlayFeature.model_validate(
            {
                "id": "ovl_02",
                "type": "polygon",
                "title": "Invalid Vector Mask",
            }
        )
    assert "requires a geometry" in str(exc.value)

    # Valid raster overlay with bounds and URL
    rast_overlay = OverlayFeature.model_validate(
        {
            "id": "ovl_03",
            "type": "raster",
            "title": "NDVI Heatmap",
            "raster_url": "/api/v1/imagery/tiles/tile_01/{z}/{x}/{y}.png",
            "bounds": [77.58, 12.96, 77.62, 13.01],
        }
    )
    assert rast_overlay.type == OverlayType.RASTER


# ---------------------------------------------------------------------------
# Tests: Findings & Evidence
# ---------------------------------------------------------------------------


def test_finding_requires_evidence_ids(valid_finding: dict[str, Any]) -> None:
    f = Finding.model_validate(valid_finding)
    assert len(f.evidence_ids) >= 1

    invalid = valid_finding.copy()
    invalid["evidence_ids"] = []
    with pytest.raises(ValidationError):
        Finding.model_validate(invalid)


# ---------------------------------------------------------------------------
# Tests: Full AnalysisResponse Parity
# ---------------------------------------------------------------------------


def test_valid_complete_analysis_response(
    valid_satellite_scene: dict[str, Any],
    valid_finding: dict[str, Any],
    valid_evidence_item: dict[str, Any],
    valid_confidence_breakdown: dict[str, Any],
) -> None:
    resp = AnalysisResponse.model_validate(
        {
            "request_id": "req_123456",
            "job_id": "job_987654",
            "status": "completed",
            "answer": "Significant vegetation increase detected in the northern sector.",
            "answer_type": "text_and_evidence",
            "findings": [valid_finding],
            "evidence": [valid_evidence_item],
            "spectral_result": {
                "scene_id": "S2B_T43PGQ_20251223T051848_L2A",
                "indices": [
                    {
                        "index_name": "NDVI",
                        "mean": 0.54,
                        "minimum": -0.1,
                        "maximum": 0.82,
                        "standard_deviation": 0.15,
                        "valid_pixel_count": 45000,
                        "unit": "index_value",
                        "scene_id": "S2B_T43PGQ_20251223T051848_L2A",
                    }
                ],
                "summary": "Overall healthy vegetation with high NDVI values.",
                "evidence_ids": ["evd_01"],
                "confidence": 0.90,
                "warnings": [],
            },
            "change_result": None,
            "overlays": [],
            "confidence": valid_confidence_breakdown,
            "warnings": [
                {
                    "code": "HIGH_CLOUD_COVER",
                    "severity": "info",
                    "title": "Minor Cloud Cover",
                    "message": "Cloud cover is 4.3%, within safe limits.",
                }
            ],
            "scenes": [valid_satellite_scene],
            "processing_metadata": {
                "processing_started_at": "2026-09-18T13:00:00Z",
                "processing_completed_at": "2026-09-18T13:00:05Z",
                "duration_milliseconds": 5000,
                "pipeline_version": "1.0.0",
                "algorithms": ["NDVI_Processor", "Gemini_VLM"],
                "ai_provider": "gemini",
                "ai_model": "gemini-2.0-flash",
                "is_mock_data": False,
            },
        }
    )
    assert resp.request_id == "req_123456"
    assert resp.status == AnalysisJobStatus.COMPLETED
    assert len(resp.findings) == 1
    assert resp.confidence.overall == 0.87


# ---------------------------------------------------------------------------
# Tests: Report Contracts & API Error
# ---------------------------------------------------------------------------


def test_report_contracts() -> None:
    req = ReportRequest.model_validate(
        {
            "analysis_job_id": "job_987654",
            "format": "pdf",
            "title": "Comprehensive Land Analysis Report",
            "include_map": True,
        }
    )
    assert req.format == ReportFormat.PDF
    assert req.include_map is True

    res = ReportResponse.model_validate(
        {
            "report_id": "rep_112233",
            "analysis_job_id": "job_987654",
            "status": "generated",
            "format": "pdf",
            "download_url": "/api/v1/reports/download/rep_112233.pdf",
            "created_at": "2026-09-18T13:05:00Z",
            "file_size_bytes": 1048576,
        }
    )
    assert res.report_id == "rep_112233"
    assert res.status == "generated"


def test_api_error() -> None:
    err = APIError.model_validate(
        {
            "code": "INVALID_AOI",
            "message": "The AOI coordinates are out of bounds.",
            "status": 422,
            "request_id": "req_err_01",
            "field_errors": [{"field": "aoi.coordinates", "message": "Longitude out of range"}],
            "retryable": False,
        }
    )
    assert err.code == APIErrorCode.INVALID_AOI
    assert err.status == 422
    assert len(err.field_errors) == 1
