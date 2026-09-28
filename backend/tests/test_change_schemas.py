from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from satquery.api.schemas.change import TwoDateChangeResult

DIGEST = "a" * 64
OTHER_DIGEST = "b" * 64


def scene(item: str) -> dict[str, str]:
    return {
        "provider": "earth-search",
        "collection": "sentinel-2-c1-l2a",
        "item": item,
    }


def result_value() -> dict[str, Any]:
    before = scene("scene-before")
    after = scene("scene-after")
    return {
        "schema_version": "1.1",
        "result_id": "00000000-0000-4000-8000-000000000801",
        "state": "complete",
        "sources": [
            {
                "temporal_role": "before",
                "scene": before,
                "acquired_at": "2026-01-01T05:30:00Z",
            },
            {
                "temporal_role": "after",
                "scene": after,
                "acquired_at": "2026-02-01T05:30:00Z",
            },
        ],
        "aoi": {
            "type": "Polygon",
            "coordinates": [
                [[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]],
                [
                    [77.52, 12.92],
                    [77.53, 12.92],
                    [77.53, 12.93],
                    [77.52, 12.93],
                    [77.52, 12.92],
                ],
            ],
        },
        "processing": {
            "preparation_job_id": "00000000-0000-4000-8000-000000000802",
            "preparation_profile": "sentinel-2-l2a-surface-reflectance-v1",
            "algorithm": "synthetic-absolute-difference",
            "algorithm_version": "fixture-v1",
            "required_band_roles": ["red", "nir"],
            "output_grid": {
                "crs": "EPSG:32643",
                "transform": [10.0, 0.0, 770000.0, 0.0, -10.0, 1450000.0],
                "width": 10,
                "height": 10,
                "resolution_metres": [10.0, 10.0],
                "bounds": [770000.0, 1449900.0, 770100.0, 1450000.0],
                "pixel_interpretation": "area",
            },
            "radiometric_harmonization": "none",
            "registration_input": "phase6_effective_pair",
            "unknown_pixel_policy": "outside_joint_usable_or_unresolved_quality",
            "parameters": [
                {
                    "name": "absolute-threshold",
                    "value": 0.08,
                    "units": "surface-reflectance",
                    "explanation": "Synthetic threshold used only to validate the contract.",
                }
            ],
            "parameters_digest_sha256": DIGEST,
        },
        "coverage": {
            "denominator": "inside_aoi",
            "aoi_pixel_count": 80,
            "joint_valid_pixel_count": 70,
            "valid_fraction_of_aoi": 0.875,
            "joint_valid_area_square_metres": 7000.0,
            "joint_usable_pixel_count": 60,
            "usable_fraction_of_aoi": 0.75,
            "joint_usable_area_square_metres": 6000.0,
            "pixel_area_square_metres": 100.0,
            "area_method": "projected_grid_cell_count",
            "area_method_explanation": (
                "Synthetic count of 10 metre projected cells whose centres are inside the AOI."
            ),
        },
        "classes": [
            {
                "classification": "unchanged",
                "raster_value": 0,
                "pixel_count": 40,
                "area_square_metres": 4000.0,
                "fraction_of_aoi": 0.5,
                "fraction_of_joint_valid": 40 / 70,
                "fraction_of_joint_usable": 2 / 3,
                "explanation": "Jointly usable pixels below the synthetic change threshold.",
            },
            {
                "classification": "changed",
                "raster_value": 1,
                "pixel_count": 20,
                "area_square_metres": 2000.0,
                "fraction_of_aoi": 0.25,
                "fraction_of_joint_valid": 20 / 70,
                "fraction_of_joint_usable": 1 / 3,
                "explanation": "Jointly usable pixels meeting the synthetic change threshold.",
            },
            {
                "classification": "unknown",
                "raster_value": 255,
                "pixel_count": 20,
                "area_square_metres": 2000.0,
                "fraction_of_aoi": 0.25,
                "fraction_of_joint_valid": None,
                "fraction_of_joint_usable": None,
                "explanation": "Inside-AOI pixels outside the joint usable mask.",
            },
        ],
        "quality_warnings": [
            {
                "warning_id": "seasonal-context",
                "state": "warning",
                "source_check_ids": ["pair-temporal-context"],
                "reason": "The dates are in different months.",
                "corrective_action": "Interpret spectral differences with seasonal context.",
            }
        ],
        "classification_artifact": {
            "artifact_id": "00000000-0000-4000-8000-000000000803",
            "kind": "change_classification",
            "media_type": "image/tiff",
            "checksum_sha256": OTHER_DIGEST,
            "byte_size": 4096,
            "access": {"state": "available", "reason": None},
        },
        "provenance": {
            "preparation_job_id": "00000000-0000-4000-8000-000000000802",
            "preparation_manifest_artifact_id": "00000000-0000-4000-8000-000000000804",
            "preparation_manifest_checksum_sha256": DIGEST,
            "prepared_scenes": [
                {
                    "scene": before,
                    "prepared_raster_artifact_id": "00000000-0000-4000-8000-000000000805",
                    "prepared_raster_checksum_sha256": DIGEST,
                    "validity_mask_checksum_sha256": OTHER_DIGEST,
                    "quality_mask_checksums_sha256": ["c" * 64],
                },
                {
                    "scene": after,
                    "prepared_raster_artifact_id": "00000000-0000-4000-8000-000000000806",
                    "prepared_raster_checksum_sha256": OTHER_DIGEST,
                    "validity_mask_checksum_sha256": DIGEST,
                    "quality_mask_checksums_sha256": ["d" * 64],
                },
            ],
            "parameters_digest_sha256": DIGEST,
            "software": [{"name": "satquery", "version": "synthetic-test"}],
            "started_at": "2026-09-24T10:00:00Z",
            "finished_at": "2026-09-24T10:00:01Z",
        },
    }


