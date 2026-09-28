"""Verify Task 6C masks against one real Sentinel-2 SCL asset."""

from __future__ import annotations

import asyncio
import json

from satquery.api.schemas.processing import PreparationRequest
from satquery.core.config import load_settings
from satquery.processing import QualityMaskService, RasterInputService
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
        raster = await RasterInputService(provider).extract(request)
        masks = await QualityMaskService(provider).decode(raster)
    finally:
        await provider.aclose()

    print(
        json.dumps(
            {
                "scene": SCENE,
                "aoi_wgs84": AOI,
                "quality_information": masks.quality_information,
                "quality_source_asset": masks.source_asset,
                "processing_baseline": masks.processing_baseline,
                "catalogue_scene_cloud_percent": masks.catalogue_scene_cloud_percent,
                "measured_aoi_statistics": [
                    {
                        "name": item.name,
                        "pixel_count": item.pixel_count,
                        "denominator_name": item.denominator_name,
                        "denominator_pixels": item.denominator_pixels,
                        "percent": item.percent,
                    }
                    for item in masks.coverage
                ],
                "scl_classes_present": sorted(
                    int(value) for value in set(masks.scl_classes.ravel())
                ),
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
