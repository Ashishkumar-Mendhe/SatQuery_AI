from fastapi.testclient import TestClient


def test_valid_request_id_is_preserved(ready_client: TestClient) -> None:
    response = ready_client.get(
        "/api/v1/health/live", headers={"X-Request-ID": "client-request_123"}
    )

    assert response.headers["x-request-id"] == "client-request_123"


def test_invalid_request_id_is_replaced(ready_client: TestClient) -> None:
    response = ready_client.get(
        "/api/v1/health/live", headers={"X-Request-ID": "invalid request id"}
    )

    request_id = response.headers["x-request-id"]
    assert request_id.startswith("req_")
    assert " " not in request_id


def test_allowed_origin_receives_cors_header(ready_client: TestClient) -> None:
    response = ready_client.options(
        "/api/v1/health/live",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unapproved_origin_is_not_allowed(ready_client: TestClient) -> None:
    response = ready_client.options(
        "/api/v1/health/live",
        headers={
            "Origin": "https://unapproved.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_catalogue_search_allows_configured_origin_post(ready_client: TestClient) -> None:
    response = ready_client.options(
        "/api/v1/catalog/searches",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,X-Request-ID",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "POST" in response.headers["access-control-allow-methods"]
