from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any
from uuid import uuid4

from test_vqa_inference import _chip

from satquery.api.schemas.vqa import ReferringGroundingRequest
from satquery.inference import (
    GroundingError,
    RawGroundingCandidate,
    ReferringGroundingService,
    RuntimeGroundingResult,
    map_to_pixel,
)


class FakeGroundingRuntime:
    def __init__(self, candidates: tuple[RawGroundingCandidate, ...]) -> None:
        self.candidates = candidates
        self.calls: list[dict[str, Any]] = []

    def infer(self, **kwargs: Any) -> RuntimeGroundingResult:
        self.calls.append(kwargs)
        return RuntimeGroundingResult(
            candidates=self.candidates,
            model_input_width=800,
            model_input_height=960,
            pad_right=0,
            pad_bottom=0,
            latency_ms=12.5,
        )


class FailingGroundingRuntime(FakeGroundingRuntime):
    def infer(self, **kwargs: Any) -> RuntimeGroundingResult:
        raise GroundingError("GROUNDING_INFERENCE_FAILED", "Synthetic model failure.")


def _request(chip: Any, **overrides: Any) -> ReferringGroundingRequest:
    value: dict[str, Any] = {
        "request_id": str(uuid4()),
        "image_chip": chip.contract.model_dump(mode="json"),
        "referring_text": "the rectangular bright feature",
        "requested_geometry": "bounding_box",
        "max_candidates": 5,
        "box_threshold": 0.35,
        "text_threshold": 0.25,
    }
    value.update(overrides)
    return ReferringGroundingRequest.model_validate(value)


def test_selected_visual_prompt_box_clips_and_round_trips_to_map() -> None:
    chip = _chip()
    selected = {
        "source_chip_id": str(chip.contract.chip_id),
        "image_width": 16,
        "image_height": 16,
        "x_min": 2,
        "y_min": 3,
        "x_max": 12,
        "y_max": 15,
        "purpose": "visual_prompt_crop",
    }
    runtime = FakeGroundingRuntime(
        (RawGroundingCandidate("bright feature", 0.82, (-2.0, 1.0, 8.0, 20.0)),)
    )
    request = _request(chip, selected_region=selected)

    result = asyncio.run(ReferringGroundingService(runtime).locate(request, chip))

    assert result.status == "detected"
    assert result.selected_region == request.selected_region
    assert result.geometry_capability == "bounding_boxes_only_no_masks"
    candidate = result.candidates[0]
    assert candidate.visual_prompt_box.model_dump()["x_min"] == 0.0
    assert (
        candidate.image_chip_box.x_min,
        candidate.image_chip_box.y_min,
        candidate.image_chip_box.x_max,
        candidate.image_chip_box.y_max,
    ) == (2.0, 4.0, 10.0, 15.0)
    assert candidate.model_score == 0.82
    assert candidate.score_meaning == "uncalibrated_model_relevance"
    map_corner = candidate.map_footprint.rings[0][0]
    assert map_corner == (770020.0, 1449960.0)
    assert map_to_pixel(chip.contract, *map_corner) == (2.0, 4.0)
    assert runtime.calls[0]["selected_region"] == request.selected_region


def test_multiple_model_candidates_are_explicitly_ambiguous() -> None:
    chip = _chip()
    runtime = FakeGroundingRuntime(
        (
            RawGroundingCandidate("feature", 0.8, (1.0, 1.0, 4.0, 4.0)),
            RawGroundingCandidate("feature", 0.7, (8.0, 8.0, 12.0, 12.0)),
        )
    )
    result = asyncio.run(ReferringGroundingService(runtime).locate(_request(chip), chip))

    assert result.status == "ambiguous_detection"
    assert len(result.candidates) == 2


def test_no_detection_and_fully_invalid_box_are_explicit() -> None:
    chip = _chip()
    runtime = FakeGroundingRuntime(
        (RawGroundingCandidate("outside", 0.9, (-9.0, -8.0, -2.0, -1.0)),)
    )
    result = asyncio.run(ReferringGroundingService(runtime).locate(_request(chip), chip))

    assert result.status == "no_detection"
    assert result.candidates == []


def test_mask_or_polygon_is_unsupported_not_a_disguised_box() -> None:
    chip = _chip()
    runtime = FakeGroundingRuntime(())
    result = asyncio.run(
        ReferringGroundingService(runtime).locate(_request(chip, requested_geometry="mask"), chip)
    )

    assert result.status == "unsupported_geometry"
    assert "boxes, not polygons or masks" in (result.reason or "")
    assert runtime.calls == []


def test_quality_binding_and_runtime_failure_fail_closed() -> None:
    blocked_chip = _chip(usable=False)
    runtime = FakeGroundingRuntime(())
    blocked = asyncio.run(
        ReferringGroundingService(runtime).locate(_request(blocked_chip), blocked_chip)
    )
    assert blocked.status == "unavailable"
    assert runtime.calls == []

    ready_chip = _chip()
    failed = asyncio.run(
        ReferringGroundingService(FailingGroundingRuntime(())).locate(
            _request(ready_chip), ready_chip
        )
    )
    assert failed.status == "failed_inference"
    assert failed.candidates == []


def test_tampered_chip_is_not_grounded() -> None:
    chip = _chip()
    tampered = replace(chip, content=chip.content + b"tampered")
    runtime = FakeGroundingRuntime(())
    result = asyncio.run(ReferringGroundingService(runtime).locate(_request(chip), tampered))

    assert result.status == "unavailable"
    assert "byte size changed" in (result.reason or "")
    assert runtime.calls == []
