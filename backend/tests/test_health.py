from conftest import UnavailableDatabase, make_settings
from fastapi.testclient import TestClient

from satquery.main import create_app


def test_liveness_does_not_require_database() -> None:
    app = create_app(settings=make_settings(), database=UnavailableDatabase())
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "live"
    assert response.headers["cache-control"] == "no-store"


def test_readiness_reports_real_dependency_shape(ready_client: TestClient) -> None:
    response = ready_client.get("/api/v1/health/ready", headers={"X-Request-ID": "test-ready"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-ready"
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "status": "ready",
        "service": "satquery-api",
        "version": "0.1.0",
        "request_id": "test-ready",
        "checks": {
            "database": {
                "status": "up",
                "postgis": "available",
                "migration": "current",
                "server_version": "18.synthetic",
                "postgis_version": "3.6.synthetic",
                "migration_revision": "20260907_0001",
            }
        },
    }


def test_readiness_returns_503_when_database_is_unavailable() -> None:
    app = create_app(settings=make_settings(), database=UnavailableDatabase())
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["retry-after"] == "5"
    assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert response.json()["error"]["details"] == {"dependency": "database"}
