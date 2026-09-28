from __future__ import annotations

from satquery.api.schemas.query import QueryIntent, WorkspaceContextSnapshot
from satquery.services.query_router import QueryRouter


def test_router_change_summary() -> None:
    router = QueryRouter()
    snapshot = WorkspaceContextSnapshot(
        snapshot_id="snap-1",
        fingerprint="fp123",
        active_change_result_id="chg-res-1",
        scene_ids=["S2-A", "S2-B"],
    )
    plan = router.route("What changed between these two dates?", snapshot)
    assert plan.intent == QueryIntent.CHANGE_SUMMARY
    assert "change_measurement" in plan.required_evidence
    assert len(plan.missing_inputs) == 0


def test_router_multimodal_summary() -> None:
    router = QueryRouter()
    snapshot = WorkspaceContextSnapshot(
        snapshot_id="snap-1",
        fingerprint="fp123",
        active_fusion_result_id="fus-res-1",
    )
    plan = router.route("Do optical and radar observations agree?", snapshot)
    assert plan.intent == QueryIntent.MULTIMODAL_SUMMARY
    assert "multimodal_fusion" in plan.required_evidence


def test_router_locate_evidence() -> None:
    router = QueryRouter()
    snapshot = WorkspaceContextSnapshot(
        snapshot_id="snap-1",
        fingerprint="fp123",
        active_change_result_id="chg-res-1",
    )
    plan = router.route("Where did the vegetation-related response decrease?", snapshot)
    assert plan.intent == QueryIntent.LOCATE_EVIDENCE


def test_router_explain_quality() -> None:
    router = QueryRouter()
    snapshot = WorkspaceContextSnapshot(
        snapshot_id="snap-1",
        fingerprint="fp123",
    )
    plan = router.route("Why is confidence low?", snapshot)
    assert plan.intent == QueryIntent.EXPLAIN_QUALITY


def test_router_spectral_summary() -> None:
    router = QueryRouter()
    snapshot = WorkspaceContextSnapshot(
        snapshot_id="snap-1",
        fingerprint="fp123",
        active_spectral_result_id="spec-res-1",
    )
    plan = router.route("Summarize vegetation and NDVI response over this scene.", snapshot)
    assert plan.intent == QueryIntent.SPECTRAL_SUMMARY


def test_router_unsupported() -> None:
    router = QueryRouter()
    snapshot = WorkspaceContextSnapshot(
        snapshot_id="snap-1",
        fingerprint="fp123",
    )
    plan = router.route("What is the weather forecast for tomorrow?", snapshot)
    assert plan.intent == QueryIntent.UNSUPPORTED
    assert plan.scope == "out_of_domain"
