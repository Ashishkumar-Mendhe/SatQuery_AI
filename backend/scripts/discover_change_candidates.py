"""List bounded real Sentinel-2 candidates for the Phase 8 workflow verifier."""

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
                        [77.585, 12.965],
                        [77.605, 12.965],
                        [77.605, 12.985],
                        [77.585, 12.985],
                        [77.585, 12.965],
                    ]
                ],
            },
            "acquisition": {
                "start": "2025-01-01T00:00:00Z",
                "end": "2025-12-31T23:59:59Z",
            },
            "collections": ["sentinel-2-c1-l2a"],
            "cloud_cover": {"max_percent": 10.0},
            "limit": 20,
            "sort": "acquired_desc",
        }
    )
    provider = EarthSearchCatalogueProvider()
    try:
        response = await provider.search(request)
        print(
            json.dumps(
                [
                    {
                        "item": item.provider_asset_id,
                        "acquired_at": item.acquisition.start.isoformat(),
                        "catalogue_cloud_percent": (
                            item.cloud_cover.percent if item.cloud_cover else None
                        ),
                    }
                    for item in response.items
                ],
                indent=2,
            )
        )
    finally:
        await provider.aclose()


if __name__ == "__main__":
    asyncio.run(verify())
