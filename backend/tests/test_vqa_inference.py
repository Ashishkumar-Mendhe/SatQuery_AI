from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import replace
from io import BytesIO
from typing import Any
from uuid import uuid4

import httpx2
import numpy as np
import pytest
from PIL import Image

from satquery.api.schemas.catalog import CatalogueScene
from satquery.api.schemas.processing import PreparationRequest
from satquery.api.schemas.viewer import ResolvedImageryAssetIdentity, ViewerSceneIdentity
from satquery.api.schemas.vqa import InferenceParameters, VqaCaptionRequest
from satquery.inference import (
    InferenceError,
    OpenAIResponsesTransport,
    SingleImageInferenceService,
    TransportInferenceResult,
    build_model_chip,
)
from satquery.inference.service import (
    OPENAI_MODEL,
    OPENAI_RESPONSES_URL,
    XAI_MODEL,
    XAI_RESPONSES_URL,
    XAIResponsesTransport,
)
from satquery.processing.quality import OpticalQualityMasks
from satquery.processing.raster import BandCalibration, CalibratedRasterInput

SCENE = ViewerSceneIdentity(
    provider="earth-search",
    collection="sentinel-2-c1-l2a",
    item="synthetic-vqa-scene",
)


def _aoi() -> dict[str, Any]:
    return {
        "type": "Polygon",
        "coordinates": [[[77.5, 12.9], [77.51, 12.9], [77.51, 12.91], [77.5, 12.91], [77.5, 12.9]]],
    }


def _request() -> PreparationRequest:
    return PreparationRequest.model_validate(
        {
            "scenes": [SCENE.model_dump(mode="json")],
            "aoi": _aoi(),
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
                "max_output_pixels": 4096,
            },
        }
    )


def _catalogue_scene() -> CatalogueScene:
    fields = [
        "provider_asset_id",
        "collection.id",
        "acquisition.start",
        "acquisition.end",
        "footprint",
        "bbox",
        "asset_access",
    ]
    return CatalogueScene.model_validate(
        {
            "provider": {"id": SCENE.provider, "name": "Synthetic Earth Search"},
            "provider_asset_id": SCENE.item,
            "provider_asset_version": None,
            "collection": {"id": SCENE.collection, "title": "Synthetic Sentinel-2"},
            "acquisition": {
                "start": "2026-01-12T10:00:00Z",
                "end": "2026-01-12T10:00:00Z",
            },
            "platform": None,
            "instruments": [],
            "product_type": None,
            "processing_level": None,
            "footprint": _aoi(),
            "bbox": [77.5, 12.9, 77.51, 12.91],
            "cloud_cover": None,
            "spatial_resolution": [],
            "bands": [],
            "polarizations": [],
            "preview": None,
            "license": None,
            "asset_access": {
                "state": "provider_accessible",
                "method": "backend_mediated",
                "reason": None,
            },
            "provenance": {
                "adapter": "synthetic-vqa-fixture",
                "adapter_version": "1.0",
                "retrieved_at": "2026-01-12T11:00:00Z",
                "source_record_id": SCENE.item,
                "source_record_version": None,
                "metadata_digest_sha256": "a" * 64,
                "fields": [
                    {
                        "normalized_field": field,
                        "source": "provider_record",
                        "source_field": f"synthetic:{field}",
                        "method": None,
                    }
                    for field in fields
                ],
            },
            "unavailable_fields": [],
        }
    )


