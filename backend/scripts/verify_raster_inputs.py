"""Run one small real Task 6B AOI extraction without exposing provider locations."""

from __future__ import annotations

import asyncio
import json

import numpy as np

from satquery.api.schemas.processing import PreparationRequest
from satquery.core.config import load_settings
from satquery.processing import RasterInputService
from satquery.providers.catalog import EarthSearchCatalogueProvider

SCENE = {
    "provider": "earth-search",
    "collection": "sentinel-2-c1-l2a",
    "item": "S2C_T43PGQ_20251228T052411_L2A",
}
AOI = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.5940, 12.9700],
            [77.5950, 12.9700],
            [77.5950, 12.9710],
            [77.5940, 12.9710],
            [77.5940, 12.9700],
        ]
    ],
}


async def verify() -> None:
    provider = EarthSearchCatalogueProvider.from_settings(load_settings())
    service = RasterInputService(provider)
    request = PreparationRequest.model_validate(
        {
            "scenes": [SCENE],
            "aoi": AOI,
            "required_bands": [
                {"role": "red", "common_name": "red"},
                {"role": "green", "common_name": "green"},
                {"role": "blue", "common_name": "blue"},
            ],
            "intended_task": "optical_single_scene",
            "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
            "options": {
                "grid_policy": "source_aligned",
                "target_resolution_metres": 10.0,
                "continuous_resampling": "nearest",
                "max_output_pixels": 10_000,
            },
        }
    )
    try:
        result = await service.extract(request)
    finally:
        await provider.aclose()

    band_results = []
    for index, band in enumerate(result.bands):
        valid_values = result.data[index][result.band_validity[index]]
        band_results.append(
            {
                "role": band.role,
                "source_asset": band.source.asset,
                "band_name": band.band_name,
                "units": band.units,
                "native_resolution_metres": band.native_resolution_metres,
                "provider_scale": band.provider_scale,
                "provider_offset": band.provider_offset,
                "calibration_method": band.method,
                "valid_pixels": int(valid_values.size),
                "calibrated_min": float(np.min(valid_values)),
                "calibrated_max": float(np.max(valid_values)),
            }
        )
    print(
        json.dumps(
            {
                "scene": result.scene.model_dump(),
                "requested_aoi_wgs84": AOI,
                "output_crs": result.crs,
                "output_transform": result.transform,
                "output_bounds": result.bounds,
                "width": result.width,
                "height": result.height,
                "inside_aoi_pixels": int(result.inside_aoi_mask.sum()),
                "band_order": result.band_order,
                "bands": band_results,
                "provider_locations_exposed": False,
                "source_assets_modified": False,
            },
            indent=2,
        )
    )


def main() -> None:
    asyncio.run(verify())


if __name__ == "__main__":
    main()
