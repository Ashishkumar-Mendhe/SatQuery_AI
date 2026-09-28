"""Bounded live optical/SAR co-location check; no cross-modal analysis claim."""

from __future__ import annotations

import asyncio
import json

from satquery.api.schemas.catalog import CatalogueSearchRequest
from satquery.api.schemas.processing import PreparationRequest
from satquery.api.schemas.sar import SarDiscoveryRequest, SarPreparationRequest
from satquery.processing.optical_sar_pair import OpticalSarPairService
from satquery.processing.sar import SarRasterService
from satquery.providers.catalog.earth_search import EarthSearchCatalogueProvider
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
    optical_provider = EarthSearchCatalogueProvider()
    sar_provider = InpeSarProvider()
    try:
        optical_search = await optical_provider.search(
            CatalogueSearchRequest.model_validate(
                {
                    "provider": "earth-search",
                    "aoi": aoi,
                    "acquisition": {"start": "2025-01-01T00:00:00Z", "end": "2025-02-10T00:00:00Z"},
                    "collections": ["sentinel-2-c1-l2a"],
                    "limit": 25,
                }
            )
        )
        sar_search = await sar_provider.search(
            SarDiscoveryRequest.model_validate(
                {
                    "aoi": aoi,
                    "acquisition": {"start": "2025-01-01T00:00:00Z", "end": "2025-02-10T00:00:00Z"},
                    "limit": 25,
                }
            )
        )
        if not optical_search.items or not sar_search.scenes:
            raise RuntimeError("No real optical/SAR candidate in the bounded São Paulo search")
        optical = min(
            optical_search.items,
            key=lambda item: (
                item.cloud_cover.percent if item.cloud_cover is not None else 101.0,
                abs(
                    (
                        item.acquisition.start - sar_search.scenes[0].acquisition.start
                    ).total_seconds()
                ),
            ),
        )
        sar = next(item for item in sar_search.scenes if "VV" in item.polarizations)
        print(
            json.dumps(
                {
                    "selected_optical": optical.provider_asset_id,
                    "selected_optical_acquisition": optical.acquisition.start.isoformat(),
                    "selected_sar": sar.source.item,
                    "selected_sar_acquisition": sar.acquisition.start.isoformat(),
                }
            ),
            flush=True,
        )
        optical_request = PreparationRequest.model_validate(
            {
                "scenes": [
                    {
                        "provider": "earth-search",
                        "collection": "sentinel-2-c1-l2a",
                        "item": optical.provider_asset_id,
                    }
                ],
                "aoi": aoi,
                "required_bands": [
                    {"role": role, "common_name": role} for role in ("red", "green", "blue")
                ],
                "intended_task": "optical_single_scene",
                "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
                "options": {
                    "grid_policy": "common_utm",
                    "target_resolution_metres": 20.0,
                    "continuous_resampling": "bilinear",
                    "max_output_pixels": 100_000,
                },
            }
        )
        sar_request = SarPreparationRequest.model_validate(
            {"scene": sar.source.model_dump(mode="json"), "aoi": aoi, "polarization": "VV"}
        )
        pair = await OpticalSarPairService().prepare_real(
            optical_request, sar_request, optical_provider, SarRasterService(sar_provider)
        )
        print(
            json.dumps(
                {
                    "state": pair.state,
                    "optical_source": pair.optical_source.model_dump(mode="json"),
                    "sar_source": pair.sar_source.model_dump(mode="json"),
                    "optical_acquisition": pair.optical_acquired_at.isoformat(),
                    "sar_acquisition": pair.sar_acquired_at.isoformat(),
                    "time_gap_hours": pair.time_gap_hours,
                    "optical_catalogue_cloud_percent": (
                        optical.cloud_cover.percent if optical.cloud_cover else None
                    ),
                    "grid": pair.grid.grid.model_dump(mode="json"),
                    "coverage": pair.coverage.__dict__
                    if hasattr(pair.coverage, "__dict__")
                    else {
                        name: getattr(pair.coverage, name)
                        for name in pair.coverage.__dataclass_fields__
                    },
                    "alignment": pair.alignment.state,
                    "reasons": pair.reasons,
                    "warnings": pair.warnings,
                },
                indent=2,
            )
        )
    finally:
        await optical_provider.aclose()
        await sar_provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())
