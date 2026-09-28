from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from satquery.api.schemas.processing import (
    OutputGrid,
    PreparationRequest,
    PreparationResult,
    ProcessingJobStatus,
    QualityCheck,
    SourceCalibration,
)

DIGEST = "a" * 64


def scene(item: str) -> dict[str, str]:
    return {
        "provider": "earth-search",
        "collection": "sentinel-2-c1-l2a",
        "item": item,
    }


def aoi() -> dict[str, Any]:
    return {
        "type": "Polygon",
        "coordinates": [[[77.5, 12.9], [77.7, 12.9], [77.7, 13.1], [77.5, 13.1], [77.5, 12.9]]],
    }


def request_value(*, pair: bool = False) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "scenes": [scene("scene-a"), scene("scene-b")] if pair else [scene("scene-a")],
        "aoi": aoi(),
        "required_bands": [
            {"role": "red", "common_name": "red"},
            {"role": "nir", "common_name": "nir"},
        ],
        "intended_task": "optical_pair" if pair else "optical_single_scene",
        "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
        "options": {
            "grid_policy": "common_utm",
            "target_resolution_metres": 10.0,
            "continuous_resampling": "bilinear",
            "mask_resampling": "nearest",
            "calibration": "source_metadata",
            "clip_to_aoi": True,
            "preserve_originals": True,
            "max_output_pixels": 1_000_000,
        },
    }


def grid_value() -> dict[str, Any]:
    return {
        "crs": "EPSG:32643",
        "transform": [10.0, 0.0, 770000.0, 0.0, -10.0, 1450000.0],
        "width": 100,
        "height": 200,
        "resolution_metres": [10.0, 10.0],
        "bounds": [770000.0, 1448000.0, 771000.0, 1450000.0],
        "pixel_interpretation": "area",
    }


def asset(item: str, band: str) -> dict[str, Any]:
    return {
        "scene": scene(item),
        "asset": f"{item}-{band}",
        "asset_version": "synthetic-v1",
    }


def artifact(identifier: str, kind: str, media_type: str = "image/tiff") -> dict[str, Any]:
    return {
        "artifact_id": identifier,
        "kind": kind,
        "media_type": media_type,
        "checksum_sha256": DIGEST,
        "byte_size": 1234,
        "access": {"state": "available", "reason": None},
    }


def provenance() -> dict[str, Any]:
    return {
        "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
        "request_digest_sha256": DIGEST,
        "source_inputs": [
            {
                "asset": asset("scene-a", "red"),
                "checksum_sha256": None,
                "checksum_unavailable_reason": "Synthetic remote source has no local checksum.",
            }
        ],
        "calibrations": [
            {
                "calibration_id": "red-calibration",
                "source": asset("scene-a", "red"),
                "band_role": "red",
                "status": "applied",
                "method": "metadata_scale_offset",
                "scale": 0.0001,
                "offset": -0.1,
                "input_units": "digital-number",
                "output_units": "surface-reflectance",
                "explanation": "Synthetic calibration fixture.",
            }
        ],
        "steps": [
            {
                "sequence": 1,
                "operation": "read",
                "method": "windowed-read",
                "parameters_digest_sha256": DIGEST,
            },
            {
                "sequence": 2,
                "operation": "calibrate",
                "method": "metadata-scale-offset",
                "parameters_digest_sha256": DIGEST,
            },
        ],
        "software": [{"name": "satquery", "version": "synthetic-test"}],
        "started_at": "2026-09-20T08:00:00Z",
        "finished_at": "2026-09-20T08:01:00Z",
    }


def prepared_raster() -> dict[str, Any]:
    return {
        "scene": scene("scene-a"),
        "artifact": artifact("00000000-0000-4000-8000-000000000601", "prepared_raster"),
        "grid": grid_value(),
        "bands": [
            {
                "role": "red",
                "source": asset("scene-a", "red"),
                "data_type": "float32",
                "units": "surface-reflectance",
                "calibration_id": "red-calibration",
            }
        ],
        "validity_mask": {
            "purpose": "validity",
            "artifact": artifact("00000000-0000-4000-8000-000000000602", "validity_mask"),
            "classes": [
                {"value": 0, "label": "invalid", "explanation": "Synthetic invalid pixel."},
                {"value": 1, "label": "valid", "explanation": "Synthetic valid pixel."},
            ],
        },
        "quality_masks": [
            {
                "purpose": "quality",
                "artifact": artifact("00000000-0000-4000-8000-000000000603", "quality_mask"),
                "classes": [
                    {"value": 0, "label": "clear", "explanation": "Synthetic clear pixel."},
                    {"value": 1, "label": "cloud", "explanation": "Synthetic cloud pixel."},
                ],
            }
        ],
        "provenance": provenance(),
    }


