"""Deterministic unit tests for temporal pairing, spatial overlap, and compatibility validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from satquery.api.schemas.analysis import (
    AOIGeometry,
    GeometryType,
    SatelliteScene,
    SensorType,
)
from satquery.api.schemas.temporal import (
    PairCompatibilityStatus,
    PairingPreferences,
    TemporalSearchRequest,
    TemporalWindow,
)
from satquery.services.temporal_pairing import (
    calculate_spatial_overlap_metrics,
    recommend_best_temporal_pair,
    validate_temporal_pair,
)

# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_aoi() -> AOIGeometry:
    """Sample rectangular AOI around Bengaluru (approx 0.04 deg box)."""
    return AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=[
            [
                [77.58, 12.95],
                [77.62, 12.95],
                [77.62, 12.99],
                [77.58, 12.99],
                [77.58, 12.95],
            ]
        ],
        bbox=(77.58, 12.95, 77.62, 12.99),
    )


@pytest.fixture
def optical_scene_before() -> SatelliteScene:
    """Optical baseline scene from Sentinel-2A with low cloud cover."""
    return SatelliteScene(
        id="S2A_MSIL2A_20250101T052000_N0500_R019",
        provider="earth-search",
        collection="sentinel-2-c1-l2a",
        acquisition_time=datetime(2025, 1, 1, 5, 20, 0, tzinfo=UTC),
        sensor_type=SensorType.MULTISPECTRAL,
        platform="Sentinel-2A",
        cloud_cover=2.5,
        bbox=(77.50, 12.80, 77.70, 13.10),
        available_bands=["B02", "B03", "B04", "B08", "B11", "B12"],
        resolution_meters=10.0,
        metadata={"data_origin": "real"},
    )


@pytest.fixture
def optical_scene_after() -> SatelliteScene:
    """Optical comparative scene from Sentinel-2B with low cloud cover."""
    return SatelliteScene(
        id="S2B_MSIL2A_20250121T052000_N0500_R019",
        provider="earth-search",
        collection="sentinel-2-c1-l2a",
        acquisition_time=datetime(2025, 1, 21, 5, 20, 0, tzinfo=UTC),
        sensor_type=SensorType.MULTISPECTRAL,
        platform="Sentinel-2B",
        cloud_cover=3.8,
        bbox=(77.50, 12.80, 77.70, 13.10),
        available_bands=["B02", "B03", "B04", "B08", "B11", "B12"],
        resolution_meters=10.0,
        metadata={"data_origin": "real"},
    )


# ---------------------------------------------------------------------------
# Temporal Window Validation Tests
# ---------------------------------------------------------------------------


def test_temporal_window_valid() -> None:
    window = TemporalWindow(start_date="2025-01-01", end_date="2025-01-31", label="before")
    assert window.start_date == "2025-01-01"
    assert window.end_date == "2025-01-31"
    assert window.label == "before"


def test_temporal_window_reversed_fails() -> None:
    with pytest.raises(ValidationError) as exc_info:
        TemporalWindow(start_date="2025-02-01", end_date="2025-01-01")
    assert "cannot be after" in str(exc_info.value)


def test_temporal_window_exceeds_max_days_fails() -> None:
    with pytest.raises(ValidationError) as exc_info:
        TemporalWindow(start_date="2020-01-01", end_date="2023-01-01")
    assert "exceeds maximum allowed limit" in str(exc_info.value)


def test_temporal_window_target_date() -> None:
    window = TemporalWindow(
        start_date="2025-01-01",
        end_date="2025-01-31",
        target_date="2025-01-15",
    )
    assert window.target_date == "2025-01-15"

    with pytest.raises(ValidationError):
        TemporalWindow(
            start_date="2025-01-01",
            end_date="2025-01-31",
            target_date="2025-02-15",
        )


def test_temporal_search_request_window_order(sample_aoi: AOIGeometry) -> None:
    before_w = TemporalWindow(start_date="2025-01-01", end_date="2025-01-31", label="before")
    after_w = TemporalWindow(start_date="2025-02-01", end_date="2025-02-28", label="after")

    req = TemporalSearchRequest(aoi=sample_aoi, before_window=before_w, after_window=after_w)
    assert req.before_window.start_date == "2025-01-01"

    # Reversed search windows (before starts after after starts)
    with pytest.raises(ValidationError):
        TemporalSearchRequest(aoi=sample_aoi, before_window=after_w, after_window=before_w)


# ---------------------------------------------------------------------------
# Spatial Overlap & Intersection Tests
# ---------------------------------------------------------------------------


def test_spatial_overlap_full_coverage(
    sample_aoi: AOIGeometry,
    optical_scene_before: SatelliteScene,
    optical_scene_after: SatelliteScene,
) -> None:
    metrics = calculate_spatial_overlap_metrics(
        sample_aoi, optical_scene_before, optical_scene_after
    )
    assert metrics.before_aoi_coverage_percent == 100.0
    assert metrics.after_aoi_coverage_percent == 100.0
    assert metrics.mutual_aoi_coverage_percent == 100.0
    assert metrics.scene_overlap_percent == 100.0
    assert metrics.shared_bbox is not None


def test_spatial_overlap_disjoint_scene(
    sample_aoi: AOIGeometry, optical_scene_before: SatelliteScene
) -> None:
    disjoint_scene = SatelliteScene(
        id="S2B_DISJOINT",
        provider="earth-search",
        collection="sentinel-2-c1-l2a",
        acquisition_time=datetime(2025, 2, 1, tzinfo=UTC),
        sensor_type=SensorType.MULTISPECTRAL,
        bbox=(10.0, 10.0, 11.0, 11.0),
    )
    metrics = calculate_spatial_overlap_metrics(sample_aoi, optical_scene_before, disjoint_scene)
    assert metrics.mutual_aoi_coverage_percent == 0.0
    assert metrics.after_aoi_coverage_percent == 0.0


# ---------------------------------------------------------------------------
# Optical Compatibility Tests
# ---------------------------------------------------------------------------


def test_optical_strong_match(
    sample_aoi: AOIGeometry,
    optical_scene_before: SatelliteScene,
    optical_scene_after: SatelliteScene,
) -> None:
    result = validate_temporal_pair(sample_aoi, optical_scene_before, optical_scene_after)
    assert result.valid is True
    assert result.status == PairCompatibilityStatus.COMPATIBLE
    assert result.compatibility_score >= 0.85
    assert result.temporal_gap_days == 20.0
    assert len(result.issues) == 0
    assert result.normalized_selection is not None
    assert result.normalized_selection.before_scene_id == optical_scene_before.id
    assert result.normalized_selection.after_scene_id == optical_scene_after.id


def test_optical_high_cloud_cover_warning(
    sample_aoi: AOIGeometry,
    optical_scene_before: SatelliteScene,
    optical_scene_after: SatelliteScene,
) -> None:
    cloudy_after = optical_scene_after.model_copy(update={"cloud_cover": 45.0})
    result = validate_temporal_pair(sample_aoi, optical_scene_before, cloudy_after)
    assert result.valid is True
    assert result.status == PairCompatibilityStatus.COMPATIBLE_WITH_WARNINGS
    assert any(i.code == "HIGH_CLOUD_COVER" for i in result.issues)
    assert any(i.code == "CLOUD_COVER_MISMATCH" for i in result.issues)


def test_optical_missing_required_bands_blocks(
    sample_aoi: AOIGeometry,
    optical_scene_before: SatelliteScene,
    optical_scene_after: SatelliteScene,
) -> None:
    missing_band_scene = optical_scene_after.model_copy(update={"available_bands": ["B02", "B03"]})
    prefs = PairingPreferences(required_bands=["B04", "B08"])
    result = validate_temporal_pair(
        sample_aoi, optical_scene_before, missing_band_scene, pairing_preferences=prefs
    )
    assert result.valid is False
    assert result.status == PairCompatibilityStatus.INCOMPATIBLE
    assert any(i.code == "REQUIRED_BANDS_MISSING" and i.blocking for i in result.issues)


def test_optical_different_collections_warning(
    sample_aoi: AOIGeometry,
    optical_scene_before: SatelliteScene,
    optical_scene_after: SatelliteScene,
) -> None:
    other_collection = optical_scene_after.model_copy(update={"collection": "landsat-8-c2-l2"})
    result = validate_temporal_pair(sample_aoi, optical_scene_before, other_collection)
    assert any(i.code == "DIFFERENT_COLLECTIONS" for i in result.issues)


# ---------------------------------------------------------------------------
# SAR Compatibility Tests
# ---------------------------------------------------------------------------


def test_sar_compatible_pair(sample_aoi: AOIGeometry) -> None:
    sar_before = SatelliteScene(
        id="S1A_IW_GRDH_20250101",
        provider="copernicus_dataspace",
        collection="sentinel-1-grd",
        acquisition_time=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        sensor_type=SensorType.SAR,
        platform="Sentinel-1A",
        bbox=(77.50, 12.80, 77.70, 13.10),
        available_bands=["VV", "VH"],
        resolution_meters=10.0,
        metadata={
            "data_origin": "real",
            "polarizations": ["VV", "VH"],
            "orbit_direction": "ASCENDING",
        },
    )
    sar_after = SatelliteScene(
        id="S1B_IW_GRDH_20250113",
        provider="copernicus_dataspace",
        collection="sentinel-1-grd",
        acquisition_time=datetime(2025, 1, 13, 12, 0, 0, tzinfo=UTC),
        sensor_type=SensorType.SAR,
        platform="Sentinel-1B",
        bbox=(77.50, 12.80, 77.70, 13.10),
        available_bands=["VV", "VH"],
        resolution_meters=10.0,
        metadata={
            "data_origin": "real",
            "polarizations": ["VV", "VH"],
            "orbit_direction": "ASCENDING",
        },
    )
    result = validate_temporal_pair(sample_aoi, sar_before, sar_after)
    assert result.valid is True
    assert result.status == PairCompatibilityStatus.COMPATIBLE
    assert not any(i.code == "HIGH_CLOUD_COVER" for i in result.issues)


def test_sar_polarization_mismatch_blocks(sample_aoi: AOIGeometry) -> None:
    sar_before = SatelliteScene(
        id="S1A_VV",
        provider="copernicus_dataspace",
        collection="sentinel-1-grd",
        acquisition_time=datetime(2025, 1, 1, tzinfo=UTC),
        sensor_type=SensorType.SAR,
        bbox=(77.50, 12.80, 77.70, 13.10),
        metadata={"data_origin": "real", "polarizations": ["VV"]},
    )
    sar_after = SatelliteScene(
        id="S1A_HH",
        provider="copernicus_dataspace",
        collection="sentinel-1-grd",
        acquisition_time=datetime(2025, 1, 13, tzinfo=UTC),
        sensor_type=SensorType.SAR,
        bbox=(77.50, 12.80, 77.70, 13.10),
        metadata={"data_origin": "real", "polarizations": ["HH"]},
    )
    result = validate_temporal_pair(sample_aoi, sar_before, sar_after)
    assert result.valid is False
    assert any(i.code == "POLARIZATION_MISMATCH" and i.blocking for i in result.issues)


# ---------------------------------------------------------------------------
# Cross-Sensor & Blocking Incompatibility Tests
# ---------------------------------------------------------------------------


def test_cross_sensor_optical_sar_blocks(
    sample_aoi: AOIGeometry, optical_scene_before: SatelliteScene
) -> None:
    sar_after = SatelliteScene(
        id="S1A_SAR",
        provider="copernicus_dataspace",
        collection="sentinel-1-grd",
        acquisition_time=datetime(2025, 1, 15, tzinfo=UTC),
        sensor_type=SensorType.SAR,
        bbox=(77.50, 12.80, 77.70, 13.10),
        metadata={"data_origin": "real"},
    )
    result = validate_temporal_pair(sample_aoi, optical_scene_before, sar_after)
    assert result.valid is False
    assert result.status == PairCompatibilityStatus.INCOMPATIBLE
    assert any(
        i.code == "CROSS_SENSOR_PAIR_REQUIRES_MULTIMODAL_PIPELINE" and i.blocking
        for i in result.issues
    )


def test_same_scene_selected_blocks(
    sample_aoi: AOIGeometry, optical_scene_before: SatelliteScene
) -> None:
    result = validate_temporal_pair(sample_aoi, optical_scene_before, optical_scene_before)
    assert result.valid is False
    assert any(i.code == "SAME_SCENE_SELECTED" and i.blocking for i in result.issues)


def test_temporal_order_reversed_blocks(
    sample_aoi: AOIGeometry,
    optical_scene_before: SatelliteScene,
    optical_scene_after: SatelliteScene,
) -> None:
    result = validate_temporal_pair(sample_aoi, optical_scene_after, optical_scene_before)
    assert result.valid is False
    assert any(i.code == "TEMPORAL_ORDER_REVERSED" and i.blocking for i in result.issues)


def test_mixed_data_origins_blocks(
    sample_aoi: AOIGeometry,
    optical_scene_before: SatelliteScene,
    optical_scene_after: SatelliteScene,
) -> None:
    mock_after = optical_scene_after.model_copy(update={"metadata": {"data_origin": "mock"}})
    result = validate_temporal_pair(sample_aoi, optical_scene_before, mock_after)
    assert result.valid is False
    assert any(i.code == "MIXED_DATA_ORIGIN" and i.blocking for i in result.issues)


# ---------------------------------------------------------------------------
# Recommendation Tests
# ---------------------------------------------------------------------------


def test_recommend_best_temporal_pair(
    sample_aoi: AOIGeometry,
    optical_scene_before: SatelliteScene,
    optical_scene_after: SatelliteScene,
) -> None:
    cloudy_after = optical_scene_after.model_copy(
        update={
            "id": "S2B_CLOUDY_AFTER",
            "cloud_cover": 65.0,
            "acquisition_time": datetime(2025, 1, 15, tzinfo=UTC),
        }
    )
    clean_after = optical_scene_after.model_copy(
        update={
            "id": "S2B_CLEAN_AFTER",
            "cloud_cover": 1.2,
            "acquisition_time": datetime(2025, 1, 25, tzinfo=UTC),
        }
    )

    recommended = recommend_best_temporal_pair(
        aoi=sample_aoi,
        before_scenes=[optical_scene_before],
        after_scenes=[cloudy_after, clean_after],
    )
    assert recommended is not None
    assert recommended.before_scene_id == optical_scene_before.id
    assert recommended.after_scene_id == clean_after.id
    assert recommended.compatibility_score >= 0.85
