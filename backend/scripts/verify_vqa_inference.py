"""Verify one real scientific chip and, when configured, live VQA plus caption inference."""

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
from satquery.api.schemas.vqa import ReferringGroundingRequest, VqaCaptionRequest
from satquery.core.config import load_settings
from satquery.inference import (
    ReferringGroundingService,
    SingleImageInferenceService,
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
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[2] / "tmp" / "phase-7f-real"


def _write_grounding_images(chip: Any, grounding: Any) -> tuple[str, str]:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    source_path = OUTPUT_DIRECTORY / "scientific-chip.png"
    overlay_path = OUTPUT_DIRECTORY / "grounding-overlay.png"
    source_path.write_bytes(chip.content)
    with Image.open(BytesIO(chip.content)) as source:
        overlay = source.convert("RGBA")
    draw = ImageDraw.Draw(overlay)
    for candidate in grounding.candidates:
        box = candidate.image_chip_box
        draw.rectangle(
            (box.x_min, box.y_min, box.x_max, box.y_max),
            outline=(255, 0, 0, 255),
            width=3,
        )
        draw.text((box.x_min + 3, box.y_min + 3), candidate.label, fill=(255, 0, 0, 255))
    overlay.save(overlay_path)
    return str(source_path), str(overlay_path)


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


async def verify() -> None:
    settings = load_settings()
    provider = EarthSearchCatalogueProvider.from_settings(settings)
    service = SingleImageInferenceService.from_settings(settings)
    attempts: list[dict[str, Any]] = []
    selected: tuple[Any, Any, Any] | None = None
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
                    "limit": 2,
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
            request = _preparation_request(scene)
            try:
                raster = await RasterInputService(provider, max_pixels=20_000).extract(request)
                quality = await QualityMaskService(provider).decode(raster)
                chip = build_model_chip(
                    raster=raster,
                    quality=quality,
                    request=request,
                    catalogue_scene=item,
                )
            except Exception as exc:
                attempts.append(
                    {
                        "scene": scene.item,
                        "status": "failed",
                        "failure_type": type(exc).__name__,
                    }
                )
                continue
            attempts.append(
                {
                    "scene": scene.item,
                    "status": "prepared",
                    "readiness": chip.contract.phase6_quality.readiness.state,
                    "quality_checks": [
                        {
                            "id": check.check_id,
                            "outcome": check.outcome,
                            "measured_value": check.measured_value,
                        }
                        for check in chip.contract.phase6_quality.quality_checks
                    ],
                }
            )
            if chip.contract.phase6_quality.readiness.state == "ready":
                selected = (item, request, chip)
                break

        if selected is None:
            output = {
                "status": "blocked",
                "reason": "No searched real scene produced a VQA-ready chip.",
                "attempts": attempts,
                "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
            }
        else:
            item, _request, chip = selected
            grounding_started = perf_counter()
            grounding = await ReferringGroundingService(
                TransformersGroundingDinoRuntime(local_files_only=True),
                timeout_seconds=300.0,
            ).locate(
                ReferringGroundingRequest(
                    request_id=uuid4(),
                    image_chip=chip.contract,
                    referring_text="vegetation",
                    box_threshold=0.25,
                    text_threshold=0.2,
                    max_candidates=5,
                ),
                chip,
            )
            grounding_latency_ms = round((perf_counter() - grounding_started) * 1000.0, 3)
            source_path, overlay_path = _write_grounding_images(chip, grounding)
            chip_summary = {
                "source_item": chip.contract.scene.item,
                "acquired_at": chip.contract.acquired_at.isoformat(),
                "source_assets": [asset.asset for asset in chip.contract.source_assets],
                "band_order": list(chip.contract.band_order),
                "rendering": chip.contract.rendering.model_dump(mode="json"),
                "width": chip.contract.width,
                "height": chip.contract.height,
                "footprint_wgs84": chip.contract.footprint_wgs84.model_dump(mode="json"),
                "crs": chip.contract.pixel_to_map.crs,
                "transform": chip.contract.pixel_to_map.affine,
                "checksum_sha256": chip.contract.checksum_sha256,
                "byte_size": chip.contract.byte_size,
                "readiness": chip.contract.phase6_quality.readiness.model_dump(mode="json"),
                "catalogue_cloud_percent": (
                    item.cloud_cover.percent if item.cloud_cover is not None else None
                ),
            }
            if service is None:
                output = {
                    "status": "inference_not_run",
                    "reason": "Server-side runtime AI provider/model/credential is not configured.",
                    "chip": chip_summary,
                    "attempts": attempts,
                    "hardware": {
                        "host_system": platform.platform(),
                        "host_processor": platform.processor() or "unavailable",
                        "model_execution": "provider_managed_not_disclosed",
                    },
                    "grounding": grounding.model_dump(mode="json"),
                    "grounding_latency_ms": grounding_latency_ms,
                    "inspection": {"source_chip": source_path, "overlay": overlay_path},
                    "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
                }
            else:
                vqa_request = VqaCaptionRequest(
                    request_id=uuid4(),
                    task="visual_question_answering",
                    image_chip=chip.contract,
                    question="What broad land-cover patterns are visible in this image?",
                    grounding="not_requested",
                    max_answer_characters=1000,
                )
                caption_request = VqaCaptionRequest(
                    request_id=uuid4(),
                    task="image_captioning",
                    image_chip=chip.contract,
                    grounding="not_requested",
                    max_answer_characters=1000,
                )
                vqa = await service.answer_question(vqa_request, chip)
                caption = await service.caption(caption_request, chip)
                output = {
                    "status": "completed",
                    "chip": chip_summary,
                    "vqa": vqa.model_dump(mode="json"),
                    "caption": caption.model_dump(mode="json"),
                    "hardware": {
                        "host_system": platform.platform(),
                        "host_processor": platform.processor() or "unavailable",
                        "model_execution": vqa.model.execution_hardware,
                    },
                    "grounding": grounding.model_dump(mode="json"),
                    "grounding_latency_ms": grounding_latency_ms,
                    "inspection": {"source_chip": source_path, "overlay": overlay_path},
                    "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
                }
        serialized = json.dumps(output, indent=2)
        OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIRECTORY / "verification.json").write_text(serialized + "\n", encoding="utf-8")
        print(serialized)
    finally:
        if service is not None:
            await service.aclose()
        await provider.aclose()


def main() -> None:
    asyncio.run(verify())


if __name__ == "__main__":
    main()
