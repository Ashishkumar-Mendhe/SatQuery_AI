from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx2
import pytest

from satquery.api.schemas.catalog import CatalogueSearchRequest
from satquery.providers.catalog import CatalogueProviderError, EarthSearchCatalogueProvider

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "stac" / "earth_search_sentinel_2_c1_l2a.json"
NOW = datetime(2026, 9, 10, 7, 30, tzinfo=UTC)


def _fixture() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))


def _request(*, cursor: str | None = None, max_cloud: float = 20.0) -> CatalogueSearchRequest:
    return CatalogueSearchRequest.model_validate(
        {
            "provider": "earth-search",
            "aoi": {
                "type": "Polygon",
                "coordinates": [[[77.5, 12.9], [77.7, 12.9], [77.7, 13.05], [77.5, 12.9]]],
            },
            "acquisition": {
                "start": "2025-01-01T00:00:00Z",
                "end": "2025-12-31T23:59:59Z",
            },
            "collections": ["sentinel-2-c1-l2a"],
            "cloud_cover": {"max_percent": max_cloud},
            "limit": 2,
            "cursor": cursor,
            "sort": "acquired_desc",
        }
    )


def _json_response(request: httpx2.Request, payload: Any, status: int = 200) -> httpx2.Response:
    return httpx2.Response(
        status,
        request=request,
        headers={"content-type": "application/json"},
        json=payload,
    )


def _provider(
    handler: Callable[[httpx2.Request], httpx2.Response],
    *,
    max_retries: int = 0,
    sleeper: Callable[[float], Awaitable[None]] | None = None,
    cache_max_entries: int = 32,
) -> EarthSearchCatalogueProvider:
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    kwargs: dict[str, Any] = {
        "client": client,
        "max_retries": max_retries,
        "cache_max_entries": cache_max_entries,
        "jitter": lambda _minimum, _maximum: 0.0,
        "now": lambda: NOW,
    }
    if sleeper is not None:
        kwargs["sleeper"] = sleeper
    return EarthSearchCatalogueProvider(**kwargs)


def _standard_handler(
    requests: list[httpx2.Request], *, next_href: str | None = None
) -> Callable[[httpx2.Request], httpx2.Response]:
    fixture = _fixture()

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if request.url.path == "/v1/":
            return _json_response(request, fixture["root"])
        if request.url.path.endswith("/queryables"):
            return _json_response(request, fixture["queryables"])
        if request.url.path == "/v1/collections":
            return _json_response(request, {"collections": [fixture["collection"]]})
        if request.url.path.endswith(f"/items/{fixture['item']['id']}"):
            return _json_response(request, fixture["item"])
        if request.url.path == "/v1/search":
            links: list[dict[str, Any]] = []
            if next_href is not None:
                links.append(
                    {
                        "rel": "next",
                        "href": next_href,
                        "method": "POST",
                        "body": {
                            "next": "2025-12-23T05:25:18.674000Z,S2B_T43PGQ_20251223T051848_L2A",
                            "collections": ["untrusted-filter-change"],
                        },
                    }
                )
            return _json_response(
                request,
                {"type": "FeatureCollection", "features": [fixture["item"]], "links": links},
            )
        raise AssertionError(f"unexpected metadata request: {request.url}")

    return handler


def test_discovers_only_enabled_collection_and_required_capabilities() -> None:
    requests: list[httpx2.Request] = []
    provider = _provider(_standard_handler(requests))

    capabilities = asyncio.run(provider.capabilities())
    collections = asyncio.run(provider.collections())
    cached_capabilities = asyncio.run(provider.capabilities())
    cached_collections = asyncio.run(provider.collections())

    assert capabilities == cached_capabilities
    assert collections == cached_collections
    assert capabilities.stac_version == "1.0.0"
    assert capabilities.supports_intersects is True
    assert capabilities.supports_cloud_filter is True
    assert capabilities.supports_sort is True
    assert capabilities.supported_queryables == ("eo:cloud_cover",)
    assert [collection.id for collection in collections] == ["sentinel-2-c1-l2a"]
    assert collections[0].spatial_resolutions_metres == (10.0, 20.0, 60.0)
    assert [request.url.path for request in requests].count("/v1/") == 1
    assert [request.url.path for request in requests].count("/v1/collections") == 1