def quality_check(outcome: str = "failed") -> dict[str, Any]:
    return {
        "check_id": "valid-fraction",
        "scope": "prepared_scene",
        "metric": "valid-pixel-fraction",
        "measured_value": 0.75,
        "units": "fraction",
        "threshold": {"operator": "gte", "value": 0.9, "units": "fraction"},
        "outcome": outcome,
        "explanation": "Synthetic measured quality fixture.",
    }


def result_value() -> dict[str, Any]:
    raster = prepared_raster()
    return {
        "schema_version": "1.0",
        "job_id": "00000000-0000-4000-8000-000000000600",
        "request": request_value(),
        "processing": {"state": "succeeded", "explanation": "Synthetic processing completed."},
        "output_grid": grid_value(),
        "prepared_rasters": [raster],
        "quality_checks": [quality_check()],
        "readiness": {
            "intended_task": "optical_single_scene",
            "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
            "scenes": [scene("scene-a")],
            "state": "not_ready",
            "quality_check_ids": ["valid-fraction"],
            "unresolved_check_ids": [],
            "explanation": "Synthetic preparation succeeded but the quality threshold failed.",
        },
        "artifacts": [
            raster["artifact"],
            raster["validity_mask"]["artifact"],
            raster["quality_masks"][0]["artifact"],
        ],
    }


def test_preparation_request_reuses_stable_scenes_and_validated_aoi() -> None:
    parsed = PreparationRequest.model_validate(request_value())

    assert parsed.scenes[0].item == "scene-a"
    assert parsed.aoi.type == "Polygon"
    assert parsed.options.preserve_originals is True


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda value: value["scenes"].append(scene("scene-b")), "exactly 1"),
        (lambda value: value["scenes"][0].update({"collection": "other"}), "supports only"),
        (
            lambda value: value.update({"source_url": "https://example.test/source.tif"}),
            "Extra inputs",
        ),
        (
            lambda value: value.update(
                {"thumbnail_url": "https://example.test/display-preview.jpg"}
            ),
            "Extra inputs",
        ),
        (
            lambda value: value.update({"display_stretch": {"minimum": 0, "maximum": 255}}),
            "Extra inputs",
        ),
        (
            lambda value: value.update({"claimed_readiness": "ready"}),
            "Extra inputs",
        ),
        (
            lambda value: value["required_bands"].append(
                {"role": "duplicate-red", "common_name": "red"}
            ),
            "common names must be unique",
        ),
    ],
)
def test_preparation_request_rejects_unsupported_or_unstable_input(
    change: Any, message: str
) -> None:
    value = request_value()
    change(value)

    with pytest.raises(ValidationError, match=message):
        PreparationRequest.model_validate(value)


def test_pair_request_requires_two_distinct_supported_optical_scenes() -> None:
    parsed = PreparationRequest.model_validate(request_value(pair=True))
    assert len(parsed.scenes) == 2

    duplicate = request_value(pair=True)
    duplicate["scenes"][1] = deepcopy(duplicate["scenes"][0])
    with pytest.raises(ValidationError, match="distinct"):
        PreparationRequest.model_validate(duplicate)


def test_output_grid_requires_consistent_north_up_geometry() -> None:
    parsed = OutputGrid.model_validate(grid_value())
    assert parsed.width * parsed.height == 20_000

    inconsistent = grid_value()
    inconsistent["bounds"][2] += 10
    with pytest.raises(ValidationError, match="must match"):
        OutputGrid.model_validate(inconsistent)

    invalid_zone = grid_value()
    invalid_zone["crs"] = "EPSG:32699"
    with pytest.raises(ValidationError, match="String should match pattern"):
        OutputGrid.model_validate(invalid_zone)


