from unittest.mock import patch

from conftest import ReadyDatabase, make_settings
from fastapi import HTTPException, Path
from fastapi.testclient import TestClient

from satquery.main import create_app


def test_validation_errors_follow_public_contract() -> None:
    app = create_app(settings=make_settings(), database=ReadyDatabase())

    async def validated(value: int = Path(ge=1)) -> dict[str, int]:
        return {"value": value}

    app.add_api_route("/_test/validated/{value}", validated)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/_test/validated/0")

    body = response.json()["error"]
    assert response.status_code == 422
    assert body["code"] == "VALIDATION_FAILED"
    assert body["retryable"] is False
    assert body["request_id"] == response.headers["x-request-id"]
    assert "input" not in body


def test_http_errors_preserve_required_headers() -> None:
    app = create_app(settings=make_settings(), database=ReadyDatabase())

    async def throttled() -> None:
        raise HTTPException(status_code=429, detail="Slow down.", headers={"Retry-After": "7"})

    app.add_api_route("/_test/throttled", throttled)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/_test/throttled")

    assert response.status_code == 429
    assert response.headers["retry-after"] == "7"
    assert response.json()["error"]["code"] == "HTTP_ERROR"


def test_unexpected_errors_are_safe_and_logged() -> None:
    app = create_app(settings=make_settings(), database=ReadyDatabase())

    async def explode() -> None:
        raise RuntimeError("private diagnostic marker")

    app.add_api_route("/_test/explode", explode)
    with patch("satquery.core.errors.logger.exception") as log_exception:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/_test/explode")

    serialized = response.text
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private diagnostic marker" not in serialized
    assert "Traceback" not in serialized
    log_exception.assert_called_once()
