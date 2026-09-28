"""Bounded real-chip/VQA smoke, separate from the protected browser job gate."""

from __future__ import annotations

import asyncio
import json
from time import perf_counter
from uuid import uuid4

from satquery.api.schemas.processing import PreparationRequest
from satquery.api.schemas.viewer import ViewerSceneIdentity
from satquery.api.schemas.vqa import VqaCaptionRequest
from satquery.core.config import load_settings
from satquery.inference import SingleImageInferenceService, build_model_chip
from satquery.inference.service import InferenceError
from satquery.processing import QualityMaskService, RasterInputService
from satquery.providers.catalog import EarthSearchCatalogueProvider

SCENE = ViewerSceneIdentity(
    provider="earth-search",
    collection="sentinel-2-c1-l2a",
    item="S2B_T43PGQ_20251223T051848_L2A",
)
AOI = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.590, 12.970],
            [77.600, 12.970],
            [77.600, 12.980],
            [77.590, 12.980],
            [77.590, 12.970],
        ]
    ],
}
QUESTION = "What broad surface patterns are visible in this image?"


async def main() -> None:
    settings = load_settings()
    provider = EarthSearchCatalogueProvider.from_settings(settings)
    answer_service = SingleImageInferenceService.from_settings(settings)
    started = perf_counter()
    output: dict[str, object] = {"scene": SCENE.item, "question": QUESTION}
    try:
        catalogue_scene = await provider.item(SCENE.collection, SCENE.item)
        request = PreparationRequest.model_validate(
            {
                "scenes": [SCENE.model_dump(mode="json")],
                "aoi": AOI,
                "required_bands": [
                    {"role": role, "common_name": role} for role in ("red", "green", "blue")
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
        raster = await RasterInputService(provider, max_pixels=20_000).extract(request)
        quality = await QualityMaskService(provider).decode(raster)
        chip = build_model_chip(
            raster=raster,
            quality=quality,
            request=request,
            catalogue_scene=catalogue_scene,
        )
        output.update(
            {
                "acquired_at": chip.contract.acquired_at.isoformat(),
                "chip_id": str(chip.contract.chip_id),
                "chip_checksum_sha256": chip.contract.checksum_sha256,
                "chip_dimensions": [chip.contract.width, chip.contract.height],
                "source_assets": [asset.asset for asset in chip.contract.source_assets],
                "phase6_readiness": chip.contract.phase6_quality.readiness.state,
                "model_input": "trusted_scientific_rgb_chip_not_basemap_or_thumbnail",
            }
        )
        if answer_service is None:
            output.update(status="model_not_configured", reason="Set the server-only xAI settings.")
        else:
            inference_request = VqaCaptionRequest(
                request_id=uuid4(),
                task="visual_question_answering",
                image_chip=chip.contract,
                question=QUESTION,
                max_answer_characters=1000,
            )
            model_started = perf_counter()
            answer = await answer_service.answer_question(inference_request, chip)
            output.update(
                status="model_response",
                model=answer.model.model_dump(mode="json"),
                answer_availability=answer.availability,
                answer=answer.answer,
                reason=answer.reason,
                provider_response_id=answer.provider_response_id,
                model_latency_ms=round((perf_counter() - model_started) * 1000, 1),
                evidence_source_chip_ids=[str(ref.source_chip_id) for ref in answer.evidence],
            )
    except InferenceError as exc:
        output.update(status="model_failed", code=exc.code, reason=str(exc))
    except Exception as exc:
        output.update(status="preparation_failed", failure_type=type(exc).__name__)
    finally:
        output["elapsed_ms"] = round((perf_counter() - started) * 1000, 1)
        await provider.aclose()
        if answer_service is not None:
            await answer_service.aclose()
        print(json.dumps(output, sort_keys=True))
    if output.get("answer_availability") != "available":
        raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(main())
