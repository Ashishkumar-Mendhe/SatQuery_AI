from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from satquery.api.schemas.scene_metadata import (
    SceneCombinationResponse,
    SceneMetadataResponse,
)


def footprint(*, with_hole: bool = False) -> dict[str, Any]:
    rings = [[[77.5, 12.9], [77.7, 12.9], [77.7, 13.1], [77.5, 13.1], [77.5, 12.9]]]
    if with_hole:
        rings.append([[77.55, 12.95], [77.55, 13.0], [77.6, 13.0], [77.6, 12.95], [77.55, 12.95]])
    return {"type": "Polygon", "coordinates": rings}


def source(*, provider: str, collection: str, item: str) -> dict[str, str]:
    return {"provider": provider, "collection": collection, "item": item}


def base_metadata(*, provider: str, collection: str, item: str) -> dict[str, Any]:
    return {
        "source": source(provider=provider, collection=collection, item=item),
        "source_version": "provider-version-1",
        "provider": {"id": provider, "name": "Synthetic contract provider"},
        "mission": "synthetic-mission",
        "acquisition": {
            "start": "2026-01-12T10:00:00+05:30",
            "end": "2026-01-12T10:05:00+05:30",
        },
        "footprint": footprint(with_hole=True),
        "native_resolution": {
            "x_metres": 10.0,
            "y_metres": 10.0,
            "source_field": "synthetic:resolution",
        },
        "crs": {
            "identifier": "EPSG:32643",
            "axis_units": "metre",
            "source_field": "synthetic:proj:epsg",
        },
        "processing_level": "L2",
        "product_maturity": "operational",
    }


def optical_response() -> dict[str, Any]:
    metadata = base_metadata(
        provider="earth-search",
        collection="sentinel-2-c1-l2a",
        item="SYNTHETIC_OPTICAL",
    )
    metadata.update(
        {
            "modality": "optical",
            "calibration": {
                "source_values": "uncalibrated",
                "method": "scale_offset",
                "scale": 0.0001,
                "offset": -0.1,
                "input_units": "digital-number",
                "output_units": "surface-reflectance",
                "explanation": "Synthetic provider metadata coefficients.",
            },
            "valid_data_mask": {
                "state": "available",
                "source_role": "scene-classification",
                "convention": "categorical_quality",
                "valid_values": [4, 5, 6],
                "explanation": "Synthetic vegetation, bare, and water classes are valid.",
            },
            "optical_bands": [
                {
                    "band_id": "B04",
                    "common_name": "red",
                    "native_resolution_metres": 10.0,
                    "units": "surface-reflectance",
                },
                {
                    "band_id": "B08",
                    "common_name": "nir",
                    "native_resolution_metres": 10.0,
                    "units": "surface-reflectance",
                },
            ],
        }
    )
    return {"schema_version": "1.0", "outcome": {"state": "available", "metadata": metadata}}


def sar_response() -> dict[str, Any]:
    metadata = base_metadata(
        provider="synthetic-sar-provider",
        collection="synthetic-sar-l2",
        item="SYNTHETIC_SAR",
    )
    metadata.update(
        {
            "modality": "sar",
            "mission": "synthetic-l-band-mission",
            "native_resolution": {
                "x_metres": 20.0,
                "y_metres": 20.0,
                "source_field": "synthetic:resolution",
            },
            "calibration": {
                "source_values": "uncalibrated",
                "method": "provider_algorithm",
                "algorithm": "synthetic-radiometric-calibration",
                "algorithm_version": "1",
                "input_units": "digital-number",
                "output_units": "sigma0-linear",
                "explanation": "Synthetic contract fixture; no SAR processing is implemented.",
            },
            "valid_data_mask": {
                "state": "available",
                "source_role": "valid-data-mask",
                "convention": "gdal_valid_nonzero",
                "valid_values": [],
                "explanation": "Non-zero means valid in this synthetic fixture.",
            },
            "polarizations": [
                {
                    "polarization": "VV",
                    "native_resolution_metres": 20.0,
                    "units": "sigma0-linear",
                },
                {
                    "polarization": "VH",
                    "native_resolution_metres": 20.0,
                    "units": "sigma0-linear",
                },
            ],
        }
    )
    return {"schema_version": "1.0", "outcome": {"state": "available", "metadata": metadata}}


def member(*, modality: str, item: str) -> dict[str, Any]:
    provider = "earth-search" if modality == "optical" else "synthetic-sar-provider"
    collection = "sentinel-2-c1-l2a" if modality == "optical" else "synthetic-sar-l2"
    return {
        "source": source(provider=provider, collection=collection, item=item),
        "modality": modality,
    }


def test_available_optical_metadata_preserves_holes_and_normalizes_time() -> None:
    response = SceneMetadataResponse.model_validate(optical_response())

    assert response.outcome.state == "available"
    metadata = response.outcome.metadata
    assert metadata.modality == "optical"
    assert metadata.acquisition.start.isoformat() == "2026-01-12T04:30:00+00:00"
    assert len(metadata.footprint.coordinates) == 2
    assert [band.common_name for band in metadata.optical_bands] == ["red", "nir"]
    assert metadata.calibration.method == "scale_offset"


def test_available_sar_metadata_retains_polarization_and_calibration_semantics() -> None:
    response = SceneMetadataResponse.model_validate(sar_response())

    assert response.outcome.state == "available"
    metadata = response.outcome.metadata
    assert metadata.modality == "sar"
    assert [item.polarization for item in metadata.polarizations] == ["VV", "VH"]
    assert metadata.calibration.method == "provider_algorithm"
    assert metadata.valid_data_mask.state == "available"
    assert metadata.valid_data_mask.convention == "gdal_valid_nonzero"


