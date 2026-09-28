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

from satquery.api.schemas.asset_resolution import AssetResolutionRequest
from satquery.providers.catalog import CatalogueProviderError, EarthSearchCatalogueProvider

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "stac" / "earth_search_sentinel_2_c1_l2a.json"
COG_MEDIA_TYPE = "image/tiff; application=geotiff; profile=cloud-optimized"


def _fixture() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))


def _item_with_rgb() -> dict[str, Any]:
    item = deepcopy(_fixture()["item"])
    item["properties"].update(
        {
            "proj:code": "EPSG:32643",
            "proj:shape": [10980, 10980],
            "proj:transform": [10.0, 0.0, 699960.0, 0.0, -10.0, 1500000.0],
        }
    )
    item["assets"] = {
        "reflectance-b04": _band("red", "B04", 10, "B04.tif", -0.1),
        "reflectance-b03": _band("green", "B03", 20, "B03.tif", -0.2),
        "reflectance-b02": _band("blue", "B02", 60, "B02.tif", -0.3),
        "quick-look": deepcopy(_fixture()["item"]["assets"]["thumbnail"]),
    }
    return cast(dict[str, Any], item)


def _band(
    common_name: str, band_name: str, gsd: int, filename: str, offset: float
) -> dict[str, Any]:
    return {
        "href": (
            "https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/"
            f"sentinel-2-c1-l2a/synthetic/{filename}"
        ),
        "type": COG_MEDIA_TYPE,
        "eo:bands": [{"name": band_name, "common_name": common_name}],
        "raster:bands": [{"scale": 0.0001, "offset": offset, "nodata": 0}],
        "gsd": gsd,
        "roles": ["data", "reflectance"],
        "file:checksum": f"sha256:{band_name.lower()}",
    }


def _request() -> AssetResolutionRequest:
    return AssetResolutionRequest.model_validate(
        {
            "scene": {
                "provider": "earth-search",
                "collection": "sentinel-2-c1-l2a",
                "item": "S2B_T43PGQ_20251223T051848_L2A",
            }
        }
    )


def _json_response(request: httpx2.Request, payload: Any, status: int = 200) -> httpx2.Response:
    return httpx2.Response(
        status,
        request=request,
        headers={"content-type": "application/json"},
        json=payload,
    )


def _handler(
    item: dict[str, Any],
    requests: list[httpx2.Request],
    *,
    head_status: dict[str, int] | None = None,
) -> Callable[[httpx2.Request], httpx2.Response]:
    fixture = _fixture()

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if request.method == "HEAD":
            status = (head_status or {}).get(request.url.path.rsplit("/", 1)[-1], 200)
            return httpx2.Response(
                status,
                request=request,
                headers={"content-type": COG_MEDIA_TYPE, "content-length": "4096"},
            )
        if request.url.path == "/v1/collections":
            return _json_response(request, {"collections": [fixture["collection"]]})
        if "/items/" in request.url.path:
            return _json_response(request, item)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    return handler


def _provider(handler: Callable[[httpx2.Request], httpx2.Response]) -> EarthSearchCatalogueProvider:
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return EarthSearchCatalogueProvider(client=client, max_retries=0)


@contextmanager
def _api_client(
    handler: Callable[[httpx2.Request], httpx2.Response],
) -> Iterator[TestClient]:
    from satquery.main import create_app

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


def test_maps_rgb_from_band_metadata_and_keeps_thumbnail_separate() -> None:
    requests: list[httpx2.Request] = []
    provider = _provider(_handler(_item_with_rgb(), requests))

    response = asyncio.run(provider.resolve_imagery(_request()))

    assert response.status.state == "supported"
    assert response.resolved_asset is not None
    assert response.resolved_asset.render_presets[0].bands == [
        "reflectance-b04",
        "reflectance-b03",
        "reflectance-b02",
    ]
    assert [component.render_role for component in response.components] == [
        "red",
        "green",
        "blue",
    ]
    assert [component.resolution_metres for component in response.components] == [10.0, 20.0, 60.0]
    assert [component.offset for component in response.components] == [-0.1, -0.2, -0.3]
    assert all(component.crs == "EPSG:32643" for component in response.components)
    assert response.thumbnail is not None and response.thumbnail.purpose == "thumbnail"
    assert response.license is not None and response.license.name == "proprietary"
    assert ".tif" not in response.model_dump_json()
    assert [request.method for request in requests].count("HEAD") == 3


def test_missing_rgb_band_is_explicitly_unavailable_without_raster_request() -> None:
    item = _item_with_rgb()
    del item["assets"]["reflectance-b03"]
    requests: list[httpx2.Request] = []
    provider = _provider(_handler(item, requests))

    response = asyncio.run(provider.resolve_imagery(_request()))

    assert response.status.state == "unavailable_asset"
    assert response.status.reason is not None and "green" in response.status.reason
    assert response.resolved_asset is None
    assert response.components == []
    assert all(request.method != "HEAD" for request in requests)


def test_unsupported_band_format_is_explicit_without_raster_request() -> None:
    item = _item_with_rgb()
    item["assets"]["reflectance-b02"]["type"] = "image/jp2"
    requests: list[httpx2.Request] = []
    provider = _provider(_handler(item, requests))

    response = asyncio.run(provider.resolve_imagery(_request()))

    assert response.status.state == "unsupported_format"
    assert response.resolved_asset is None
    assert response.components == []
    assert all(request.method != "HEAD" for request in requests)


def test_restricted_band_access_requires_credentials_and_returns_no_asset() -> None:
    requests: list[httpx2.Request] = []
    provider = _provider(_handler(_item_with_rgb(), requests, head_status={"B03.tif": 403}))

    response = asyncio.run(provider.resolve_imagery(_request()))

    assert response.status.state == "access_credentials_required"
    assert response.status.reason is not None and "green" in response.status.reason
    assert response.resolved_asset is None
    assert response.components == []


def test_expired_reference_is_unavailable_without_raster_request() -> None:
    item = _item_with_rgb()
    item["assets"]["reflectance-b04"]["expires"] = "2020-01-01T00:00:00Z"
    requests: list[httpx2.Request] = []
    provider = _provider(_handler(item, requests))

    response = asyncio.run(provider.resolve_imagery(_request()))

    assert response.status.state == "unavailable_asset"
    assert response.asset_accessibility.state == "expired"
    assert response.asset_accessibility.expires_at is not None
    assert response.resolved_asset is None
    assert all(request.method != "HEAD" for request in requests)


def test_rejects_unapproved_provider_asset_location() -> None:
    item = _item_with_rgb()
    item["assets"]["reflectance-b04"]["href"] = "https://attacker.test/red.tif"
    requests: list[httpx2.Request] = []
    provider = _provider(_handler(item, requests))

    with pytest.raises(CatalogueProviderError, match="unapproved raster") as captured:
        asyncio.run(provider.resolve_imagery(_request()))

    assert captured.value.code == "INVALID_PROVIDER_RESPONSE"
    assert all(request.url.host != "attacker.test" for request in requests)


def test_asset_resolution_route_accepts_only_stable_identity() -> None:
    requests: list[httpx2.Request] = []
    with _api_client(_handler(_item_with_rgb(), requests)) as client:
        response = client.post("/api/v1/catalog/asset-resolutions", json=_request().model_dump())
        rejected = client.post(
            "/api/v1/catalog/asset-resolutions",
            json={
                **_request().model_dump(),
                "href": "https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/file.tif",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "supported"
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "VALIDATION_FAILED"
