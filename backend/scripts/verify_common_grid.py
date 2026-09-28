"""Verify Task 6D against a small real Sentinel-2 optical pair."""

from __future__ import annotations

import asyncio
import json

from satquery.api.schemas.processing import PreparationRequest
from satquery.core.config import load_settings
from satquery.processing import (
    CommonGridResult,
    CommonGridService,
    QualityMaskService,
    RasterInputService,
    ScenePreparationInput,
)
from satquery.providers.catalog import EarthSearchCatalogueProvider

SCENES = [
    {
        "provider": "earth-search",
        "collection": "sentinel-2-c1-l2a",
        "item": "S2C_T43PGQ_20251218T052410_L2A",
    },
    {
        "provider": "earth-search",
        "collection": "sentinel-2-c1-l2a",
        "item": "S2C_T43PGQ_20251228T052411_L2A",
    },
]
AOI = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.0000, 13.0000],
            [77.0080, 13.0000],
            [77.0080, 13.0080],
            [77.0000, 13.0080],
            [77.0000, 13.0000],
        ]
    ],
}
BANDS = [
    {"role": "red", "common_name": "red"},
    {"role": "green", "common_name": "green"},
    {"role": "blue", "common_name": "blue"},
]


def _request(scenes: list[dict[str, str]], *, pair: bool) -> PreparationRequest:
    return PreparationRequest.model_validate(
        {
            "scenes": scenes,
            "aoi": AOI,
            "required_bands": BANDS,
            "intended_task": "optical_pair" if pair else "optical_single_scene",
            "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
            "options": {
                "grid_policy": "common_utm" if pair else "source_aligned",
                "target_resolution_metres": 10.0,
                "continuous_resampling": "bilinear" if pair else "nearest",
                "max_output_pixels": 10_000,
            },
        }
    )


async def prepare_real_pair() -> CommonGridResult:
    provider = EarthSearchCatalogueProvider.from_settings(load_settings())
    raster_service = RasterInputService(provider)
    quality_service = QualityMaskService(provider)
    inputs: list[ScenePreparationInput] = []
    try:
        for scene in SCENES:
            raster = await raster_service.extract(_request([scene], pair=False))
            quality = await quality_service.decode(raster)
            inputs.append(ScenePreparationInput(raster, quality))
        return CommonGridService().prepare(_request(SCENES, pair=True), tuple(inputs))
    finally:
        await provider.aclose()


async def verify() -> None:
    result = await prepare_real_pair()
    print(
        json.dumps(
            {
                "scenes": SCENES,
                "aoi_wgs84": AOI,
                "grid": result.grid.model_dump(mode="json"),
                "area_method": result.area_method,
                "continuous_resampling": result.scenes[0].continuous_resampling,
                "mask_resampling": "nearest",
                "scene_coverage": [
                    {
                        "scene": scene.scene.item,
                        "native_resolutions_metres": scene.native_resolutions_metres,
                        "output_resolution_metres": scene.output_resolution_metres,
                        "quality_information": scene.quality.quality_information,
                        "statistics": [
                            {
                                "name": item.name,
                                "pixels": item.pixel_count,
                                "denominator": item.denominator_name,
                                "denominator_pixels": item.denominator_pixels,
                                "percent": item.percent,
                                "area_square_metres": item.area_square_metres,
                            }
                            for item in scene.coverage
                        ],
                    }
                    for scene in result.scenes
                ],
                "pair_coverage": [
                    {
                        "name": item.name,
                        "pixels": item.pixel_count,
                        "denominator": item.denominator_name,
                        "denominator_pixels": item.denominator_pixels,
                        "percent": item.percent,
                        "area_square_metres": item.area_square_metres,
                    }
                    for item in result.pair_coverage
                ],
                "registration_status": result.registration_status,
                "radiometric_harmonization": result.radiometric_harmonization,
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
