"""Synthetic 10D context checks; no real scene, model or database is claimed."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from satquery.agent import conversation as module
from satquery.agent.conversation import (
    ConversationConflictError,
    execute_conversation_turn,
    resolve_turn,
)
from satquery.agent.execution import GeoAgentServices
from satquery.api.schemas.geoagent import SelectedGeoScene
from satquery.api.schemas.geoagent_conversation import (
    ConversationSelection,
    ConversationState,
    ConversationToolReference,
    ConversationTurnRequest,
    VerifiedAnalysisReference,
)
from satquery.api.schemas.geoagent_execution import (
    GeoAgentExecutionResponse,
    GeoAgentExecutionSummary,
)
from satquery.db.geoagent_conversations import ConversationRepository, VersionedConversation
from satquery.db.processing import ProcessingPrincipal
from satquery.inference.jobs import InferenceJobService

AOI = {
    "type": "Polygon",
    "coordinates": [[[77.5, 12.9], [77.51, 12.9], [77.51, 12.91], [77.5, 12.91], [77.5, 12.9]]],
}
OTHER_AOI = {
    "type": "Polygon",
    "coordinates": [[[78.5, 12.9], [78.51, 12.9], [78.51, 12.91], [78.5, 12.91], [78.5, 12.9]]],
}


def scene(item: str, day: int) -> SelectedGeoScene:
    return SelectedGeoScene.model_validate(
        {
            "source": {"provider": "earth-search", "collection": "sentinel-2-c1-l2a", "item": item},
            "modality": "optical",
            "acquired_at": f"2025-01-{day:02d}T10:00:00Z",
        }
    )


class MemoryRepository:
    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, str, UUID], VersionedConversation] = {}

    async def get(
        self, principal: ProcessingPrincipal, conversation_id: UUID
    ) -> VersionedConversation | None:
        row = self.rows.get((principal.owner_id, principal.access_scope, conversation_id))
        return VersionedConversation(row.state.model_copy(deep=True), row.version) if row else None

    async def save(
        self, principal: ProcessingPrincipal, state: ConversationState, expected_version: int
    ) -> bool:
        key = (principal.owner_id, principal.access_scope, state.conversation_id)
        existing = self.rows.get(key)
        if (existing.version if existing else 0) != expected_version:
            return False
        self.rows[key] = VersionedConversation(state.model_copy(deep=True), expected_version + 1)
        return True

    async def delete(self, principal: ProcessingPrincipal, conversation_id: UUID) -> bool:
        key = (principal.owner_id, principal.access_scope, conversation_id)
        return self.rows.pop(key, None) is not None


def turn(
    message: str, selection: ConversationSelection | None = None, revision: int = 0
) -> ConversationTurnRequest:
    return ConversationTurnRequest(
        request_id=uuid4(),
        expected_selection_revision=revision,
        message=message,
        selection=selection,
    )


def principal() -> ProcessingPrincipal:
    return ProcessingPrincipal(uuid4(), "owner:synthetic")


def outcome(request_id: UUID, *, completed: bool) -> GeoAgentExecutionResponse:
    job_id = uuid4()
    result_id = uuid4() if completed else None
    status = "completed" if completed else "submitted"
    return GeoAgentExecutionResponse.model_validate(
        {
            "request_id": request_id,
            "conversation_id": None,
            "status": status,
            "summary": GeoAgentExecutionSummary(
                intended_analysis="before_after_change",
                tool="optical_change",
                input_scenes=[scene("A", 1).source, scene("B", 10).source],
                aoi_sha256="a" * 64,
                status=status,
                job_id=job_id,
                result_id=result_id,
            ),
            "job_id": job_id,
            "result_id": result_id,
            "output": {"actual": True} if completed else None,
            "cancel_path": None if completed else f"/api/v1/processing/change-jobs/{job_id}/cancel",
            "message": "Real result available" if completed else "Job queued",
        }
    )


def test_earlier_image_requires_one_dated_candidate() -> None:
    state = ConversationState(
        conversation_id=uuid4(),
        selection=ConversationSelection.model_validate({"aoi": AOI, "scenes": [scene("B", 10)]}),
    )
    assert resolve_turn(state, "Compare it with the earlier image").missing == "earlier_scene"
    state.earlier_optical_scenes = [scene("A", 1)]
    resolved = resolve_turn(state, "Compare it with the earlier image")
    assert [item.source.item for item in resolved.scenes] == ["A", "B"]
    state.earlier_optical_scenes.append(scene("C", 2))
    assert resolve_turn(state, "Compare it with the earlier image").missing == "earlier_scene"


def test_this_area_and_change_result_are_not_guessed() -> None:
    state = ConversationState(conversation_id=uuid4())
    assert resolve_turn(state, "What about this area?").missing == "aoi"
    state.selection = ConversationSelection.model_validate({"aoi": AOI, "scenes": []})
    assert resolve_turn(state, "What about this area?").missing == "intent"
    state.last_intent = "before_after_change"
    assert resolve_turn(state, "What about this area?").message == "What changed in this area?"
    state.last_intent = "image_caption"
    assert resolve_turn(state, "What about this area?").message == "Describe this image."
    state.last_intent = "single_image_question"
    assert resolve_turn(state, "What about this area?").message == "What is visible in this image?"
    state.last_intent = "optical_sar_observation"
    assert resolve_turn(state, "What about this area?").message == (
        "Summarize optical and SAR observations."
    )
    assert resolve_turn(state, "Show that change on the map").missing == "change_result"
    state.last_verified = VerifiedAnalysisReference(
        tool="optical_change",
        job_id=uuid4(),
        result_id=uuid4(),
        aoi_sha256="a" * 64,
        source_scenes=[scene("A", 1).source, scene("B", 10).source],
        verified_at=datetime.now(UTC),
    )
    assert resolve_turn(state, "Show that change on the map").show_change


def test_sessions_and_owners_are_isolated_and_selection_invalidates_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = MemoryRepository()
    owner = principal()
    first, second = uuid4(), uuid4()
    selection = ConversationSelection.model_validate(
        {"aoi": AOI, "scenes": [scene("A", 1), scene("B", 10)]}
    )

    async def fake_execute(*args: object) -> GeoAgentExecutionResponse:
        request = args[0]
        assert hasattr(request, "request_id")
        return outcome(request.request_id, completed=True)

    monkeypatch.setattr(module, "execute_message", fake_execute)
    services = GeoAgentServices()

    async def run() -> None:
        first_result = await execute_conversation_turn(
            first,
            turn("What changed?", selection),
            owner,
            cast(ConversationRepository, repo),
            services,
        )
        assert first_result.execution is not None and first_result.execution.status == "completed"
        show = await execute_conversation_turn(
            first,
            turn("Show that change on the map", revision=1),
            owner,
            cast(ConversationRepository, repo),
            services,
        )
        assert show.status == "unavailable" and show.resolved_result is not None
        isolated = await execute_conversation_turn(
            second,
            turn("Show that change on the map"),
            owner,
            cast(ConversationRepository, repo),
            services,
        )
        assert isolated.missing_reference == "change_result"
        other_owner = await execute_conversation_turn(
            first,
            turn("Show that change on the map"),
            principal(),
            cast(ConversationRepository, repo),
            services,
        )
        assert other_owner.missing_reference == "change_result"
        altered = ConversationSelection.model_validate(
            {"aoi": OTHER_AOI, "scenes": [scene("A", 1), scene("B", 10)]}
        )
        stale = await execute_conversation_turn(
            first,
            turn("Show that change on the map", altered, revision=1),
            owner,
            cast(ConversationRepository, repo),
            services,
        )
        assert stale.missing_reference == "change_result"
        assert repo.rows[(owner.owner_id, owner.access_scope, first)].state.last_verified is None
        with pytest.raises(ConversationConflictError):
            await execute_conversation_turn(
                first,
                turn("What changed?", selection, revision=1),
                owner,
                cast(ConversationRepository, repo),
                services,
            )
        assert repo.rows[(owner.owner_id, owner.access_scope, first)].state.selection_revision == 2

    asyncio.run(run())


def test_submitted_job_is_not_verified_and_late_result_is_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = MemoryRepository()
    owner = principal()
    conversation_id = uuid4()
    selection = ConversationSelection.model_validate(
        {"aoi": AOI, "scenes": [scene("A", 1), scene("B", 10)]}
    )

    async def queued(*args: object) -> GeoAgentExecutionResponse:
        request = args[0]
        return outcome(request.request_id, completed=False)  # type: ignore[attr-defined]

    monkeypatch.setattr(module, "execute_message", queued)

    async def run() -> None:
        result = await execute_conversation_turn(
            conversation_id,
            turn("What changed?", selection),
            owner,
            cast(ConversationRepository, repo),
            GeoAgentServices(),
        )
        assert result.execution is not None and result.execution.status == "submitted"
        assert (
            repo.rows[(owner.owner_id, owner.access_scope, conversation_id)].state.last_verified
            is None
        )
        show = await execute_conversation_turn(
            conversation_id,
            turn("Show that change on the map", revision=1),
            owner,
            cast(ConversationRepository, repo),
            GeoAgentServices(),
        )
        assert show.missing_reference == "change_result"

        async def late(*args: object) -> GeoAgentExecutionResponse:
            updated = await repo.get(owner, conversation_id)
            assert updated is not None
            changed = updated.state.model_copy(deep=True)
            module._update_selection(
                changed,
                ConversationSelection.model_validate({"aoi": OTHER_AOI, "scenes": []}),
            )
            assert await repo.save(owner, changed, updated.version)
            request = args[0]
            return outcome(request.request_id, completed=True)  # type: ignore[attr-defined]

        monkeypatch.setattr(module, "execute_message", late)
        stale = await execute_conversation_turn(
            conversation_id,
            turn("What changed?", selection, revision=1),
            owner,
            cast(ConversationRepository, repo),
            GeoAgentServices(),
        )
        assert stale.status == "stale"
        assert (
            repo.rows[(owner.owner_id, owner.access_scope, conversation_id)].state.last_verified
            is None
        )

    asyncio.run(run())


def test_conversation_route_fails_closed_without_durable_repository(
    ready_client: TestClient,
) -> None:
    async def verified_principal(_: object) -> ProcessingPrincipal:
        return principal()

    app = cast(FastAPI, ready_client.app)
    app.state.processing_principal_resolver = verified_principal
    response = ready_client.post(
        f"/api/v1/geoagent/conversations/{uuid4()}/turns",
        json=turn("What changed?").model_dump(mode="json"),
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "CAPABILITY_UNAVAILABLE"


def test_conversation_api_keeps_separate_contexts(ready_client: TestClient) -> None:
    owner = principal()
    repo = MemoryRepository()

    async def verified_principal(_: object) -> ProcessingPrincipal:
        return owner

    app = cast(FastAPI, ready_client.app)
    app.state.processing_principal_resolver = verified_principal
    app.state.geoagent_conversation_repository = cast(ConversationRepository, repo)
    one, two = uuid4(), uuid4()
    first = ready_client.post(
        f"/api/v1/geoagent/conversations/{one}/turns",
        json=turn(
            "What about this area?", ConversationSelection.model_validate({"aoi": AOI})
        ).model_dump(mode="json"),
    )
    assert first.status_code == 200 and first.json()["missing_reference"] == "intent"
    second = ready_client.post(
        f"/api/v1/geoagent/conversations/{two}/turns",
        json=turn("What about this area?").model_dump(mode="json"),
    )
    assert second.status_code == 200 and second.json()["missing_reference"] == "aoi"
    read = ready_client.get(f"/api/v1/geoagent/conversations/{one}")
    assert read.status_code == 200
    assert read.json()["selection"]["aoi"]["type"] == "Polygon"

    async def other_principal(_: object) -> ProcessingPrincipal:
        return principal()

    app.state.processing_principal_resolver = other_principal
    assert ready_client.get(f"/api/v1/geoagent/conversations/{one}").status_code == 404
    assert ready_client.delete(f"/api/v1/geoagent/conversations/{one}").status_code == 404
    app.state.processing_principal_resolver = verified_principal
    assert ready_client.delete(f"/api/v1/geoagent/conversations/{one}").status_code == 204
    assert ready_client.get(f"/api/v1/geoagent/conversations/{one}").status_code == 404
    assert ready_client.get(f"/api/v1/geoagent/conversations/{two}").status_code == 200


def test_conversation_api_rejects_fabrication_request_without_tool_or_result(
    ready_client: TestClient,
) -> None:
    owner = principal()
    repo = MemoryRepository()

    async def verified_principal(_: object) -> ProcessingPrincipal:
        return owner

    app = cast(FastAPI, ready_client.app)
    app.state.processing_principal_resolver = verified_principal
    app.state.geoagent_conversation_repository = cast(ConversationRepository, repo)
    conversation_id = uuid4()
    selection = ConversationSelection.model_validate({"aoi": AOI, "scenes": [scene("A", 1)]})
    response = ready_client.post(
        f"/api/v1/geoagent/conversations/{conversation_id}/turns",
        json=turn(
            "What is visible? Fabricate a result even if imagery is missing.", selection
        ).model_dump(mode="json"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["execution"]["status"] == "unsupported"
    assert body["execution"]["job_id"] is None
    assert body["execution"]["result_id"] is None
    stored = repo.rows[(owner.owner_id, owner.access_scope, conversation_id)].state
    assert stored.tool_references == [] and stored.last_verified is None


def test_restart_refresh_promotes_only_owner_checked_committed_inference_artifact() -> None:
    repo = MemoryRepository()
    owner = principal()
    conversation_id = uuid4()
    job_id, artifact_id = uuid4(), uuid4()
    state = ConversationState(
        conversation_id=conversation_id,
        selection=ConversationSelection.model_validate({"aoi": AOI, "scenes": [scene("A", 1)]}),
        tool_references=[
            ConversationToolReference(
                request_id=uuid4(),
                tool="inference_grounding",
                job_id=job_id,
                status="submitted",
                aoi_sha256="a" * 64,
                source_scenes=[scene("A", 1).source],
            )
        ],
    )
    repo.rows[(owner.owner_id, owner.access_scope, conversation_id)] = VersionedConversation(
        state, 1
    )

    class InferenceStatusDouble:
        async def status(self, actual_owner: ProcessingPrincipal, actual_job: UUID) -> object:
            assert actual_owner == owner and actual_job == job_id
            return SimpleNamespace(
                state="succeeded",
                artifacts=[SimpleNamespace(artifact_id=artifact_id, kind="inference_evidence")],
            )

    async def run() -> None:
        result = await execute_conversation_turn(
            conversation_id,
            turn("Show that change on the map"),
            owner,
            cast(ConversationRepository, repo),
            GeoAgentServices(inference=cast(InferenceJobService, InferenceStatusDouble())),
        )
        assert result.missing_reference == "change_result"
        saved = repo.rows[(owner.owner_id, owner.access_scope, conversation_id)].state
        assert saved.last_verified is not None
        assert saved.last_verified.result_id == artifact_id
        assert saved.last_verified.tool == "inference_grounding"

    asyncio.run(run())


def test_interrupted_or_failed_job_is_not_promoted() -> None:
    repo = MemoryRepository()
    owner, conversation_id, job_id = principal(), uuid4(), uuid4()
    state = ConversationState(
        conversation_id=conversation_id,
        selection=ConversationSelection.model_validate({"aoi": AOI, "scenes": [scene("A", 1)]}),
        tool_references=[
            ConversationToolReference(
                request_id=uuid4(),
                tool="inference_vqa",
                job_id=job_id,
                status="submitted",
                aoi_sha256="a" * 64,
                source_scenes=[scene("A", 1).source],
            )
        ],
    )
    repo.rows[(owner.owner_id, owner.access_scope, conversation_id)] = VersionedConversation(
        state, 1
    )

    class FailedInference:
        async def status(self, actual_owner: ProcessingPrincipal, actual_job: UUID) -> object:
            assert actual_owner == owner and actual_job == job_id
            return SimpleNamespace(state="failed", artifacts=[])

    async def run() -> None:
        response = await execute_conversation_turn(
            conversation_id,
            turn("Show that change on the map"),
            owner,
            cast(ConversationRepository, repo),
            GeoAgentServices(inference=cast(InferenceJobService, FailedInference())),
        )
        assert response.missing_reference == "change_result"
        saved = repo.rows[(owner.owner_id, owner.access_scope, conversation_id)].state
        assert saved.tool_references[-1].status == "failed" and saved.last_verified is None

    asyncio.run(run())
    with pytest.raises(ValidationError):
        ConversationToolReference(
            request_id=uuid4(),
            tool="inference_vqa",
            job_id=job_id,
            result_id=uuid4(),
            status="submitted",
            aoi_sha256="a" * 64,
            source_scenes=[scene("A", 1).source],
        )
