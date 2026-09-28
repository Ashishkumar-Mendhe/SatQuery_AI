from __future__ import annotations

import json

from fastapi.testclient import TestClient

from satquery.api.schemas.catalog import CatalogueSearchResponse
from satquery.core.config import load_settings
from satquery.db.session import DatabaseReadiness
from satquery.main import create_app


class DatabaseMustNotBeUsed:
    async def check_readiness(self) -> DatabaseReadiness:
        raise AssertionError("Public catalogue search must not access the database")

    async def dispose(self) -> None:
        return None


def main() -> None:
    app = create_app(settings=load_settings(), database=DatabaseMustNotBeUsed())
    request_id = "catalog-api-live-smoke"
    payload = {
        "provider": "earth-search",
        "aoi": {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.5, 12.9],
                    [77.7, 12.9],
                    [77.7, 13.05],
                    [77.5, 13.05],
                    [77.5, 12.9],
                ]
            ],
        },
        "acquisition": {
            "start": "2025-01-01T00:00:00Z",
            "end": "2025-12-31T23:59:59Z",
        },
        "collections": ["sentinel-2-c1-l2a"],
        "cloud_cover": {"max_percent": 100.0},
        "limit": 1,
        "sort": "acquired_desc",
    }
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/catalog/searches",
            json=payload,
            headers={"X-Request-ID": request_id},
        )
    response.raise_for_status()
    result = CatalogueSearchResponse.model_validate(response.json())
    print(
        json.dumps(
            {
                "route": "/api/v1/catalog/searches",
                "http_status": response.status_code,
                "request_id": response.headers.get("x-request-id"),
                "provider": result.provider.id,
                "returned_count": result.returned_count,
                "item_ids": [item.provider_asset_id for item in result.items],
                "next_cursor_present": result.next_cursor is not None,
                "searched_at": result.searched_at.isoformat(),
                "database_accessed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
