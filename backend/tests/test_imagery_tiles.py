from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import httpx2
import numpy as np
import pytest
from conftest import UnavailableDatabase, make_settings
from fastapi.testclient import TestClient
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds
from rio_tiler.utils import render

from satquery.api.schemas.asset_resolution import AssetResolutionRequest
from satquery.api.schemas.viewer import TileMetadata, TileMetadataRequest
from satquery.main import create_app
from satquery.providers.catalog import EarthSearchCatalogueProvider
from satquery.tiles import ImageryTileService, TileServiceError
from satquery.tiles.service import _render_natural_color, _validate_source_location

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "stac" / "earth_search_sentinel_2_c1_l2a.json"
COG_MEDIA_TYPE = "image/tiff; application=geotiff; profile=cloud-optimized"
SCENE = {
    "provider": "earth-search",
    "collection": "sentinel-2-c1-l2a",
    "item": "S2B_T43PGQ_20251223T051848_L2A",
}


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
        "B04": _band("red", "B04"),
        "B03": _band("green", "B03"),
        "B02": _band("blue", "B02"),
    }
    return cast(dict[str, Any], item)


def _band(common_name: str, name: str) -> dict[str, Any]:
    return {
        "href": (
            "https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/"
            f"sentinel-2-c1-l2a/synthetic/{name}.tif"
        ),
        "type": COG_MEDIA_TYPE,
        "eo:bands": [{"name": name, "common_name": common_name}],
        "raster:bands": [{"scale": 0.0001, "offset": -0.1, "nodata": 0}],
        "gsd": 10,
        "roles": ["data", "reflectance"],
    }


def _handler(
    item: dict[str, Any], *, head_status: int = 200
) -> Callable[[httpx2.Request], httpx2.Response]:
    fixture = _fixture()

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.method == "HEAD":
            return httpx2.Response(
                head_status,
                request=request,
                headers={"content-type": COG_MEDIA_TYPE, "content-length": "4096"},
            )
        if request.url.path == "/v1/collections":
            return httpx2.Response(
                200,
                request=request,
                headers={"content-type": "application/json"},
                json={"collections": [fixture["collection"]]},
            )
        if "/items/" in request.url.path:
            return httpx2.Response(
                200,
                request=request,
                headers={"content-type": "application/json"},
                json=item,
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    return handler


@contextmanager
def _client(
    *,
    head_status: int = 200,
    renderer: Callable[..., bytes] | None = None,
) -> Iterator[TestClient]:
    upstream = httpx2.AsyncClient(
        transport=httpx2.MockTransport(_handler(_item_with_rgb(), head_status=head_status))
    )
    provider = EarthSearchCatalogueProvider(client=upstream, max_retries=0)
    service = ImageryTileService(provider, renderer=renderer or _opaque_png)
    app = create_app(
        settings=make_settings(),
        database=UnavailableDatabase(),
        catalogue_provider=provider,
        imagery_tile_service=service,
    )
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        asyncio.run(service.aclose())
        asyncio.run(upstream.aclose())


def _opaque_png(*_args: object) -> bytes:
    return render(
        np.full((3, 256, 256), 128, dtype=np.uint8),
        mask=np.full((256, 256), 255, dtype=np.uint8),
        img_format="PNG",
    )


def _tile_for(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    count = 2**zoom
    x = int((lon + 180.0) / 360.0 * count)
    latitude = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(latitude)) / math.pi) / 2.0 * count)
    return x, y


