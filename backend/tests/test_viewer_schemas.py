from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from satquery.api.schemas.viewer import (
    ActiveImageryLayer,
    ComparisonSelection,
    ResolvedImageryAsset,
    SavedViewerState,
    TileMetadata,
    TimelineSelection,
)


def synthetic_scene(item: str, acquired_at: str) -> dict[str, Any]:
    return {
        "scene": {
            "provider": "synthetic-provider",
            "collection": "synthetic-optical-l2",
            "item": item,
        },
        "acquisition": {"start": acquired_at, "end": acquired_at},
    }


def synthetic_asset() -> dict[str, Any]:
    scene = synthetic_scene("scene-synthetic-001", "2026-01-12T10:00:00Z")
    return {
        "schema_version": "1.0",
        "identity": {
            "scene": scene["scene"],
            "asset": "synthetic-visual-asset",
            "asset_version": "v1",
        },
        "acquisition": scene["acquisition"],
        "media_type": "image/tiff",
        "bounds": [77.5, 12.9, 77.7, 13.05],
        "render_presets": [
            {
                "id": "true_color",
                "title": "Synthetic true color",
                "description": "Synthetic visualization preset; no real imagery is represented.",
                "mode": "rgb",
                "bands": ["synthetic-red", "synthetic-green", "synthetic-blue"],
                "purpose": "visualization",
            },
            {
                "id": "red_band",
                "title": "Synthetic red band",
                "description": "Synthetic single-band visualization.",
                "mode": "single_band",
                "bands": ["synthetic-red"],
                "purpose": "visualization",
            },
        ],
        "default_render_preset": "true_color",
        "catalogue_availability": {"state": "available", "reason": None},
        "asset_accessibility": {
            "state": "accessible",
            "method": "backend_mediated",
            "reason": None,
            "expires_at": "2026-01-12T11:30:00Z",
        },
        "analysis_readiness": {
            "state": "not_assessed",
            "reason": "Viewer resolution does not perform analytical validation.",
        },
        "attributions": ["Synthetic fixture; not provider imagery."],
        "resolved_at": "2026-01-12T11:00:00Z",
    }


def synthetic_tile() -> dict[str, Any]:
    asset = synthetic_asset()
    return {
        "schema_version": "1.0",
        "tile_set_id": "00000000-0000-4000-8000-000000000005",
        "asset": asset["identity"],
        "render_preset": "true_color",
        "bounds": asset["bounds"],
        "min_zoom": 4,
        "max_zoom": 14,
        "tile_size": 256,
        "media_type": "image/png",
        "url_template": "/api/v1/viewer/tiles/00000000-0000-4000-8000-000000000005/{z}/{x}/{y}",
        "expires_at": "2026-01-12T11:30:00Z",
        "attributions": asset["attributions"],
        "access": {"state": "available", "reason": None},
    }


def synthetic_display() -> dict[str, Any]:
    return {
        "visible": True,
        "opacity": 0.8,
        "brightness_min": 0.05,
        "brightness_max": 0.95,
        "contrast": 0.1,
        "saturation": -0.1,
    }


def test_resolved_asset_preserves_scene_identity_presets_and_distinct_capabilities() -> None:
    asset = ResolvedImageryAsset.model_validate(synthetic_asset())

    assert asset.identity.scene.item == "scene-synthetic-001"
    assert asset.default_render_preset == "true_color"
    assert asset.catalogue_availability.state == "available"
    assert asset.asset_accessibility.state == "accessible"
    assert asset.analysis_readiness.state == "not_assessed"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda value: value.update({"default_render_preset": "missing"}), "supported"),
        (lambda value: value["render_presets"][0].update({"bands": ["red"]}), "exactly 3"),
        (
            lambda value: value["asset_accessibility"].update(
                {"state": "unavailable", "method": "backend_mediated", "reason": "Synthetic."}
            ),
            "must not expose",
        ),
        (lambda value: value.update({"bounds": [77.7, 12.9, 77.5, 13.05]}), "ordered"),
        (lambda value: value.update({"unexpected": True}), "Extra inputs"),
    ],
)
def test_resolved_asset_rejects_inconsistent_contracts(change: Any, message: str) -> None:
    value = synthetic_asset()
    change(value)

    with pytest.raises(ValidationError, match=message):
        ResolvedImageryAsset.model_validate(value)


def test_tile_metadata_requires_mediated_expiring_access() -> None:
    tile = TileMetadata.model_validate(synthetic_tile())

    assert tile.url_template is not None
    assert tile.url_template.startswith("/api/v1/")
    assert tile.access.state == "available"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda value: value.update({"url_template": "https://provider.test/{z}/{x}/{y}"}),
            "relative",
        ),
        (lambda value: value.update({"expires_at": None}), "expires_at"),
        (lambda value: value.update({"min_zoom": 15, "max_zoom": 14}), "max_zoom"),
        (
            lambda value: value.update(
                {"access": {"state": "denied", "reason": "Synthetic denial."}}
            ),
            "must not expose",
        ),
    ],
)
def test_tile_metadata_rejects_unsafe_or_inconsistent_access(change: Any, message: str) -> None:
    value = synthetic_tile()
    change(value)

    with pytest.raises(ValidationError, match=message):
        TileMetadata.model_validate(value)