def test_metadata_cache_evicts_oldest_entry_at_configured_bound() -> None:
    requests: list[httpx2.Request] = []
    provider = _provider(_standard_handler(requests), cache_max_entries=1)

    asyncio.run(provider.capabilities())
    asyncio.run(provider.collections())
    asyncio.run(provider.capabilities())

    paths = [request.url.path for request in requests]
    assert paths.count("/v1/") == 2
    assert paths.count("/v1/collections/sentinel-2-c1-l2a/queryables") == 2


def test_search_uses_intersection_cloud_sort_and_normalizes_actual_metadata() -> None:
    requests: list[httpx2.Request] = []
    provider = _provider(_standard_handler(requests))

    response = asyncio.run(provider.search(_request()))

    search_request = next(request for request in requests if request.url.path == "/v1/search")
    body = json.loads(search_request.content)
    assert body["intersects"]["type"] == "Polygon"
    assert body["datetime"] == "2025-01-01T00:00:00Z/2025-12-31T23:59:59Z"
    assert body["query"] == {"eo:cloud_cover": {"lte": 20.0}}
    assert body["sortby"] == [
        {"field": "properties.datetime", "direction": "desc"},
        {"field": "id", "direction": "asc"},
    ]
    assert response.returned_count == 1
    scene = response.items[0]
    assert scene.provider_asset_id == "S2B_T43PGQ_20251223T051848_L2A"
    assert scene.acquisition.start.isoformat() == "2025-12-23T05:25:18.674000+00:00"
    assert scene.provenance.retrieved_at == NOW
    assert scene.cloud_cover is not None and scene.cloud_cover.percent == 4.321234
    assert scene.provider_asset_version is None
    assert scene.platform == "sentinel-2b"
    assert scene.instruments == ["msi"]
    assert scene.bands == ["red"]
    assert [resolution.value for resolution in scene.spatial_resolution] == [10.0]
    assert scene.preview is not None and scene.preview.purpose == "thumbnail"
    assert scene.asset_access.state == "provider_accessible"
    assert scene.license is not None and scene.license.name == "proprietary"
    assert {field.field for field in scene.unavailable_fields} >= {
        "provider_asset_version",
        "product_type",
        "processing_level",
        "polarizations",
    }
    assert all(request.url.host == "earth-search.aws.element84.com" for request in requests)
    assert not any(request.url.path.endswith((".tif", ".jpg")) for request in requests)


def test_pagination_preserves_original_filters_and_rejects_filter_changes() -> None:
    requests: list[httpx2.Request] = []
    provider = _provider(
        _standard_handler(requests, next_href="https://earth-search.aws.element84.com/v1/search")
    )

    first = asyncio.run(provider.search(_request()))
    assert first.next_cursor is not None
    second = asyncio.run(provider.search(_request(cursor=first.next_cursor)))
    search_requests = [request for request in requests if request.url.path == "/v1/search"]
    second_body = json.loads(search_requests[1].content)
    assert second_body["collections"] == ["sentinel-2-c1-l2a"]
    assert second_body["query"] == {"eo:cloud_cover": {"lte": 20.0}}
    assert second_body["next"].startswith("2025-12-23T05:25:18.674000Z")
    assert second.returned_count == 1

    with pytest.raises(CatalogueProviderError, match="does not match") as captured:
        asyncio.run(provider.search(_request(cursor=first.next_cursor, max_cloud=10.0)))
    assert captured.value.code == "INVALID_CURSOR"


