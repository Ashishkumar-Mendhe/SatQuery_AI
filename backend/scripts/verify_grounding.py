"""Run one real-scene Grounding DINO check and save a labelled inspection overlay."""

from __future__ import annotations

import asyncio
import json
import platform
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from PIL import Image, ImageDraw

from satquery.api.schemas.catalog import CatalogueSearchRequest
from satquery.api.schemas.processing import PreparationRequest
from satquery.api.schemas.viewer import ViewerSceneIdentity
from satquery.api.schemas.vqa import ReferringGroundingRequest
from satquery.core.config import load_settings
from satquery.inference import (
    ReferringGroundingService,
    TransformersGroundingDinoRuntime,
    build_model_chip,
)
from satquery.processing import QualityMaskService, RasterInputService
from satquery.providers.catalog import EarthSearchCatalogueProvider

AOI = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.5900, 12.9700],
            [77.6000, 12.9700],
            [77.6000, 12.9800],
            [77.5900, 12.9800],
            [77.5900, 12.9700],
        ]
    ],
}
REFERRING_TEXT = "vegetation"
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[2] / "tmp" / "phase-7c-grounding"


def _preparation_request(scene: ViewerSceneIdentity) -> PreparationRequest:
    return PreparationRequest.model_validate(
        {
            "scenes": [scene.model_dump(mode="json")],
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
                "max_output_pixels": 20_000,
            },
        }
    )


def _write_inspection_images(chip: Any, result: Any) -> tuple[str, str]:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    source_path = OUTPUT_DIRECTORY / "scientific-chip.png"
    overlay_path = OUTPUT_DIRECTORY / "grounding-overlay.png"
    source_path.write_bytes(chip.content)
    with Image.open(BytesIO(chip.content)) as source:
        overlay = source.convert("RGBA")
    draw = ImageDraw.Draw(overlay)
    if result.selected_region is not None:
        selected = result.selected_region
        draw.rectangle(
            (selected.x_min, selected.y_min, selected.x_max, selected.y_max),
            outline=(0, 255, 0, 255),
            width=3,
        )
    for candidate in result.candidates:
        box = candidate.image_chip_box
        draw.rectangle(
            (box.x_min, box.y_min, box.x_max, box.y_max),
            outline=(255, 0, 0, 255),
            width=3,
        )
        draw.text((box.x_min + 3, box.y_min + 3), candidate.label, fill=(255, 0, 0, 255))
    overlay.save(overlay_path)
    return str(source_path), str(overlay_path)


async def verify() -> None:
    settings = load_settings()
    provider = EarthSearchCatalogueProvider.from_settings(settings)
    attempts: list[dict[str, Any]] = []
    started = perf_counter()
    try:
        search = await provider.search(
            CatalogueSearchRequest.model_validate(
                {
                    "provider": "earth-search",
                    "aoi": AOI,
                    "acquisition": {
                        "start": "2025-01-01T00:00:00Z",
                        "end": "2025-12-31T23:59:59Z",
                    },
                    "collections": ["sentinel-2-c1-l2a"],
                    "cloud_cover": {"max_percent": 10.0},
                    "limit": 3,
                    "sort": "acquired_desc",
                }
            )
        )
        for item in search.items:
            scene = ViewerSceneIdentity(
                provider=item.provider.id,
                collection=item.collection.id,
                item=item.provider_asset_id,
            )
            preparation = _preparation_request(scene)
            try:
                raster = await RasterInputService(provider, max_pixels=20_000).extract(preparation)
                quality = await QualityMaskService(provider).decode(raster)
                chip = build_model_chip(
                    raster=raster,
                    quality=quality,
                    request=preparation,
                    catalogue_scene=item,
                )
            except Exception as exc:
                attempts.append(
                    {"scene": scene.item, "status": "failed", "failure": type(exc).__name__}
                )
                continue
            if chip.contract.phase6_quality.readiness.state != "ready":
                attempts.append(
                    {
                        "scene": scene.item,
                        "status": "quality_blocked",
                        "readiness": chip.contract.phase6_quality.readiness.state,
                    }
                )
                continue
            request = ReferringGroundingRequest(
                request_id=uuid4(),
                image_chip=chip.contract,
                referring_text=REFERRING_TEXT,
                box_threshold=0.25,
                text_threshold=0.2,
                max_candidates=5,
            )
            result = await ReferringGroundingService(
                TransformersGroundingDinoRuntime(local_files_only=True),
                timeout_seconds=300.0,
            ).locate(request, chip)
            source_path, overlay_path = _write_inspection_images(chip, result)
            print(
                json.dumps(
                    {
                        "status": "completed",
                        "scene": scene.model_dump(mode="json"),
                        "acquired_at": chip.contract.acquired_at.isoformat(),
                        "source_assets": [
                            asset.model_dump(mode="json") for asset in chip.contract.source_assets
                        ],
                        "chip": {
                            "chip_id": str(chip.contract.chip_id),
                            "width": chip.contract.width,
                            "height": chip.contract.height,
                            "crs": chip.contract.pixel_to_map.crs,
                            "affine": chip.contract.pixel_to_map.affine,
                            "checksum_sha256": chip.contract.checksum_sha256,
                            "rendering": chip.contract.rendering.model_dump(mode="json"),
                        },
                        "grounding": result.model_dump(mode="json"),
                        "inspection": {
                            "source_chip": source_path,
                            "overlay": overlay_path,
                            "overlay_is_visual_verification_only": True,
                        },
                        "hardware": {
                            "host": platform.platform(),
                            "processor": platform.processor() or "unavailable",
                            "model_execution": "local_cpu",
                        },
                        "attempts": attempts,
                        "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
                    },
                    indent=2,
                )
            )
            return
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": "No searched real scene produced a quality-ready scientific chip.",
                    "attempts": attempts,
                    "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
                },
                indent=2,
            )
        )
    finally:
        await provider.aclose()


def main() -> None:
    asyncio.run(verify())


if __name__ == "__main__":
    main()
