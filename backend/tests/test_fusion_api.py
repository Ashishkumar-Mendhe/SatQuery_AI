"""API tests for evidence fusion endpoints."""

from __future__ import annotations

from conftest import ReadyDatabase, make_settings
from starlette.testclient import TestClient

from satquery.main import create_app


def test_fusion_capabilities_endpoint() -> None:
    settings = make_settings()
    app = create_app(settings=settings, database=ReadyDatabase())
    with TestClient(app) as client:
        res = client.get("/api/v1/fusion/capabilities")
        assert res.status_code == 200
        data = res.json()
        assert "rules" in data
        assert len(data["rules"]) > 0
        assert data["rules"][0]["rule_id"] == "co_observed_response_change"
        assert "supported_polarizations" in data


def test_fusion_result_not_found() -> None:
    settings = make_settings()
    app = create_app(settings=settings, database=ReadyDatabase())
    with TestClient(app) as client:
        res = client.get("/api/v1/fusion/results/nonexistent-id")
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "HTTP_ERROR"