def _raster() -> CalibratedRasterInput:
    data = np.zeros((3, 16, 16), dtype=np.float32)
    data[0] = 0.20
    data[1] = 0.12
    data[2] = 0.06
    bands = tuple(
        BandCalibration(
            source=ResolvedImageryAssetIdentity(
                scene=SCENE,
                asset=role,
                asset_version="synthetic-v1",
            ),
            role=role,
            band_name=name,
            band_index=1,
            units="1",
            native_resolution_metres=10.0,
            source_nodata=0.0,
            provider_scale=0.0001,
            provider_offset=-0.1,
            applied_scale=0.0001,
            applied_offset=-0.1,
            method="metadata_scale_offset",
        )
        for role, name in zip(("red", "green", "blue"), ("B04", "B03", "B02"), strict=True)
    )
    return CalibratedRasterInput(
        scene=SCENE,
        data=data,
        inside_aoi_mask=np.ones((16, 16), dtype=bool),
        band_validity=np.ones((3, 16, 16), dtype=bool),
        crs="EPSG:32643",
        transform=(10.0, 0.0, 770000.0, 0.0, -10.0, 1450000.0),
        bounds=(770000.0, 1449840.0, 770160.0, 1450000.0),
        width=16,
        height=16,
        band_order=("red", "green", "blue"),
        bands=bands,
    )


def _quality(*, usable: bool = True, available: bool = True) -> OpticalQualityMasks:
    shape = (16, 16)
    false = np.zeros(shape, dtype=bool)
    usable_mask = np.ones(shape, dtype=bool) if usable else false
    return OpticalQualityMasks(
        quality_information="available" if available else "unavailable",
        unavailable_reason=None if available else "Synthetic QA is unavailable.",
        source_asset="scl" if available else None,
        processing_baseline="05.11" if available else None,
        catalogue_scene_cloud_percent=5.0 if available else None,
        scl_classes=np.full(shape, 4 if available else 255, dtype=np.uint8),
        class_labels={4: "vegetation", 255: "quality_unavailable"},
        outside_aoi=false,
        missing_or_invalid=false,
        clouds_or_cirrus=false,
        cloud_shadows=false,
        cast_shadows=false,
        snow_or_ice=false,
        unknown_quality=false if available else np.ones(shape, dtype=bool),
        usable=usable_mask,
        excluded_any=~usable_mask,
        coverage=(),
    )


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[VqaCaptionRequest, bytes, InferenceParameters]] = []
        self.active = 0
        self.max_active = 0

    async def infer(
        self,
        request: VqaCaptionRequest,
        image_content: bytes,
        parameters: InferenceParameters,
    ) -> TransportInferenceResult:
        self.calls.append((request, image_content, parameters))
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0)
        self.active -= 1
        text = (
            "The chip shows a mixture of vegetation and built surfaces."
            if request.task == "image_captioning"
            else "Vegetated and built surfaces appear visible."
        )
        return TransportInferenceResult(
            response_id=f"resp-{request.task}",
            model_version=OPENAI_MODEL,
            availability="available",
            answer=text,
            reason=None,
            latency_ms=7.5,
        )

    async def aclose(self) -> None:
        return None


class SlowTransport(FakeTransport):
    async def infer(
        self,
        request: VqaCaptionRequest,
        image_content: bytes,
        parameters: InferenceParameters,
    ) -> TransportInferenceResult:
        await asyncio.sleep(0.05)
        return await super().infer(request, image_content, parameters)


def _chip(*, usable: bool = True, available: bool = True) -> Any:
    return build_model_chip(
        raster=_raster(),
        quality=_quality(usable=usable, available=available),
        request=_request(),
        catalogue_scene=_catalogue_scene(),
    )


def _inference_request(task: str, chip: Any, question: str | None = None) -> VqaCaptionRequest:
    return VqaCaptionRequest.model_validate(
        {
            "request_id": str(uuid4()),
            "task": task,
            "image_chip": chip.contract.model_dump(mode="json"),
            "question": question,
            "grounding": "not_requested",
            "max_answer_characters": 1000,
        }
    )


def test_7b_fake_transport_runs_vqa_and_caption_on_exact_scientific_chip() -> None:
    chip = _chip()
    transport = FakeTransport()
    service = SingleImageInferenceService(transport)
    vqa = _inference_request(
        "visual_question_answering", chip, "What broad surface patterns are visible?"
    )
    caption = _inference_request("image_captioning", chip)

    async def run() -> tuple[Any, Any]:
        return await service.answer_question(vqa, chip), await service.caption(caption, chip)

    vqa_result, caption_result = asyncio.run(run())

    assert vqa_result.availability == "available"
    assert caption_result.availability == "available"
    assert len(transport.calls) == 2
    assert all(call[1] == chip.content for call in transport.calls)
    assert all(
        call[0].image_chip.source_mode == "trusted_ephemeral_extraction" for call in transport.calls
    )
    assert vqa_result.phase6_quality.readiness.state == "ready"
    assert vqa_result.calibrated_confidence is None
    assert vqa_result.model.version == OPENAI_MODEL


