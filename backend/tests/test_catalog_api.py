from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import httpx2
import pytest
from conftest import UnavailableDatabase, make_settings
from fastapi.testclient import TestClient

from satquery.main import create_app
from satquery.providers.catalog import EarthSearchCatalogueProvider

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "stac" / "earth_search_sentinel_2_c1_l2a.json"


def _fixture() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))


def _search_body(**updates: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "provider": "earth-search",
        "aoi": {
            "type": "Polygon",
            "coordinates": [[[77.5, 12.9], [77.7, 12.9], [77.7, 13.05], [77.5, 12.9]]],
        },
        "acquisition": {
            "start": "2025-01-01T05:30:00+05:30",
            "end": "2025-12-31T23:59:59Z",
        },
        "collections": ["sentinel-2-c1-l2a"],
        "cloud_cover": {"max_percent": 20.0},
        "limit": 2,
        "sort": "acquired_desc",
    }
    body.update(updates)
    return body


def _json_response(
    request: httpx2.Request,
    payload: Any,
    status_code: int = 200,
    *,
    headers: dict[str, str] | None = None,
) -> httpx2.Response:
    return httpx2.Response(
        status_code,
        request=request,
        headers={"content-type": "application/json", **(headers or {})},
        json=payload,
    )


def _metadata_handler(
    requests: list[httpx2.Request],
    *,
    search_features: list[dict[str, Any]] | None = None,
    with_next: bool = False,
    collection_without_optional_metadata: bool = False,
) -> Callable[[httpx2.Request], httpx2.Response]:
    fixture = _fixture()
    collection = deepcopy(fixture["collection"])
    if collection_without_optional_metadata:
        collection.pop("title", None)
        collection.pop("description", None)

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if request.url.path == "/v1/":
            return _json_response(request, fixture["root"])
        if request.url.path.endswith("/queryables"):
            return _json_response(request, fixture["queryables"])
        if request.url.path == "/v1/collections":
            return _json_response(request, {"collections": [collection]})
        if "/items/" in request.url.path:
            return _json_response(request, fixture["item"])
        if request.url.path == "/v1/search":
            links: list[dict[str, Any]] = []
            if with_next:
                links.append(
                    {
                        "rel": "next",
                        "href": "https://earth-search.aws.element84.com/v1/search",
                        "method": "POST",
                        "body": {"next": "provider-continuation-token"},
                    }
                )
            features = [fixture["item"]] if search_features is None else search_features
            return _json_response(
                request,
                {"type": "FeatureCollection", "features": features, "links": links},
            )
        raise AssertionError(f"unexpected metadata request: {request.url}")

    return handler


@contextmanager
def _client_for(
    handler: Callable[[httpx2.Request], httpx2.Response],
) -> Iterator[TestClient]:
    upstream_client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    provider = EarthSearchCatalogueProvider(client=upstream_client, max_retries=0)
    app = create_app(
        settings=make_settings(),
        database=UnavailableDatabase(),
        catalogue_provider=provider,
    )
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        asyncio.run(upstream_client.aclose())


def test_lists_collections_without_database_or_inventing_optional_metadata() -> None:
    requests: list[httpx2.Request] = []
    with _client_for(
        _metadata_handler(requests, collection_without_optional_metadata=True)
    ) as client:
        response = client.get(
            "/api/v1/catalog/collections",
            params={"provider": "earth-search"},
            headers={"X-Request-ID": "catalog-collections"},
        )
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "catalog-collections"
    assert response.json()["returned_count"] == 1
    assert response.json()["items"][0]["id"] == "sentinel-2-c1-l2a"
    assert response.json()["items"][0]["title"] is None
    assert response.json()["items"][0]["description"] is None
    assert not any("database" in request.url.path for request in requests)


def test_search_and_item_detail_return_typed_metadata_with_nulls() -> None:
    requests: list[httpx2.Request] = []
    with _client_for(_metadata_handler(requests)) as client:
        search = client.post(
            "/api/v1/catalog/searches",
            json=_search_body(),
            headers={"X-Request-ID": "catalog-search"},
        )
        item_id = search.json()["items"][0]["provider_asset_id"]
        detail = client.get(
            f"/api/v1/catalog/collections/sentinel-2-c1-l2a/items/{item_id}",
            params={"provider": "earth-search"},
        )
    assert search.status_code == 200
    assert search.headers["x-request-id"] == "catalog-search"
    assert search.json()["query"]["acquisition"]["start"] == "2025-01-01T00:00:00Z"
    assert search.json()["returned_count"] == 1
    assert search.json()["items"][0]["provider_asset_version"] is None
    assert detail.status_code == 200
    assert detail.json()["provider_asset_id"] == item_id
    assert detail.json()["product_type"] is None