def test_rejects_unapproved_provider_pagination_url() -> None:
    requests: list[httpx2.Request] = []
    provider = _provider(_standard_handler(requests, next_href="https://attacker.test/search"))

    with pytest.raises(CatalogueProviderError, match="unapproved pagination") as captured:
        asyncio.run(provider.search(_request()))

    assert captured.value.code == "INVALID_PROVIDER_RESPONSE"


def test_item_detail_uses_bounded_path_and_metadata_cache() -> None:
    requests: list[httpx2.Request] = []
    provider = _provider(_standard_handler(requests))
    item_id = "S2B_T43PGQ_20251223T051848_L2A"

    first = asyncio.run(provider.item("sentinel-2-c1-l2a", item_id))
    second = asyncio.run(provider.item("sentinel-2-c1-l2a", item_id))

    assert first == second
    item_requests = [request for request in requests if "/items/" in request.url.path]
    assert len(item_requests) == 1
    assert item_requests[0].url.path.endswith(f"/items/{item_id}")


def test_retries_transient_failures_with_a_bound() -> None:
    fixture = _fixture()
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        if request.url.path == "/v1/":
            attempts += 1
            if attempts < 3:
                return _json_response(request, {"error": "temporary"}, status=503)
            return _json_response(request, fixture["root"])
        if request.url.path.endswith("/queryables"):
            return _json_response(request, fixture["queryables"])
        raise AssertionError(f"unexpected request: {request.url}")

    async def sleeper(delay: float) -> None:
        delays.append(delay)

    provider = _provider(handler, max_retries=2, sleeper=sleeper)
    capabilities = asyncio.run(provider.capabilities())

    assert capabilities.supports_sort is True
    assert attempts == 3
    assert delays == [0.25, 0.5]


def test_reports_exhausted_transient_failure_without_fallback_results() -> None:
    attempts = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        return _json_response(request, {"error": "temporary"}, status=503)

    async def sleeper(_delay: float) -> None:
        return None

    provider = _provider(handler, max_retries=1, sleeper=sleeper)

    with pytest.raises(CatalogueProviderError) as captured:
        asyncio.run(provider.capabilities())

    assert captured.value.code == "PROVIDER_UNAVAILABLE"
    assert captured.value.retryable is True
    assert captured.value.upstream_status == 503
    assert attempts == 2


def test_rejects_unknown_cloud_inclusion_and_unapproved_collections_without_io() -> None:
    requests: list[httpx2.Request] = []
    provider = _provider(_standard_handler(requests))
    cloud_cover = _request().cloud_cover
    assert cloud_cover is not None
    include_unknown = _request().model_copy(
        update={"cloud_cover": cloud_cover.model_copy(update={"include_unknown": True})}
    )

    with pytest.raises(CatalogueProviderError) as cloud_error:
        asyncio.run(provider.search(include_unknown))
    assert cloud_error.value.code == "UNSUPPORTED_FILTER"

    unsupported = _request().model_copy(update={"collections": ["sentinel-1-grd"]})
    with pytest.raises(CatalogueProviderError) as collection_error:
        asyncio.run(provider.search(unsupported))
    assert collection_error.value.code == "UNSUPPORTED_COLLECTION"
    assert requests == []


def test_rejects_non_json_metadata() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            request=request,
            headers={"content-type": "text/html"},
            text="not metadata",
        )

    provider = _provider(handler)
    with pytest.raises(CatalogueProviderError, match="non-JSON") as captured:
        asyncio.run(provider.capabilities())
    assert captured.value.code == "INVALID_PROVIDER_RESPONSE"


def test_accepts_standard_json_schema_media_type() -> None:
    fixture = _fixture()

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/v1/":
            return _json_response(request, fixture["root"])
        if request.url.path.endswith("/queryables"):
            return httpx2.Response(
                200,
                request=request,
                headers={"content-type": "application/schema+json"},
                json=fixture["queryables"],
            )
        raise AssertionError(f"unexpected request: {request.url}")

    provider = _provider(handler)
    assert asyncio.run(provider.capabilities()).supports_cloud_filter is True
