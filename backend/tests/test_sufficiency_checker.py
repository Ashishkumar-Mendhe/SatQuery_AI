from __future__ import annotations

from satquery.api.schemas.analysis import AOIGeometry, GeometryType
from satquery.api.schemas.query import (
    QueryIntent,
    QueryPlan,
    SufficiencyStatus,
    WorkspaceContextSnapshot,
)
from satquery.services.evidence_retriever import EvidenceBundle
from satquery.services.sufficiency_checker import SufficiencyChecker


def test_sufficiency_no_aoi() -> None:
    checker = SufficiencyChecker()
    snapshot = WorkspaceContextSnapshot(
        snapshot_id="snap-1",
        fingerprint="fp123",
        aoi_geometry=None,
    )
    plan = QueryPlan(
        intent=QueryIntent.CHANGE_SUMMARY,
        scope="bi_temporal",
        context_fingerprint="fp123",
        routing_reason="test",
    )
    bundle = EvidenceBundle()

    status, actions = checker.check(snapshot, plan, bundle)
    assert status == SufficiencyStatus.INSUFFICIENT_EVIDENCE
    assert any(a.action_id == "draw_aoi" for a in actions)


def test_sufficiency_needs_processing() -> None:
    checker = SufficiencyChecker()
    aoi = AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
    )
    snapshot = WorkspaceContextSnapshot(
        snapshot_id="snap-1",
        fingerprint="fp123",
        aoi_geometry=aoi,
        scene_ids=["S2-A", "S2-B"],
        active_change_result_id=None,
    )
    plan = QueryPlan(
        intent=QueryIntent.CHANGE_SUMMARY,
        scope="bi_temporal",
        context_fingerprint="fp123",
        routing_reason="test",
    )
    bundle = EvidenceBundle()

    status, actions = checker.check(snapshot, plan, bundle)
    assert status == SufficiencyStatus.NEEDS_PROCESSING
    assert any(a.action_id == "run_change_detection" for a in actions)


def test_sufficiency_answerable_with_evidence() -> None:
    checker = SufficiencyChecker()
    aoi = AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
    )
    snapshot = WorkspaceContextSnapshot(
        snapshot_id="snap-1",
        fingerprint="fp123",
        aoi_geometry=aoi,
        active_change_result_id="chg-1",
    )
    plan = QueryPlan(
        intent=QueryIntent.CHANGE_SUMMARY,
        scope="bi_temporal",
        context_fingerprint="fp123",
        routing_reason="test",
    )
    bundle = EvidenceBundle(measurements={"change_detection": {"method": "ndvi_difference"}})

    status, actions = checker.check(snapshot, plan, bundle)
    assert status == SufficiencyStatus.ANSWERABLE
    assert len(actions) == 0
