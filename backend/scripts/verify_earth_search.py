"""Run the bounded, metadata-only Phase 4B Earth Search smoke check."""

from __future__ import annotations

import asyncio
import json

from satquery.api.schemas.catalog import CatalogueSearchRequest
from satquery.providers.catalog import EarthSearchCatalogueProvider


async def verify() -> None:
    request = CatalogueSearchRequest.model_validate(
        {
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
            "limit": 2,
            "sort": "acquired_desc",
        }
    )
    provider = EarthSearchCatalogueProvider()
    try:
        capabilities = await provider.capabilities()
        collections = await provider.collections()
        response = await provider.search(request)
        detail = await provider.item(
            response.items[-1].collection.id,
            response.items[-1].provider_asset_id,
        )
        print(
            json.dumps(
                {
                    "query": request.model_dump(mode="json"),
                    "stac_version": capabilities.stac_version,
                    "queryables": capabilities.supported_queryables,
                    "collections": [collection.id for collection in collections],
                    "searched_at": response.searched_at.isoformat(),
                    "item_ids": [item.provider_asset_id for item in response.items],
                    "cloud_cover": [
                        item.cloud_cover.percent if item.cloud_cover is not None else None
                        for item in response.items
                    ],
                    "next_cursor_available": response.next_cursor is not None,
                    "detail_id": detail.provider_asset_id,
                    "detail_retrieved_at": detail.provenance.retrieved_at.isoformat(),
                },
                indent=2,
            )
        )
    finally:
        await provider.aclose()


if __name__ == "__main__":
    asyncio.run(verify())
