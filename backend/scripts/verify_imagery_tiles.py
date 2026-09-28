"""Render one real natural-colour tile through SatQuery's stable-identity API."""

from __future__ import annotations

import json
import math

import numpy as np
from fastapi.testclient import TestClient
from rasterio.io import MemoryFile

from satquery.api.schemas.viewer import TileMetadata
from satquery.core.config import load_settings
from satquery.db.session import DatabaseReadiness
from satquery.main import create_app

SCENE = {
    "provider": "earth-search",
    "collection": "sentinel-2-c1-l2a",
    "item": "S2C_T43PGQ_20251228T052411_L2A",
}
ZOOM = 8


class DatabaseMustNotBeUsed:
    async def check_readiness(self) -> DatabaseReadiness:
        raise AssertionError("Public imagery tile delivery must not access the database")

    async def dispose(self) -> None:
        return None


def _tile_for(lon: float, lat: float) -> tuple[int, int]:
    count = 2**ZOOM
    x = int((lon + 180.0) / 360.0 * count)
    latitude = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(latitude)) / math.pi) / 2.0 * count)
    return x, y


def main() -> None:
    app = create_app(settings=load_settings(), database=DatabaseMustNotBeUsed())
    with TestClient(app, raise_server_exceptions=False) as client:
        metadata_response = client.post(
            "/api/v1/imagery/tile-sets",
            json={"scene": SCENE},
            headers={"X-Request-ID": "phase-5c-live-metadata"},
        )
        metadata_response.raise_for_status()
        metadata = TileMetadata.model_validate(metadata_response.json())
        west, south, east, north = metadata.bounds
        x, y = _tile_for((west + east) / 2.0, (south + north) / 2.0)
        assert metadata.url_template is not None
        tile_path = (
            metadata.url_template.replace("{z}", str(ZOOM))
            .replace("{x}", str(x))
            .replace("{y}", str(y))
        )
        tile_response = client.get(
            tile_path,
            headers={"X-Request-ID": "phase-5c-live-tile"},
        )
        tile_response.raise_for_status()

    with MemoryFile(tile_response.content) as memory:
        with memory.open() as image:
            rgba = image.read()
    alpha = rgba[3]
    valid = alpha > 0
    assert rgba.shape == (4, 256, 256)
    assert np.any(valid)
    assert np.any(rgba[:3, valid] > 0)
    print(
        json.dumps(
            {
                "metadata_route": "/api/v1/imagery/tile-sets",
                "metadata_http_status": metadata_response.status_code,
                "metadata_request_id": metadata_response.headers.get("x-request-id"),
                "tile_http_status": tile_response.status_code,
                "tile_request_id": tile_response.headers.get("x-request-id"),
                "scene": SCENE,
                "resolved_asset": metadata.asset.asset,
                "render_preset": metadata.render_preset,
                "bounds": metadata.bounds,
                "tile": {"matrix": "WebMercatorQuad", "z": ZOOM, "x": x, "y": y},
                "tile_size": metadata.tile_size,
                "media_type": tile_response.headers.get("content-type"),
                "response_bytes": len(tile_response.content),
                "valid_pixels": int(np.count_nonzero(valid)),
                "transparent_pixels": int(valid.size - np.count_nonzero(valid)),
                "rgb_min_valid": int(rgba[:3, valid].min()),
                "rgb_max_valid": int(rgba[:3, valid].max()),
                "database_accessed": False,
                "browser_rendered": False,
                "analysis_performed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
