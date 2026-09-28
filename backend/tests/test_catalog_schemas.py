from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from satquery.api.schemas.catalog import CatalogueSearchRequest, CatalogueSearchResponse


def synthetic_polygon() -> dict[str, Any]:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [77.5, 12.9],
                [77.7, 12.9],
                [77.7, 13.05],
                [77.5, 13.05],
                [77.5, 12.9],
            ]
        ],
    }


def synthetic_request() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "provider": "synthetic-provider",
        "aoi": synthetic_polygon(),
        "acquisition": {
            "start": "2026-01-01T00:00:00+05:30",
            "end": "2026-01-31T23:59:59+05:30",
        },
        "collections": ["synthetic-optical-l2"],
        "cloud_cover": {
            "max_percent": 20,
            "source": "provider_reported",
            "include_unknown": False,
        },
        "limit": 25,
        "cursor": None,
        "sort": "acquired_desc",
    }


def synthetic_scene() -> dict[str, Any]:
    fields = [
        "provider_asset_id",
        "provider_asset_version",
        "collection.id",
        "acquisition.start",
        "acquisition.end",
        "platform",
        "instruments",
        "product_type",
        "processing_level",
        "footprint",
        "bbox",
        "cloud_cover",
        "spatial_resolution",
        "bands",
        "preview",
        "license",
        "asset_access",
    ]
    return {
        "provider": {"id": "synthetic-provider", "name": "Synthetic provider"},
        "provider_asset_id": "scene-synthetic-001",
        "provider_asset_version": "v1",
        "collection": {"id": "synthetic-optical-l2", "title": "Synthetic optical L2"},
        "acquisition": {
            "start": "2026-01-12T10:00:00Z",
            "end": "2026-01-12T10:05:00Z",
        },
        "platform": "SYNTHETIC-SAT-1",
        "instruments": ["SYNTHETIC-OPTICAL"],
        "product_type": "synthetic-surface-reflectance",
        "processing_level": "L2",
        "footprint": synthetic_polygon(),
        "bbox": [77.5, 12.9, 77.7, 13.05],
        "cloud_cover": {
            "percent": 12.5,
            "source_field": "synthetic:cloud_cover",
            "semantics": "Synthetic provider-reported scene cloud percentage.",
        },
        "spatial_resolution": [
            {
                "value": 10,
                "unit": "metre",
                "axis": "nominal",
                "source_field": "synthetic:gsd",
            }
        ],
        "bands": ["SYNTHETIC-RED", "SYNTHETIC-NIR"],
        "polarizations": [],
        "preview": {
            "purpose": "thumbnail",
            "access": "public",
            "href": "https://example.test/previews/scene-synthetic-001.png",
            "media_type": "image/png",
            "width": 512,
            "height": 512,
            "expires_at": None,
            "attribution": "Synthetic fixture; not provider imagery.",
        },
        "license": {
            "name": "Synthetic test license",
            "url": "https://example.test/license",
            "permits_analytical_use": None,
            "summary": "Illustrative only; no real data rights are represented.",
        },
        "asset_access": {
            "state": "metadata_only",
            "method": "none",
            "reason": "Synthetic catalogue metadata has no analytical pixels.",
        },
        "provenance": {
            "adapter": "synthetic-contract-fixture",
            "adapter_version": "1.0",
            "retrieved_at": "2026-01-12T11:00:00Z",
            "source_record_id": "scene-synthetic-001",
            "source_record_version": "v1",
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
        "unavailable_fields": [
            {
                "field": "polarizations",
                "availability": "unavailable",
                "reason": "Not applicable to this synthetic optical fixture.",
            }
        ],
    }


def synthetic_response() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "search_id": "00000000-0000-4000-8000-000000000004",
        "status": "succeeded",
        "query": synthetic_request(),
        "provider": {"id": "synthetic-provider", "name": "Synthetic provider"},
        "items": [synthetic_scene()],
        "returned_count": 1,
        "next_cursor": "opaque-synthetic-cursor",
        "searched_at": "2026-01-12T11:00:01Z",
        "attributions": ["Synthetic fixture; not real provider data."],
        "warnings": [],
    }


def test_catalogue_request_normalizes_time_and_preserves_filter_semantics() -> None:
    request = CatalogueSearchRequest.model_validate(synthetic_request())

    assert request.acquisition.start.isoformat() == "2025-12-31T18:30:00+00:00"
    assert request.cloud_cover is not None
    assert request.cloud_cover.source == "provider_reported"
    assert request.aoi.type == "Polygon"


