"""Bounded live verification for the explicitly supported Phase 9B product."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from satquery.api.schemas.sar import SarDiscoveryRequest, SarPreparationRequest
from satquery.processing.sar import SarRasterService
from satquery.providers.catalog.inpe_sar import InpeSarProvider


async def main() -> None:
    aoi = {
        "type": "Polygon",
        "coordinates": [
            [
                [-46.650, -23.560],
                [-46.650, -23.557],
                [-46.647, -23.557],
                [-46.647, -23.560],
                [-46.650, -23.560],
            ]
        ],
    }
    provider = InpeSarProvider()
    service = SarRasterService(provider)
    try:
        discovery = await provider.search(
            SarDiscoveryRequest.model_validate(
                {
                    "aoi": aoi,
                    "acquisition": {
                        "start": datetime(2025, 1, 1, tzinfo=UTC),
                        "end": datetime(2025, 2, 1, tzinfo=UTC),
                    },
                    "limit": 5,
                }
            )
        )
        scene = next(item for item in discovery.scenes if "VV" in item.polarizations)
        outcome = await service.prepare(
            SarPreparationRequest.model_validate(
                {"scene": scene.source, "aoi": aoi, "polarization": "VV"}
            )
        )
        raster = service.analytical_raster(outcome.preparation_id)
        valid_values = raster.values[raster.valid_mask]
        print(
            json.dumps(
                {
                    "source": outcome.source.model_dump(),
                    "acquisition": outcome.acquisition_time.isoformat(),
                    "available_polarizations": scene.polarizations,
                    "shape": [outcome.height, outcome.width],
                    "crs": outcome.crs,
                    "transform": outcome.transform,
                    "valid_pixels": outcome.mask.valid_pixels,
                    "aoi_pixels": outcome.mask.aoi_pixels,
                    "nodata_pixels": outcome.mask.nodata_pixels,
                    "layover_shadow_pixels": outcome.mask.layover_or_shadow_pixels,
                    "minimum_gamma0_power": float(valid_values.min()),
                    "maximum_gamma0_power": float(valid_values.max()),
                    "preview_bytes": len(service.preview(outcome.preparation_id)),
                    "terrain_model": outcome.terrain_model,
                },
                indent=2,
            )
        )
    finally:
        await provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())