def test_two_date_change_result_preserves_sources_holes_measurements_and_provenance() -> None:
    result = TwoDateChangeResult.model_validate(result_value())

    assert [source.temporal_role for source in result.sources] == ["before", "after"]
    assert result.sources[0].acquired_at.isoformat() == "2026-01-01T05:30:00+00:00"
    assert result.aoi.type == "Polygon" and len(result.aoi.coordinates) == 2
    assert result.coverage.valid_fraction_of_aoi == 0.875
    assert result.coverage.usable_fraction_of_aoi == 0.75
    assert {item.classification for item in result.classes} == {
        "changed",
        "unchanged",
        "unknown",
    }
    assert result.provenance.parameters_digest_sha256 == result.processing.parameters_digest_sha256


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda value: value["sources"][0].update({"acquired_at": "2026-03-01T05:30:00Z"}),
            "before acquisition must precede",
        ),
        (
            lambda value: value["sources"][1].update({"temporal_role": "before"}),
            "exactly one before and one after",
        ),
        (
            lambda value: value["sources"][1]["scene"].update({"collection": "other"}),
            "one provider and collection",
        ),
    ],
)
def test_change_sources_are_distinct_ordered_and_compatible(change: Any, message: str) -> None:
    value = result_value()
    change(value)
    with pytest.raises(ValidationError, match=message):
        TwoDateChangeResult.model_validate(value)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda value: value["coverage"].update({"valid_fraction_of_aoi": 0.8}),
            "fraction must match",
        ),
        (
            lambda value: value["classes"][1].update({"pixel_count": 21}),
            "changed plus unchanged",
        ),
        (
            lambda value: value["classes"][0].update({"area_square_metres": 4001.0}),
            "class area must match",
        ),
        (
            lambda value: value["classes"][1].update({"fraction_of_joint_valid": 1 / 3}),
            "must use joint-valid pixels",
        ),
        (
            lambda value: value["classes"][2].update({"raster_value": 2}),
            "fixed meaning",
        ),
    ],
)
def test_change_measurements_cannot_contradict_counts_or_fixed_classes(
    change: Any, message: str
) -> None:
    value = result_value()
    change(value)
    with pytest.raises(ValidationError, match=message):
        TwoDateChangeResult.model_validate(value)


def test_unknown_quality_requires_a_limited_result() -> None:
    value = result_value()
    value["quality_warnings"][0]["state"] = "unknown"
    with pytest.raises(ValidationError, match="requires a limited"):
        TwoDateChangeResult.model_validate(value)

    value["state"] = "limited"
    assert TwoDateChangeResult.model_validate(value).state == "limited"


def test_change_result_rejects_unbound_provenance_and_wrong_artifact_kind() -> None:
    value = result_value()
    value["provenance"]["parameters_digest_sha256"] = OTHER_DIGEST
    with pytest.raises(ValidationError, match="parameters digest"):
        TwoDateChangeResult.model_validate(value)

    value = result_value()
    value["classification_artifact"]["kind"] = "prepared_raster"
    with pytest.raises(ValidationError, match="change_classification"):
        TwoDateChangeResult.model_validate(value)


@pytest.mark.parametrize("field", ["source_url", "filesystem_path", "confidence"])
def test_change_result_rejects_untrusted_locations_and_fabricated_confidence(field: str) -> None:
    value = result_value()
    value[field] = "https://example.test/raster.tif" if field == "source_url" else "not-allowed"
    with pytest.raises(ValidationError, match="Extra inputs"):
        TwoDateChangeResult.model_validate(value)


def test_zero_valid_coverage_remains_unknown_instead_of_unchanged() -> None:
    value = result_value()
    value["state"] = "limited"
    value["coverage"].update(
        {
            "joint_valid_pixel_count": 0,
            "valid_fraction_of_aoi": 0.0,
            "joint_valid_area_square_metres": 0.0,
            "joint_usable_pixel_count": 0,
            "usable_fraction_of_aoi": 0.0,
            "joint_usable_area_square_metres": 0.0,
        }
    )
    value["classes"][0].update(
        {
            "pixel_count": 0,
            "area_square_metres": 0.0,
            "fraction_of_aoi": 0.0,
            "fraction_of_joint_valid": None,
            "fraction_of_joint_usable": None,
        }
    )
    value["classes"][1].update(
        {
            "pixel_count": 0,
            "area_square_metres": 0.0,
            "fraction_of_aoi": 0.0,
            "fraction_of_joint_valid": None,
            "fraction_of_joint_usable": None,
        }
    )
    value["classes"][2].update(
        {
            "pixel_count": 80,
            "area_square_metres": 8000.0,
            "fraction_of_aoi": 1.0,
        }
    )

    result = TwoDateChangeResult.model_validate(value)
    assert (
        next(item for item in result.classes if item.classification == "unknown").pixel_count == 80
    )
