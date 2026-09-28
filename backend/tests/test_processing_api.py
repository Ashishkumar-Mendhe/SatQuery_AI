from __future__ import annotations

from fastapi.testclient import TestClient


def test_processing_routes_deny_when_identity_and_durable_service_are_unavailable(
    ready_client: TestClient,
) -> None:
    response = ready_client.post(
        "/api/v1/processing/preparations",
        headers={"Idempotency-Key": "synthetic-request"},
        json={"not": "a request"},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "CAPABILITY_UNAVAILABLE"

    change_response = ready_client.post(
        "/api/v1/processing/changes",
        headers={"Idempotency-Key": "synthetic-change"},
        json={"not": "a request"},
    )
    assert change_response.status_code == 503
    assert change_response.json()["error"]["code"] == "CAPABILITY_UNAVAILABLE"

    tile_response = ready_client.get(
        "/api/v1/processing/artifacts/10000000-0000-4000-8000-000000000002/tiles/usable/0/0/0.png"
    )
    assert tile_response.status_code == 503
    assert tile_response.json()["error"]["code"] == "CAPABILITY_UNAVAILABLE"