def _metadata(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/v1/imagery/tile-sets", json={"scene": SCENE})
    assert response.status_code == 200
    return cast(dict[str, Any], response.json())


def test_tile_metadata_and_nonempty_png_use_only_stable_identity() -> None:
    with _client() as client:
        metadata = _metadata(client)
        x, y = _tile_for(77.35, 13.05, 8)
        tile = client.get(f"/api/v1/imagery/tiles/{metadata['tile_set_id']}/8/{x}/{y}.png")
        rejected = client.post(
            "/api/v1/imagery/tile-sets",
            json={"scene": SCENE, "url": "file:///etc/passwd"},
        )
        unsupported_recipe = client.post(
            "/api/v1/imagery/tile-sets",
            json={"scene": SCENE, "render_preset": "unrestricted-expression"},
        )
        unsupported_display_parameter = client.post(
            "/api/v1/imagery/tile-sets",
            json={"scene": SCENE, "opacity": 1.5},
        )
        invalid_identity = client.post(
            "/api/v1/imagery/tile-sets",
            json={"scene": {**SCENE, "provider": "internal-provider"}},
        )

    assert metadata["render_preset"] == "natural-color"
    assert metadata["media_type"] == "image/png"
    assert metadata["url_template"].startswith("/api/v1/imagery/tiles/")
    assert tile.status_code == 200 and tile.headers["content-type"] == "image/png"
    assert len(tile.content) > 100
    assert rejected.status_code == 422
    assert unsupported_recipe.status_code == 422
    assert unsupported_display_parameter.status_code == 422
    assert invalid_identity.status_code == 422


@pytest.mark.parametrize(
    "location",
    [
        "file:///var/data/scene.tif",
        "http://127.0.0.1/scene.tif",
        "https://127.0.0.1/sentinel-2-c1-l2a/scene.tif",
        (
            "https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/"
            "sentinel-2-c1-l2a/%2e%2e/secret.tif"
        ),
        "https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/other/scene.tif",
    ],
)
def test_rejects_local_internal_and_unapproved_raster_locations(location: str) -> None:
    with pytest.raises(TileServiceError) as captured:
        _validate_source_location(location)

    assert captured.value.code == "UPSTREAM_INVALID_ASSET_LOCATION"


def test_invalid_tile_matrix_bounds_and_unknown_set_are_errors() -> None:
    with _client() as client:
        metadata = _metadata(client)
        invalid = client.get(f"/api/v1/imagery/tiles/{metadata['tile_set_id']}/2/4/0.png")
        outside = client.get(f"/api/v1/imagery/tiles/{metadata['tile_set_id']}/2/0/0.png")
        unknown = client.get("/api/v1/imagery/tiles/00000000-0000-0000-0000-000000000000/0/0/0.png")

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_TILE_COORDINATES"
    assert outside.status_code == 404
    assert outside.json()["error"]["code"] == "TILE_OUTSIDE_COVERAGE"
    assert unknown.status_code == 404


def test_tile_caches_are_keyed_by_scene_recipe_and_access_scope() -> None:
    upstream = httpx2.AsyncClient(transport=httpx2.MockTransport(_handler(_item_with_rgb())))
    provider = EarthSearchCatalogueProvider(client=upstream, max_retries=0)
    render_calls: list[tuple[int, int, int]] = []

    def counted_renderer(_sources: object, z: int, x: int, y: int, _tile_size: int) -> bytes:
        render_calls.append((z, x, y))
        return _opaque_png()

    service = ImageryTileService(provider, renderer=counted_renderer)

    async def exercise() -> tuple[TileMetadata, TileMetadata, TileMetadata]:
        request = TileMetadataRequest.model_validate({"scene": SCENE})
        first = await service.metadata(request, access_scope="owner:a")
        repeated = await service.metadata(request, access_scope="owner:a")
        other_scope = await service.metadata(request, access_scope="owner:b")
        x, y = _tile_for(77.35, 13.05, 8)
        await service.tile(first.tile_set_id, 8, x, y, access_scope="owner:a")
        await service.tile(first.tile_set_id, 8, x, y, access_scope="owner:a")
        await service.aclose()
        await upstream.aclose()
        return first, repeated, other_scope

    first, repeated, other_scope = asyncio.run(exercise())

    assert first.tile_set_id == repeated.tile_set_id
    assert first.tile_set_id != other_scope.tile_set_id
    assert render_calls == [(8, *_tile_for(77.35, 13.05, 8))]


def test_restricted_asset_and_upstream_render_failure_are_not_successes() -> None:
    with _client(head_status=403) as client:
        denied = client.post("/api/v1/imagery/tile-sets", json={"scene": SCENE})

    def fail(*_args: object) -> bytes:
        raise RuntimeError("synthetic upstream read failure")

    with _client(renderer=fail) as client:
        metadata = _metadata(client)
        x, y = _tile_for(77.35, 13.05, 8)
        failed = client.get(f"/api/v1/imagery/tiles/{metadata['tile_set_id']}/8/{x}/{y}.png")

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "IMAGERY_ACCESS_DENIED"
    assert failed.status_code == 502
    assert failed.json()["error"]["code"] == "TILE_RENDER_FAILED"


def test_nodata_is_transparent_in_rendered_png() -> None:
    upstream = httpx2.AsyncClient(transport=httpx2.MockTransport(_handler(_item_with_rgb())))
    provider = EarthSearchCatalogueProvider(
        client=upstream,
        max_retries=0,
    )
    source_set = asyncio.run(
        provider.resolve_imagery_sources(AssetResolutionRequest.model_validate({"scene": SCENE}))
    )
    data = np.zeros((256, 256), dtype=np.uint16)
    data[:, :128] = 2500
    mercator_limit = 20037508.342789244
    transform = from_bounds(
        -mercator_limit, -mercator_limit, mercator_limit, mercator_limit, 256, 256
    )
    local_sources = []
    memories: list[MemoryFile] = []
    for index, source in enumerate(source_set.sources):
        memory = MemoryFile(filename=f"band-{index}.tif")
        memories.append(memory)
        with memory.open(
            driver="GTiff",
            width=256,
            height=256,
            count=1,
            dtype="uint16",
            crs="EPSG:3857",
            transform=transform,
            nodata=0,
            tiled=True,
            blockxsize=128,
            blockysize=128,
        ) as dataset:
            dataset.write(data, 1)
        local_sources.append(
            replace(
                source,
                component=source.component.model_copy(
                    update={
                        "crs": "EPSG:3857",
                        "shape": (256, 256),
                        "transform": tuple(transform),
                    }
                ),
                location=memory.name,
            )
        )

    rendered = _render_natural_color(tuple(local_sources), 0, 0, 0, 256)
    with MemoryFile(rendered) as memory:
        with memory.open() as image:
            alpha = image.read(4)

    assert np.all(alpha[:, :120] == 255)
    assert np.all(alpha[:, 136:] == 0)
    for memory in memories:
        memory.close()
    asyncio.run(provider.aclose())
    asyncio.run(upstream.aclose())
