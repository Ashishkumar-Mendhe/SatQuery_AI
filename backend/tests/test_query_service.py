from __future__ import annotations

from datetime import UTC, datetime

import pytest

from satquery.api.schemas.analysis import (
    AOIGeometry,
    ConfidenceBreakdown,
    EvidenceItem,
    EvidenceProvenance,
    EvidenceType,
    GeometryType,
)
from satquery.api.schemas.change import (
    ChangeDetectionDefinition,
    ChangeDetectionMethod,
    ChangeDetectionResult,
    ChangeDirectionality,
    ChangeMetrics,
    ChangePixelCounts,
    ChangeRegion,
    ChangeThresholdConfig,
    ThresholdStrategy,
)
from satquery.api.schemas.preparation import RasterProvenance
from satquery.api.schemas.query import (
    GenerationMode,
    QueryRequest,
    SufficiencyStatus,
    WorkspaceContextSnapshot,
)
from satquery.providers.ai.mock import MockAIProvider
from satquery.services.query_service import QueryService


def create_mock_change_result() -> ChangeDetectionResult:
    return ChangeDetectionResult(
        result_id="chg-1",
        pair_id="pair-1",
        method=ChangeDetectionMethod.NDVI_DIFFERENCE,
        definition=ChangeDetectionDefinition(
            method=ChangeDetectionMethod.NDVI_DIFFERENCE,
            display_name="NDVI Difference",
            formula="NDVI_after - NDVI_before",
            input_type="spectral_index",
            directionality=ChangeDirectionality.BIDIRECTIONAL,
            expected_range=(-2.0, 2.0),
            default_threshold_config=ChangeThresholdConfig(),
            description="Test NDVI difference",
            limitations="Vegetation canopy response only",
        ),
        before_scene_id="S2-A",
        after_scene_id="S2-B",
        before_asset_id="ast-prep-a",
        after_asset_id="ast-prep-b",
        difference_asset_id="ast-chg-1",
        metrics=ChangeMetrics(
            gain_area_km2=0.0,
            loss_area_km2=0.2,
            stable_area_km2=0.8,
            net_change_area_km2=-0.2,
            shared_valid_area_km2=1.0,
            positive_threshold_applied=0.15,
            negative_threshold_applied=-0.15,
            threshold_strategy=ThresholdStrategy.FIXED,
            pixel_counts=ChangePixelCounts(
                total_aoi_pixels=1000,
                shared_valid_pixels=1000,
                gain_pixels=0,
                loss_pixels=200,
                stable_pixels=800,
                uncertain_pixels=0,
                gain_percent=0.0,
                loss_percent=20.0,
                stable_percent=80.0,
                uncertain_percent=0.0,
            ),
        ),
        regions=[
            ChangeRegion(
                id="reg-1",
                category="spectral_loss",
                geometry=AOIGeometry(
                    type=GeometryType.POLYGON,
                    coordinates=[[[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5], [0, 0]]],
                ),
                area_km2=0.2,
                pixel_count=200,
                mean_magnitude=-0.4,
                min_magnitude=-0.6,
                max_magnitude=-0.2,
                threshold_rule="Delta NDVI < -0.15",
                evidence_id="ev-1",
                confidence=0.85,
            )
        ],
        evidence=[
            EvidenceItem(
                id="ev-1",
                type=EvidenceType.CHANGE_MEASUREMENT,
                title="NDVI Decrease",
                description="20% decrease over 0.2 km2",
                source_scene_ids=["S2-A", "S2-B"],
                observed_at=datetime(2026, 9, 15, tzinfo=UTC),
                confidence=0.85,
                provenance=EvidenceProvenance(
                    computation="ndvi_diff",
                    processed_at=datetime(2026, 9, 20, tzinfo=UTC),
                ),
            )
        ],
        confidence_breakdown=ConfidenceBreakdown(
            overall=0.85,
            data_quality=0.85,
            temporal_quality=0.90,
            spatial_quality=1.0,
            model_confidence=0.85,
            evidence_agreement=0.85,
            methodology="Standard multi-factor score",
        ),
        confidence=0.85,
        provenance=RasterProvenance(
            pipeline_version="1.0.0",
            source_asset_ids=["ast-prep-a", "ast-prep-b"],
            source_scene_ids=["S2-A", "S2-B"],
            operations=[],
            parameters={},
            software="SatQuery",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_milliseconds=100.0,
        ),
        created_at=datetime.now(UTC),
    )


@pytest.mark.anyio
async def test_query_service_change_answer_deterministic() -> None:
    service = QueryService()
    aoi = AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
    )
    snapshot = WorkspaceContextSnapshot(
        snapshot_id="snap-1",
        fingerprint="fp123",
        aoi_geometry=aoi,
        active_change_result_id="chg-1",
        scene_ids=["S2-A", "S2-B"],
    )
    req = QueryRequest(
        question="What changed between these two dates?",
        context_snapshot=snapshot,
    )

    override_change = create_mock_change_result()

    answer = await service.answer_query(
        req,
        override_change_result=override_change,
        ai_provider_override=None,
    )

    assert answer.answer_status == SufficiencyStatus.ANSWERABLE
    assert answer.generation_mode == GenerationMode.DETERMINISTIC_SUMMARY
    assert "20.0% of valid area" in answer.summary
    assert len(answer.claims) >= 1
    assert "reg-1" in answer.spatial_references


@pytest.mark.anyio
async def test_query_service_with_mock_ai() -> None:
    service = QueryService()
    mock_ai = MockAIProvider()
    aoi = AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
    )
    snapshot = WorkspaceContextSnapshot(
        snapshot_id="snap-1",
        fingerprint="fp123",
        aoi_geometry=aoi,
        active_change_result_id="chg-1",
        scene_ids=["S2-A", "S2-B"],
    )
    req = QueryRequest(
        question="What changed between these two dates?",
        context_snapshot=snapshot,
    )

    override_change = create_mock_change_result()

    answer = await service.answer_query(
        req,
        override_change_result=override_change,
        ai_provider_override=mock_ai,
    )

    assert answer.answer_status == SufficiencyStatus.ANSWERABLE
    assert answer.generation_mode == GenerationMode.MOCK_DEMO
    assert len(answer.processing_trace) >= 4
