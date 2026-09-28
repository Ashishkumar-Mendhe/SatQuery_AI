"""10F route-level smoke checks using labelled synthetic service and storage doubles."""

from __future__ import annotations

from typing import cast
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_geoagent_conversation_phase10d import MemoryRepository
from test_geoagent_execution_phase10c import (
    AOI,
    PRINCIPAL,
    CatalogueDouble,
    ChangeDouble,
    InferenceDouble,
    OpticalSarDouble,
    _sar,
    _scene,
)

from satquery.db.geoagent_conversations import ConversationRepository
from satquery.db.processing import ProcessingPrincipal
from satquery.inference.jobs import InferenceJobService
from satquery.processing.jobs import PreparationJobService
from satquery.processing.optical_sar_jobs import OpticalSarJobService
from satquery.providers.catalog import CatalogueProvider


def test_conversation_api_routes_selected_sources_and_invalidates_changed_context(
    ready_client: TestClient,
) -> None:
    """No raster/model/database is used; only real route orchestration is under test."""
    app = cast(FastAPI, ready_client.app)
    repo = MemoryRepository()
    inference, change, optical_sar = InferenceDouble(), ChangeDouble(), OpticalSarDouble()

    async def verified_principal(_: object) -> ProcessingPrincipal:
        return PRINCIPAL

    app.state.processing_principal_resolver = verified_principal
    app.state.geoagent_conversation_repository = cast(ConversationRepository, repo)
    app.state.inference_job_service = cast(InferenceJobService, inference)
    app.state.processing_job_service = cast(PreparationJobService, change)
    app.state.optical_sar_job_service = cast(OpticalSarJobService, optical_sar)
    app.state.catalogue_provider = cast(CatalogueProvider, CatalogueDouble())
    conversation_id = uuid4()

    def post(
        message: str, revision: int, scenes: list[dict[str, object]] | None
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "request_id": str(uuid4()),
            "expected_selection_revision": revision,
            "message": message,
        }
        if scenes is not None:
            payload["selection"] = {"aoi": AOI, "scenes": scenes}
        response = ready_client.post(
            f"/api/v1/geoagent/conversations/{conversation_id}/turns", json=payload
        )
        assert response.status_code == 200, response.text
        return cast(dict[str, object], response.json())

    def submitted(body: dict[str, object], tool: str, items: list[str]) -> None:
        assert body["status"] == "executed"
        execution = cast(dict[str, object], body["execution"])
        assert execution["status"] == "submitted"
        assert execution["job_id"] is not None and execution["result_id"] is None
        summary = cast(dict[str, object], execution["summary"])
        assert summary["tool"] == tool
        assert len(cast(str, summary["aoi_sha256"])) == 64
        sources = cast(list[dict[str, str]], summary["input_scenes"])
        assert [source["item"] for source in sources] == items

    first = post("What is visible in this image?", 0, [_scene("BEFORE", 1)])
    submitted(first, "inference_vqa", ["BEFORE"])
    assert first["selection_revision"] == 1

    ground = post("Where is the water?", 1, None)
    submitted(ground, "inference_grounding", ["BEFORE"])
    assert ground["selection_revision"] == 1

    change_turn = post(
        "What changed between these dates?", 1, [_scene("AFTER", 10), _scene("BEFORE", 1)]
    )
    submitted(change_turn, "optical_change", ["BEFORE", "AFTER"])
    assert change_turn["selection_revision"] == 2

    sar_turn = post("Summarize optical and SAR observations.", 2, [_scene("BEFORE", 1), _sar()])
    submitted(sar_turn, "optical_sar_observation", ["BEFORE", "S1_A"])
    assert sar_turn["selection_revision"] == 3

    same_area = post("What about this area?", 3, None)
    submitted(same_area, "optical_sar_observation", ["BEFORE", "S1_A"])
    assert same_area["selection_revision"] == 3

    changed_scene = post("What about this area?", 3, [_scene("AFTER", 10)])
    assert changed_scene["status"] == "clarification_required"
    assert changed_scene["missing_reference"] == "intent"
    assert changed_scene["selection_revision"] == 4
    assert len(inference.calls) == 2 and len(change.calls) == 1 and len(optical_sar.calls) == 2
    state = ready_client.get(f"/api/v1/geoagent/conversations/{conversation_id}")
    assert state.status_code == 200
    assert state.json()["last_verified"] is None
    assert state.json()["tool_references"] == []

    other = uuid4()
    isolated = ready_client.post(
        f"/api/v1/geoagent/conversations/{other}/turns",
        json={
            "request_id": str(uuid4()),
            "expected_selection_revision": 0,
            "message": "Where is water?",
        },
    )
    assert isolated.status_code == 200
    assert isolated.json()["execution"]["status"] == "clarification_required"
    assert isolated.json()["execution"]["job_id"] is None
    assert (
        ready_client.get(f"/api/v1/geoagent/conversations/{other}").json()["selection_revision"]
        == 0
    )

    app.state.inference_job_service = None
    unavailable = post("What is visible?", 4, None)
    assert cast(dict[str, object], unavailable["execution"])["status"] == "unavailable"
    assert cast(dict[str, object], unavailable["execution"])["result_id"] is None
