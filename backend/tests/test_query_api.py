from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import ReadyDatabase, make_settings
from fastapi.testclient import TestClient

from satquery.api.schemas.analysis import AOIGeometry, GeometryType
from satquery.api.schemas.query import WorkspaceContextSnapshot
from satquery.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = make_settings()
    settings.imagery_storage_dir = tmp_path / "imagery_cache"
    app = create_app(settings=settings, database=ReadyDatabase())
    with TestClient(app) as test_client:
        yield test_client


def test_get_capabilities_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/query/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert "supported_intents" in data
    assert "supported_generation_modes" in data
    assert "example_questions" in data
    assert len(data["supported_intents"]) >= 7


def test_ask_query_endpoint(client: TestClient) -> None:
    aoi = AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=[[[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]]],
    )
    snapshot = WorkspaceContextSnapshot(
        snapshot_id="snap-test-1",
        fingerprint="fp12345678",
        aoi_geometry=aoi,
        scene_ids=["S2A_123", "S2B_456"],
    )
    payload = {
        "question": "What changed between these dates?",
        "context_snapshot": snapshot.model_dump(mode="json"),
    }

    response = client.post("/api/v1/query/ask", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer_id" in data
    assert "answer_status" in data
    assert "summary" in data
    assert "processing_trace" in data