def test_unknown_calibration_retains_unknown_coefficients() -> None:
    calibration = provenance()["calibrations"][0]
    calibration.update(
        {
            "status": "unavailable",
            "method": "unavailable",
            "scale": None,
            "offset": None,
            "output_units": None,
        }
    )
    parsed = SourceCalibration.model_validate(calibration)
    assert parsed.scale is None

    calibration["scale"] = 1.0
    with pytest.raises(ValidationError, match="unknown coefficients"):
        SourceCalibration.model_validate(calibration)


def test_quality_checks_require_measurement_evidence_or_explicit_unknown() -> None:
    passing = quality_check("passed")
    passing["measured_value"] = 0.95
    parsed = QualityCheck.model_validate(passing)
    assert parsed.measured_value == 0.95

    unresolved = quality_check("unresolved")
    unresolved.update({"measured_value": None, "units": None, "threshold": None})
    assert QualityCheck.model_validate(unresolved).measured_value is None

    missing = quality_check("passed")
    missing["measured_value"] = None
    with pytest.raises(ValidationError, match="measured value"):
        QualityCheck.model_validate(missing)

    inconsistent = quality_check("passed")
    with pytest.raises(ValidationError, match="must match"):
        QualityCheck.model_validate(inconsistent)


def test_successful_processing_can_be_unsuitable_for_the_task() -> None:
    result = PreparationResult.model_validate(result_value())

    assert result.processing.state == "succeeded"
    assert result.readiness.state == "not_ready"
    assert result.prepared_rasters[0].validity_mask.purpose == "validity"
    assert result.prepared_rasters[0].quality_masks[0].purpose == "quality"


def test_ready_result_cannot_hide_failed_or_unresolved_quality() -> None:
    value = result_value()
    value["readiness"]["state"] = "ready"
    with pytest.raises(ValidationError, match="every referenced quality check"):
        PreparationResult.model_validate(value)

    value = result_value()
    value["quality_checks"][0].update(
        {"outcome": "unresolved", "measured_value": None, "units": None, "threshold": None}
    )
    with pytest.raises(ValidationError, match="unresolved checks must match"):
        PreparationResult.model_validate(value)


def test_failed_processing_exposes_no_prepared_outputs_or_ready_claim() -> None:
    value = result_value()
    value["processing"] = {"state": "failed", "explanation": "Synthetic bounded failure."}
    value["output_grid"] = None
    value["prepared_rasters"] = []
    value["readiness"]["state"] = "ready"
    value["quality_checks"][0]["outcome"] = "passed"
    value["quality_checks"][0]["measured_value"] = 0.95
    with pytest.raises(ValidationError, match="cannot be task-ready"):
        PreparationResult.model_validate(value)


def test_artifact_references_are_opaque_and_reject_urls() -> None:
    value = result_value()
    value["artifacts"][0]["url"] = "https://object-store.test/signed"
    with pytest.raises(ValidationError, match="Extra inputs"):
        PreparationResult.model_validate(value)


def test_processing_job_status_requires_committed_success_artifacts() -> None:
    status = ProcessingJobStatus.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "00000000-0000-4000-8000-000000000600",
            "state": "succeeded",
            "submitted_at": "2026-09-20T07:59:00Z",
            "started_at": "2026-09-20T08:00:00Z",
            "finished_at": "2026-09-20T08:01:00Z",
            "attempt": 1,
            "progress": {"completed_units": 2, "total_units": 2, "units": "scenes"},
            "artifacts": [artifact("00000000-0000-4000-8000-000000000601", "prepared_raster")],
            "error_code": None,
            "safe_error_message": None,
        }
    )
    assert status.state == "succeeded"

    missing_artifact = status.model_dump(mode="json")
    missing_artifact["artifacts"] = []
    with pytest.raises(ValidationError, match="committed artifact"):
        ProcessingJobStatus.model_validate(missing_artifact)


def test_queued_job_can_be_cancelled_without_inventing_a_start_time() -> None:
    cancelled = ProcessingJobStatus.model_validate(
        {
            "schema_version": "1.0",
            "job_id": "00000000-0000-4000-8000-000000000604",
            "state": "cancelled",
            "submitted_at": "2026-09-20T07:59:00Z",
            "started_at": None,
            "finished_at": "2026-09-20T08:00:00Z",
            "attempt": 0,
            "progress": None,
            "artifacts": [],
            "error_code": None,
            "safe_error_message": None,
        }
    )
    assert cancelled.started_at is None
