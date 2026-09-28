from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from satquery.api.schemas.vqa import ModelAnswer, VqaCaptionRequest

DIGEST = "a" * 64
CHIP_ID = "00000000-0000-4000-8000-000000000701"
JOB_ID = "00000000-0000-4000-8000-000000000702"
REQUEST_ID = "00000000-0000-4000-8000-000000000703"


def scene() -> dict[str, str]:
    return {
        "provider": "earth-search",
        "collection": "sentinel-2-c1-l2a",
        "item": "synthetic-scene-a",
    }


def artifact(identifier: str, kind: str, media_type: str) -> dict[str, Any]:
    return {
        "artifact_id": identifier,
        "kind": kind,
        "media_type": media_type,
        "checksum_sha256": DIGEST,
        "byte_size": 128,
        "access": {"state": "available", "reason": None},
    }


def quality_context() -> dict[str, Any]:
    return {
        "preparation_job_id": JOB_ID,
        "provenance_state": "committed_manifest",
        "provenance_manifest": artifact(
            "00000000-0000-4000-8000-000000000704",
            "provenance_manifest",
            "application/json",
        ),
        "readiness": {
            "intended_task": "optical_single_scene",
            "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
            "scenes": [scene()],
            "state": "not_ready",
            "quality_check_ids": ["usable-coverage"],
            "unresolved_check_ids": [],
            "explanation": "Synthetic chip intentionally retains a failed Phase 6 gate.",
        },
        "quality_checks": [
            {
                "check_id": "usable-coverage",
                "scope": "prepared_scene",
                "metric": "usable-pixel-fraction",
                "measured_value": 0.4,
                "units": "fraction",
                "threshold": {"operator": "gte", "value": 0.8, "units": "fraction"},
                "outcome": "failed",
                "explanation": "Synthetic low usable coverage.",
            }
        ],
    }


def request_value(*, task: str = "visual_question_answering") -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "request_id": REQUEST_ID,
        "task": task,
        "image_chip": {
            "schema_version": "1.0",
            "chip_id": CHIP_ID,
            "scene": scene(),
            "acquired_at": "2026-09-20T08:00:00Z",
            "source_mode": "authorized_prepared_artifact",
            "source_raster": artifact(
                "00000000-0000-4000-8000-000000000705",
                "prepared_raster",
                "image/tiff",
            ),
            "source_assets": [
                {"scene": scene(), "asset": "red", "asset_version": "synthetic-v1"},
                {"scene": scene(), "asset": "green", "asset_version": "synthetic-v1"},
                {"scene": scene(), "asset": "blue", "asset_version": "synthetic-v1"},
            ],
            "checksum_sha256": DIGEST,
            "media_type": "image/png",
            "byte_size": 1024,
            "width": 64,
            "height": 64,
            "band_order": ["red", "green", "blue"],
            "rendering": {
                "method": "fixed_linear",
                "source_units": "surface-reflectance",
                "input_range": [0.0, 0.3],
                "output_data_type": "uint8",
                "output_range": [0, 255],
                "out_of_range_behavior": "clip_visual_representation_only",
                "per_image_normalization": False,
                "invalid_pixels": "transparent",
            },
            "pixel_to_map": {
                "crs": "EPSG:32643",
                "affine": [10.0, 0.0, 770000.0, 0.0, -10.0, 1450000.0],
                "pixel_interpretation": "area",
                "pixel_origin": "upper_left",
                "x_axis": "column_increases_right",
                "y_axis": "row_increases_down",
                "coordinate_reference": "pixel_edges",
            },
            "footprint_wgs84": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [77.5, 12.9],
                        [77.6, 12.9],
                        [77.6, 13.0],
                        [77.5, 13.0],
                        [77.5, 12.9],
                    ]
                ],
            },
            "phase6_quality": quality_context(),
        },
        "question": "What broad land-cover patterns are visible?"
        if task == "visual_question_answering"
        else None,
        "grounding": "separate_optional",
        "max_answer_characters": 1000,
    }


def model_identity() -> dict[str, str]:
    return {
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "version": "gpt-4.1-mini-2025-04-14",
        "adapter_version": "satquery-vqa-openai-v1",
        "runtime": "hosted_api",
        "weights": "hosted_not_disclosed",
        "licence_basis": "Hosted service; deployment is governed by provider service terms.",
        "execution_hardware": "provider_managed_not_disclosed",
    }


def answer_value() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "request_id": REQUEST_ID,
        "task": "visual_question_answering",
        "source_chip_id": CHIP_ID,
        "availability": "unknown",
        "answer": None,
        "reason": "The image does not support a reliable answer to the question.",
        "model": model_identity(),
        "inference_parameters": {
            "prompt_version": "satquery-vqa-v1",
            "image_detail": "high",
            "max_output_tokens": 300,
            "temperature": 0.0,
            "timeout_seconds": 60.0,
            "store_provider_response": False,
        },
        "provider_response_id": "resp_synthetic_fixture",
        "latency_ms": 12.5,
        "evidence": [
            {
                "evidence_id": "00000000-0000-4000-8000-000000000706",
                "source_chip_id": CHIP_ID,
                "source_scene": scene(),
                "basis": "phase6_quality_check",
                "description": "The prepared input has low usable coverage.",
                "phase6_check_ids": ["usable-coverage"],
            }
        ],
        "grounding": {
            "availability": "unavailable",
            "method": "separate-geochat-grounding-candidate",
            "model": None,
            "geometries": [],
            "reason": "No separately validated grounding runtime is configured.",
        },
        "quality_warnings": [
            {
                "code": "phase6-usable-coverage",
                "severity": "blocking",
                "message": "Usable coverage failed the recorded Phase 6 threshold.",
                "corrective_action": "Select a clearer scene and prepare it again.",
                "phase6_check_id": "usable-coverage",
            }
        ],
        "phase6_quality": quality_context(),
        "calibrated_confidence": None,
    }


