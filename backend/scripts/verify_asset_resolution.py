"""Resolve one real Phase 4 selection using metadata and bounded HEAD checks only."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from satquery.api.schemas.asset_resolution import AssetResolutionResponse
from satquery.core.config import load_settings
from satquery.db.session import DatabaseReadiness
from satquery.main import create_app

SCENE = {
    "provider": "earth-search",
    "collection": "sentinel-2-c1-l2a",
    "item": "S2C_T43PGQ_20251228T052411_L2A",
}


class DatabaseMustNotBeUsed:
    async def check_readiness(self) -> DatabaseReadiness:
        raise AssertionError("Public asset resolution must not access the database")

    async def dispose(self) -> None:
        return None


def main() -> None:
    app = create_app(settings=load_settings(), database=DatabaseMustNotBeUsed())
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/catalog/asset-resolutions",
            json={"scene": SCENE},
            headers={"X-Request-ID": "phase-5b-live-resolution"},
        )
    response.raise_for_status()
    result = AssetResolutionResponse.model_validate(response.json())
    print(
        json.dumps(
            {
                "route": "/api/v1/catalog/asset-resolutions",
                "http_status": response.status_code,
                "request_id": response.headers.get("x-request-id"),
                "scene": result.scene.model_dump(),
                "state": result.status.state,
                "reason": result.status.reason,
                "resolved_asset": (
                    result.resolved_asset.identity.asset
                    if result.resolved_asset is not None
                    else None
                ),
                "components": [
                    {
                        "asset": component.identity.asset,
                        "band": component.band_name,
                        "common_name": component.common_name,
                        "media_type": component.media_type,
                        "scale": component.scale,
                        "offset": component.offset,
                        "nodata": component.nodata,
                        "crs": component.crs,
                        "resolution_metres": component.resolution_metres,
                        "shape": component.shape,
                        "access_check": component.access_check,
                        "content_length_bytes": component.content_length_bytes,
                    }
                    for component in result.components
                ],
                "thumbnail_separate": result.thumbnail is not None,
                "license": result.license.name if result.license is not None else None,
                "checked_at": result.checked_at.isoformat(),
                "database_accessed": False,
                "raster_downloaded": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
