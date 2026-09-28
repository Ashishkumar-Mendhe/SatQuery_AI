"""Tests for the /api/v1/providers/status endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from satquery.api.schemas.providers import ProvidersStatusResponse


def test_providers_status_endpoint(ready_client: TestClient) -> None:
    response = ready_client.get("/api/v1/providers/status")
    assert response.status_code == 200

    data = response.json()
    assert "environment" in data
    assert "contract_version" in data
    assert "satellite_provider" in data
    assert "ai_provider" in data
    assert "processing_mode" in data
    assert "overall_readiness" in data
    assert "timestamp" in data

    # Verify Pydantic validation of response
    parsed = ProvidersStatusResponse.model_validate(data)
    assert parsed.satellite_provider.provider_id in {"earth-search", "mock"}
    assert parsed.ai_provider.provider_id in {"gemini", "mock"}

    # Ensure no secrets leak
    resp_text = response.text
    assert "password" not in resp_text.lower()
    assert "secret" not in resp_text.lower()
    assert "key" not in resp_text.lower() or "api_key" not in resp_text.lower()