def test_7b_acceptance_contract_fixture_is_executable_and_retains_failed_quality() -> None:
    """7B will run this same boundary through its deterministic fake transport."""

    request = VqaCaptionRequest.model_validate(request_value())
    answer = ModelAnswer.model_validate(answer_value())

    assert request.image_chip.rendering.per_image_normalization is False
    assert request.image_chip.phase6_quality.readiness.state == "not_ready"
    assert answer.phase6_quality == request.image_chip.phase6_quality
    assert answer.availability == "unknown"
    assert answer.calibrated_confidence is None


def test_caption_forbids_question_and_vqa_requires_one() -> None:
    caption = VqaCaptionRequest.model_validate(request_value(task="image_captioning"))
    assert caption.question is None

    missing_question = request_value()
    missing_question["question"] = None
    with pytest.raises(ValidationError, match="requires a question"):
        VqaCaptionRequest.model_validate(missing_question)

    caption_with_question = request_value(task="image_captioning")
    caption_with_question["question"] = "This must not be accepted."
    with pytest.raises(ValidationError, match="does not accept a question"):
        VqaCaptionRequest.model_validate(caption_with_question)


def test_chip_rejects_urls_unavailable_sources_and_per_image_normalization() -> None:
    supplied_url = request_value()
    supplied_url["image_chip"]["source_url"] = "https://attacker.test/arbitrary.tif"
    with pytest.raises(ValidationError, match="Extra inputs"):
        VqaCaptionRequest.model_validate(supplied_url)

    unavailable = request_value()
    unavailable["image_chip"]["source_raster"]["access"] = {
        "state": "denied",
        "reason": "Synthetic access denial.",
    }
    with pytest.raises(ValidationError, match="authorized and available"):
        VqaCaptionRequest.model_validate(unavailable)

    normalized = request_value()
    normalized["image_chip"]["rendering"]["per_image_normalization"] = True
    with pytest.raises(ValidationError):
        VqaCaptionRequest.model_validate(normalized)


def test_answer_forbids_numeric_confidence_and_requires_explicit_unknown_reason() -> None:
    confidence = answer_value()
    confidence["calibrated_confidence"] = 0.91
    with pytest.raises(ValidationError):
        ModelAnswer.model_validate(confidence)

    invented_field = answer_value()
    invented_field["confidence"] = 91
    with pytest.raises(ValidationError, match="Extra inputs"):
        ModelAnswer.model_validate(invented_field)

    unexplained = answer_value()
    unexplained["reason"] = None
    with pytest.raises(ValidationError, match="require a reason"):
        ModelAnswer.model_validate(unexplained)

    available = answer_value()
    available.update(
        {
            "availability": "available",
            "answer": "A broad mix of built and vegetated surfaces may be visible.",
            "reason": None,
        }
    )
    assert ModelAnswer.model_validate(available).availability == "available"
    available["evidence"] = []
    with pytest.raises(ValidationError, match="image-specific evidence"):
        ModelAnswer.model_validate(available)


def test_grounding_declares_coordinate_space_and_rejects_wrong_chip_or_bounds() -> None:
    grounded = answer_value()
    grounded["grounding"] = {
        "availability": "available",
        "method": "synthetic-grounding-fixture",
        "model": model_identity(),
        "geometries": [
            {
                "coordinate_space": "image_pixel",
                "source_chip_id": CHIP_ID,
                "pixel_origin": "upper_left",
                "x_axis": "column_increases_right",
                "y_axis": "row_increases_down",
                "coordinate_reference": "pixel_edges",
                "image_width": 64,
                "image_height": 64,
                "x_min": 4.0,
                "y_min": 5.0,
                "x_max": 20.0,
                "y_max": 25.0,
            }
        ],
        "reason": None,
    }
    parsed = ModelAnswer.model_validate(grounded)
    assert parsed.grounding is not None
    assert parsed.grounding.geometries[0].coordinate_space == "image_pixel"

    outside = deepcopy(grounded)
    outside["grounding"]["geometries"][0]["x_max"] = 65.0
    with pytest.raises(ValidationError, match="exceed the chip"):
        ModelAnswer.model_validate(outside)

    wrong_chip = deepcopy(grounded)
    wrong_chip["grounding"]["geometries"][0]["source_chip_id"] = (
        "00000000-0000-4000-8000-000000000799"
    )
    with pytest.raises(ValidationError, match="answer source chip"):
        ModelAnswer.model_validate(wrong_chip)


def test_phase6_context_cannot_claim_ready_while_referenced_check_failed() -> None:
    contradictory = request_value()
    contradictory["image_chip"]["phase6_quality"]["readiness"]["state"] = "ready"
    with pytest.raises(ValidationError, match="ready tasks require"):
        VqaCaptionRequest.model_validate(contradictory)