@pytest.mark.parametrize(
    ("update", "field_fragment"),
    [
        ({"provider": "unconfigured"}, "provider"),
        ({"limit": 101}, "limit"),
        ({"cloud_cover": {"max_percent": 101.0}}, "cloud_cover"),
        ({"collections": ["sentinel-1-grd"]}, "collection"),
        (
            {
                "acquisition": {
                    "start": "2025-01-01T00:00:00",
                    "end": "2025-12-31T23:59:59Z",
                }
            },
            "acquisition",
        ),
        (
            {
                "acquisition": {
                    "start": "2025-12-31T00:00:00Z",
                    "end": "2025-01-01T00:00:00Z",
                }
            },
            "acquisition",
        ),
        (
            {
                "aoi": {
                    "type": "Polygon",
                    "coordinates": [
                        [[77.5, 12.9], [77.7, 13.1], [77.7, 12.9], [77.5, 13.1], [77.5, 12.9]]
                    ],
                }
            },
            "aoi",
        ),
    ],
)
def test_rejects_invalid_search_input_without_upstream_io(
    update: dict[str, Any], field_fragment: str
) -> None:
    requests: list[httpx2.Request] = []
    with _client_for(_metadata_handler(requests)) as client:
        response = client.post("/api/v1/catalog/searches", json=_search_body(**update))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert field_fragment in json.dumps(response.json()["error"])
    assert requests == []


def test_rejects_unsupported_cloud_semantics_as_unavailable_capability() -> None:
    requests: list[httpx2.Request] = []
    with _client_for(_metadata_handler(requests)) as client:
        response = client.post(
            "/api/v1/catalog/searches",
            json=_search_body(cloud_cover={"max_percent": 20.0, "include_unknown": True}),
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CAPABILITY_UNAVAILABLE"
    assert requests == []


def test_pagination_uses_provider_continuation_and_rejects_query_mismatch() -> None:
    requests: list[httpx2.Request] = []
    with _client_for(_metadata_handler(requests, with_next=True)) as client:
        first = client.post("/api/v1/catalog/searches", json=_search_body())
        cursor = first.json()["next_cursor"]
        second = client.post("/api/v1/catalog/searches", json=_search_body(cursor=cursor))
        mismatch = client.post(
            "/api/v1/catalog/searches",
            json=_search_body(cursor=cursor, cloud_cover={"max_percent": 10.0}),
        )
    search_requests = [request for request in requests if request.url.path == "/v1/search"]
    second_upstream_body = json.loads(search_requests[1].content)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second_upstream_body["next"] == "provider-continuation-token"
    assert second_upstream_body["collections"] == ["sentinel-2-c1-l2a"]
    assert second_upstream_body["query"] == {"eo:cloud_cover": {"lte": 20.0}}
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["code"] == "VALIDATION_FAILED"
    assert len(search_requests) == 2


def test_empty_search_is_a_successful_empty_page() -> None:
    requests: list[httpx2.Request] = []
    with _client_for(_metadata_handler(requests, search_features=[])) as client:
        response = client.post("/api/v1/catalog/searches", json=_search_body())

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["returned_count"] == 0


@pytest.mark.parametrize(
    ("status_code", "expected_status", "expected_code"),
    [
        (429, 429, "RATE_LIMITED"),
        (503, 503, "UPSTREAM_UNAVAILABLE"),
        (504, 504, "UPSTREAM_TIMEOUT"),
    ],
)
def test_provider_failures_never_become_empty_success(
    status_code: int, expected_status: int, expected_code: str
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        headers = {"retry-after": "17"} if status_code == 429 else None
        return _json_response(request, {"error": "synthetic failure"}, status_code, headers=headers)

    with _client_for(handler) as client:
        response = client.post("/api/v1/catalog/searches", json=_search_body())

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code
    assert "items" not in response.json()
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    if status_code == 429:
        assert response.headers["retry-after"] == "17"


def test_provider_transport_timeout_is_explicit() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("synthetic timeout", request=request)

    with _client_for(handler) as client:
        response = client.post("/api/v1/catalog/searches", json=_search_body())

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"
    assert response.json()["error"]["retryable"] is True
    assert "items" not in response.json()