def test_catalogue_request_accepts_a_bounded_multipolygon() -> None:
    value = synthetic_request()
    second_polygon = deepcopy(synthetic_polygon()["coordinates"])
    for position in second_polygon[0]:
        position[0] += 1
    value["aoi"] = {
        "type": "MultiPolygon",
        "coordinates": [synthetic_polygon()["coordinates"], second_polygon],
    }

    request = CatalogueSearchRequest.model_validate(value)

    assert request.aoi.type == "MultiPolygon"
    assert len(request.aoi.coordinates) == 2


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda value: value["acquisition"].update(
                {"start": "2026-02-01T00:00:00Z", "end": "2026-01-01T00:00:00Z"}
            ),
            "must not precede",
        ),
        (lambda value: value["acquisition"].update({"start": "2026-01-01T00:00:00"}), "UTC"),
        (lambda value: value.update({"collections": ["duplicate", "duplicate"]}), "unique"),
        (lambda value: value.update({"cursor": "bad\nvalue"}), "control"),
        (lambda value: value["cloud_cover"].update({"max_percent": 101}), "less than or equal"),
        (lambda value: value.update({"unexpected": True}), "Extra inputs"),
        (lambda value: value["cloud_cover"].update({"max_percent": "20"}), "valid number"),
    ],
)
def test_catalogue_request_rejects_invalid_filters(
    change: Any,
    message: str,
) -> None:
    value = synthetic_request()
    change(value)

    with pytest.raises(ValidationError, match=message):
        CatalogueSearchRequest.model_validate(value)


@pytest.mark.parametrize(
    "coordinates",
    [
        [[[0, 0], [1, 0], [1, 1], [0, 1]]],
        [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]],
        [[[170, 0], [-170, 0], [-170, 1], [170, 1], [170, 0]]],
        [[[0, 0], [181, 0], [1, 1], [0, 0]]],
    ],
)
def test_catalogue_request_rejects_invalid_synthetic_geometry(
    coordinates: list[Any],
) -> None:
    value = synthetic_request()
    value["aoi"] = {"type": "Polygon", "coordinates": coordinates}

    with pytest.raises(ValidationError):
        CatalogueSearchRequest.model_validate(value)


def test_catalogue_response_validates_normalized_metadata_and_access_boundaries() -> None:
    response = CatalogueSearchResponse.model_validate(synthetic_response())

    assert response.search_id == UUID("00000000-0000-4000-8000-000000000004")
    assert response.items[0].asset_access.state == "metadata_only"
    assert response.items[0].preview is not None
    assert response.items[0].preview.purpose == "thumbnail"
    assert response.items[0].license is not None
    assert response.items[0].license.permits_analytical_use is None


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda value: value.update({"returned_count": 2}), "returned_count"),
        (lambda value: value["provider"].update({"id": "other-provider"}), "must match"),
        (
            lambda value: value["items"][0]["asset_access"].update(
                {"state": "metadata_only", "method": "backend_mediated"}
            ),
            "method 'none'",
        ),
        (
            lambda value: value["items"][0]["preview"].update({"access": "backend_mediated"}),
            "must not expose",
        ),
        (
            lambda value: value["items"][0]["provenance"].update(
                {
                    "fields": [
                        item
                        for item in value["items"][0]["provenance"]["fields"]
                        if item["normalized_field"] != "provider_asset_id"
                    ]
                }
            ),
            "provenance is missing",
        ),
        (lambda value: value.update({"status": "partial"}), "require at least one warning"),
        (lambda value: value["items"][0].update({"bbox": [0, 0, 1, 1]}), "must match"),
    ],
)
def test_catalogue_response_rejects_inconsistent_or_misleading_metadata(
    change: Any,
    message: str,
) -> None:
    value = deepcopy(synthetic_response())
    change(value)

    with pytest.raises(ValidationError, match=message):
        CatalogueSearchResponse.model_validate(value)


def test_catalogue_contract_generates_closed_json_schemas() -> None:
    request_schema = CatalogueSearchRequest.model_json_schema()
    response_schema = CatalogueSearchResponse.model_json_schema()

    assert request_schema["additionalProperties"] is False
    assert response_schema["additionalProperties"] is False
    assert request_schema["properties"]["aoi"]["discriminator"]["propertyName"] == "type"
    assert response_schema["properties"]["items"]["maxItems"] == 100