@pytest.mark.parametrize(
    ("value_factory", "change", "message"),
    [
        (
            optical_response,
            lambda value: value["outcome"]["metadata"].update(
                {
                    "polarizations": [
                        {"polarization": "VV", "native_resolution_metres": 10.0, "units": None}
                    ]
                }
            ),
            "Extra inputs",
        ),
        (
            sar_response,
            lambda value: value["outcome"]["metadata"].update(
                {
                    "optical_bands": [
                        {
                            "band_id": "B04",
                            "common_name": "red",
                            "native_resolution_metres": 10.0,
                            "units": None,
                        }
                    ]
                }
            ),
            "Extra inputs",
        ),
        (
            optical_response,
            lambda value: value["outcome"]["metadata"]["provider"].update(
                {"id": "different-provider"}
            ),
            "must match",
        ),
        (
            optical_response,
            lambda value: value["outcome"]["metadata"]["optical_bands"].append(
                deepcopy(value["outcome"]["metadata"]["optical_bands"][0])
            ),
            "must be unique",
        ),
        (
            optical_response,
            lambda value: value["outcome"]["metadata"]["calibration"].update(
                {"method": "provider_algorithm", "algorithm": "wrong"}
            ),
            "Extra inputs",
        ),
        (
            optical_response,
            lambda value: value["outcome"]["metadata"]["crs"].update(
                {"identifier": "C:\\private\\scene.tif"}
            ),
            "string_pattern_mismatch",
        ),
    ],
)
def test_available_metadata_rejects_cross_modality_or_unbound_fields(
    value_factory: Any, change: Any, message: str
) -> None:
    value = value_factory()
    change(value)

    with pytest.raises(ValidationError, match=message):
        SceneMetadataResponse.model_validate(value)


def test_unavailable_metadata_is_explicit_and_cannot_carry_a_record() -> None:
    value: dict[str, Any] = {
        "schema_version": "1.0",
        "outcome": {
            "state": "unavailable",
            "source": source(
                provider="synthetic-sar-provider",
                collection="synthetic-sar-l2",
                item="MISSING_SAR",
            ),
            "provider": {"id": "synthetic-sar-provider", "name": "Synthetic SAR provider"},
            "expected_modality": "sar",
            "reason_code": "metadata_incomplete",
            "missing_fields": ["calibration", "valid_data_mask"],
            "retryable": False,
            "reason": "The provider record lacks required scientific metadata.",
            "corrective_action": "Select a supported product with calibration and mask metadata.",
        },
    }

    response = SceneMetadataResponse.model_validate(value)
    assert response.outcome.state == "unavailable"
    assert response.outcome.missing_fields == ["calibration", "valid_data_mask"]

    value["outcome"]["metadata"] = optical_response()["outcome"]["metadata"]
    with pytest.raises(ValidationError, match="Extra inputs"):
        SceneMetadataResponse.model_validate(value)


@pytest.mark.parametrize(
    ("reason_code", "retryable"),
    [("transient_provider_failure", False), ("access_denied", True)],
)
def test_unavailable_metadata_rejects_false_retryability(reason_code: str, retryable: bool) -> None:
    value: dict[str, Any] = {
        "schema_version": "1.0",
        "outcome": {
            "state": "unavailable",
            "source": source(provider="synthetic", collection="sar", item="missing"),
            "provider": {"id": "synthetic", "name": "Synthetic"},
            "expected_modality": "sar",
            "reason_code": reason_code,
            "missing_fields": [],
            "retryable": retryable,
            "reason": "Synthetic failure.",
            "corrective_action": "Retry or select another source.",
        },
    }

    with pytest.raises(ValidationError, match="only transient"):
        SceneMetadataResponse.model_validate(value)


def test_unsupported_optical_sar_combination_is_typed_without_confidence() -> None:
    value: dict[str, Any] = {
        "schema_version": "1.0",
        "outcome": {
            "state": "unsupported",
            "combination": "optical_sar_pair",
            "members": [
                member(modality="optical", item="OPTICAL"),
                member(modality="sar", item="SAR"),
            ],
            "reason_code": "calibration_unavailable",
            "reason": "Comparable calibrated SAR evidence is unavailable.",
            "corrective_action": "Resolve a supported calibrated SAR product.",
        },
    }

    response = SceneCombinationResponse.model_validate(value)
    assert response.outcome.state == "unsupported"
    assert "confidence" not in response.model_dump()


def test_supported_pair_requires_distinct_sources_and_matching_modalities() -> None:
    value: dict[str, Any] = {
        "schema_version": "1.0",
        "outcome": {
            "state": "supported",
            "combination": "optical_pair",
            "members": [
                member(modality="optical", item="A"),
                member(modality="optical", item="B"),
            ],
            "policy_version": "synthetic-policy-v1",
            "explanation": "Synthetic contract fixture only.",
        },
    }
    response = SceneCombinationResponse.model_validate(value)
    assert response.outcome.state == "supported"

    value["outcome"]["members"][1] = deepcopy(value["outcome"]["members"][0])
    with pytest.raises(ValidationError, match="distinct"):
        SceneCombinationResponse.model_validate(value)

    value = deepcopy(value)
    value["outcome"]["members"][1] = member(modality="sar", item="SAR")
    with pytest.raises(ValidationError, match="modalities"):
        SceneCombinationResponse.model_validate(value)


def test_contract_rejects_urls_paths_and_extra_readiness_claims() -> None:
    value = sar_response()
    value["outcome"]["metadata"]["asset_url"] = "https://example.test/private.tif"
    value["outcome"]["metadata"]["filesystem_path"] = "C:\\private\\scene.tif"
    value["outcome"]["metadata"]["analysis_ready"] = True

    with pytest.raises(ValidationError, match="Extra inputs"):
        SceneMetadataResponse.model_validate(value)