def test_active_layer_keeps_render_and_analysis_readiness_independent() -> None:
    asset = synthetic_asset()
    layer = ActiveImageryLayer.model_validate(
        {
            "layer_id": "primary_imagery",
            "asset": asset["identity"],
            "acquisition": asset["acquisition"],
            "render_preset": "true_color",
            "tile_set_id": None,
            "display": synthetic_display(),
            "catalogue_availability": {"state": "available", "reason": None},
            "asset_accessibility": asset["asset_accessibility"],
            "render_status": {"state": "failed", "reason": "Synthetic tile load failure."},
            "analysis_readiness": asset["analysis_readiness"],
        }
    )

    assert layer.asset_accessibility.state == "accessible"
    assert layer.render_status.state == "failed"
    assert layer.analysis_readiness.state == "not_assessed"


def test_comparison_requires_distinct_chronological_scenes() -> None:
    comparison = {
        "scene_a": synthetic_scene("scene-a", "2026-01-01T10:00:00Z"),
        "scene_b": synthetic_scene("scene-b", "2026-02-01T10:00:00Z"),
    }
    parsed = ComparisonSelection.model_validate(comparison)
    assert parsed.scene_a.acquisition.start < parsed.scene_b.acquisition.start

    reversed_value = deepcopy(comparison)
    reversed_value["scene_a"], reversed_value["scene_b"] = (
        reversed_value["scene_b"],
        reversed_value["scene_a"],
    )
    with pytest.raises(ValidationError, match="before"):
        ComparisonSelection.model_validate(reversed_value)


def test_timeline_requires_unique_ordered_scenes_and_selected_membership() -> None:
    timeline = {
        "scenes": [
            synthetic_scene("scene-a", "2026-01-01T10:00:00Z"),
            synthetic_scene("scene-b", "2026-02-01T10:00:00Z"),
        ],
        "selected_scene": synthetic_scene("scene-b", "2026-02-01T10:00:00Z")["scene"],
    }
    parsed = TimelineSelection.model_validate(timeline)
    assert parsed.selected_scene.item == "scene-b"

    timeline["selected_scene"] = synthetic_scene("missing", "2026-03-01T10:00:00Z")["scene"]
    with pytest.raises(ValidationError, match="must identify"):
        TimelineSelection.model_validate(timeline)


def test_saved_viewer_state_is_versioned_and_excludes_transient_tile_state() -> None:
    asset = synthetic_asset()
    value = {
        "version": 1,
        "saved_at": "2026-01-12T11:05:00Z",
        "aoi_reference": {
            "storage_key": "satquery.aoi-draft.v1",
            "geometry_fingerprint": '{"type":"Polygon"}',
        },
        "camera": {"center": [77.6, 13.0], "zoom": 8, "bearing": 0, "pitch": 0},
        "active_layer": {
            "layer_id": "primary_imagery",
            "asset": asset["identity"],
            "acquisition": asset["acquisition"],
            "render_preset": "true_color",
            "display": synthetic_display(),
        },
        "comparison_slots": None,
        "comparison": None,
        "timeline": None,
    }
    state = SavedViewerState.model_validate(value)
    assert state.version == 1

    value["tile_metadata"] = synthetic_tile()
    with pytest.raises(ValidationError, match="Extra inputs"):
        SavedViewerState.model_validate(value)


def test_saved_viewer_state_retains_one_comparison_slot_without_inventing_another() -> None:
    scene_a = synthetic_scene("scene-a", "2026-01-01T10:00:00Z")
    state = SavedViewerState.model_validate(
        {
            "version": 1,
            "saved_at": "2026-01-12T11:05:00Z",
            "aoi_reference": None,
            "camera": None,
            "active_layer": None,
            "comparison_slots": {"scene_a": scene_a, "scene_b": None},
            "comparison": None,
            "timeline": None,
        }
    )
    assert state.comparison_slots is not None
    assert state.comparison_slots.scene_b is None

    with pytest.raises(ValidationError, match="must be distinct"):
        SavedViewerState.model_validate(
            {
                **state.model_dump(mode="json"),
                "comparison_slots": {"scene_a": scene_a, "scene_b": scene_a},
            }
        )


def test_viewer_contracts_generate_closed_json_schemas() -> None:
    for contract in (
        ResolvedImageryAsset,
        TileMetadata,
        ActiveImageryLayer,
        ComparisonSelection,
        TimelineSelection,
        SavedViewerState,
    ):
        assert contract.model_json_schema()["additionalProperties"] is False