def test_nonfinite_invalid_samples_are_deterministic_transparent_chip_pixels() -> None:
    raster = _raster()
    data = raster.data.copy()
    validity = raster.band_validity.copy()
    data[:, 0, 0] = np.nan
    validity[:, 0, 0] = False

    chip = build_model_chip(
        raster=replace(raster, data=data, band_validity=validity),
        quality=_quality(),
        request=_request(),
        catalogue_scene=_catalogue_scene(),
    )

    with Image.open(BytesIO(chip.content)) as image:
        assert image.convert("RGBA").getpixel((0, 0)) == (0, 0, 0, 0)


def test_quality_and_unsupported_measurement_fail_before_model_call() -> None:
    blocked_chip = _chip(usable=False)
    transport = FakeTransport()
    service = SingleImageInferenceService(transport)
    blocked = _inference_request(
        "visual_question_answering", blocked_chip, "What broad patterns are visible?"
    )
    measured_chip = _chip()
    measurement = _inference_request(
        "visual_question_answering", measured_chip, "What percentage of this AOI is vegetation?"
    )

    async def run() -> tuple[Any, Any]:
        return (
            await service.answer_question(blocked, blocked_chip),
            await service.answer_question(measurement, measured_chip),
        )

    blocked_result, measurement_result = asyncio.run(run())

    assert blocked_result.availability == "unavailable"
    assert blocked_result.phase6_quality.readiness.state == "not_ready"
    assert measurement_result.availability == "unavailable"
    assert transport.calls == []


def test_missing_qa_is_unresolved_and_never_assumed_clear() -> None:
    chip = _chip(available=False, usable=False)
    request = _inference_request("image_captioning", chip)
    transport = FakeTransport()
    result = asyncio.run(SingleImageInferenceService(transport).caption(request, chip))

    assert chip.contract.phase6_quality.readiness.state == "unresolved"
    assert result.availability == "unavailable"
    assert transport.calls == []


def test_concurrency_is_bounded_to_one() -> None:
    chip = _chip()
    transport = FakeTransport()
    service = SingleImageInferenceService(transport, max_concurrency=1)
    first = _inference_request("image_captioning", chip)
    second = _inference_request("image_captioning", chip)

    async def run() -> None:
        await asyncio.gather(service.caption(first, chip), service.caption(second, chip))

    asyncio.run(run())
    assert transport.max_active == 1


def test_execution_timeout_is_enforced() -> None:
    chip = _chip()
    request = _inference_request("image_captioning", chip)
    service = SingleImageInferenceService(SlowTransport(), timeout_seconds=0.01)

    with pytest.raises(InferenceError, match="time limit"):
        asyncio.run(service.caption(request, chip))


def test_openai_transport_uses_base64_image_structured_output_and_no_storage() -> None:
    chip = _chip()
    request = _inference_request("image_captioning", chip)
    observed: list[httpx2.Request] = []

    def handler(upstream: httpx2.Request) -> httpx2.Response:
        observed.append(upstream)
        payload = json.loads(upstream.content)
        image_url = payload["input"][0]["content"][1]["image_url"]
        assert upstream.url == OPENAI_RESPONSES_URL
        assert payload["model"] == OPENAI_MODEL
        assert payload["store"] is False
        assert payload["max_output_tokens"] == 300
        assert payload["text"]["format"]["strict"] is True
        assert image_url.startswith("data:image/png;base64,")
        assert base64.b64decode(image_url.split(",", 1)[1]) == chip.content
        return httpx2.Response(
            200,
            request=upstream,
            json={
                "id": "resp-real-shape-fixture",
                "model": OPENAI_MODEL,
                "status": "completed",
                "output_text": json.dumps(
                    {"availability": "available", "answer": "A bounded caption.", "reason": None}
                ),
            },
        )

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    transport = OpenAIResponsesTransport("synthetic-secret", timeout_seconds=60.0, client=client)
    parameters = InferenceParameters(
        prompt_version="satquery-single-image-v1",
        max_output_tokens=300,
        temperature=0.0,
        timeout_seconds=60.0,
    )
    result = asyncio.run(transport.infer(request, chip.content, parameters))
    asyncio.run(client.aclose())

    assert result.answer == "A bounded caption."
    assert len(observed) == 1
    assert observed[0].headers["authorization"] == "Bearer synthetic-secret"


def test_xai_transport_uses_actual_chip_and_nested_structured_response() -> None:
    chip = _chip()
    request = _inference_request("visual_question_answering", chip, "What is visible here?")

    def handler(upstream: httpx2.Request) -> httpx2.Response:
        payload = json.loads(upstream.content)
        assert upstream.url == XAI_RESPONSES_URL
        assert payload["model"] == XAI_MODEL
        assert payload["store"] is False
        assert payload["reasoning"] == {"effort": "none"}
        assert payload["text"]["format"]["strict"] is True
        assert chip.contract.scene.item in payload["input"][0]["content"][0]["text"]
        assert "Phase 6 readiness" in payload["input"][0]["content"][0]["text"]
        image_url = payload["input"][0]["content"][1]["image_url"]
        assert base64.b64decode(image_url.split(",", 1)[1]) == chip.content
        return httpx2.Response(
            200,
            request=upstream,
            json={
                "id": "resp-xai-shape-fixture",
                "model": XAI_MODEL,
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "availability": "available",
                                        "answer": "Vegetation is visible in the selected image.",
                                        "reason": None,
                                    }
                                ),
                            }
                        ],
                    }
                ],
            },
        )

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    transport = XAIResponsesTransport("synthetic-secret", timeout_seconds=60.0, client=client)
    service = SingleImageInferenceService(transport, provider="xai")
    result = asyncio.run(service.answer_question(request, chip))
    asyncio.run(client.aclose())
    assert result.answer == "Vegetation is visible in the selected image."
    assert result.model.provider == "xai"
    assert result.model.version == XAI_MODEL
    assert result.source_chip_id == chip.contract.chip_id
    assert result.evidence[0].source_scene == chip.contract.scene


@pytest.mark.parametrize(
    ("status", "error_code"),
    [
        (401, "MODEL_AUTH_INVALID"),
        (402, "MODEL_BILLING_REQUIRED"),
        (403, "MODEL_ACCESS_DENIED"),
        (404, "MODEL_NOT_AVAILABLE"),
    ],
)
def test_xai_transport_reports_safe_account_or_model_blocker(status: int, error_code: str) -> None:
    chip = _chip()
    request = _inference_request("image_captioning", chip)

    def handler(upstream: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, request=upstream, json={"error": "synthetic-private-detail"})

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    transport = XAIResponsesTransport("synthetic-secret", timeout_seconds=60.0, client=client)
    parameters = InferenceParameters(
        prompt_version="satquery-single-image-v1",
        max_output_tokens=300,
        temperature=0.0,
        timeout_seconds=60.0,
    )
    with pytest.raises(InferenceError) as captured:
        asyncio.run(transport.infer(request, chip.content, parameters))
    asyncio.run(client.aclose())
    assert captured.value.code == error_code
    assert "synthetic-private-detail" not in str(captured.value)


def test_chip_bytes_or_contract_cannot_be_substituted() -> None:
    chip = _chip()
    request = _inference_request("image_captioning", chip)
    tampered = replace(chip, content=chip.content + b"tampered")

    with pytest.raises(InferenceError, match="byte size changed"):
        asyncio.run(SingleImageInferenceService(FakeTransport()).caption(request, tampered))
