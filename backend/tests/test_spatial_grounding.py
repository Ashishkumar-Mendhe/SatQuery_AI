"""Tests for spatial grounding coordinate transformations and the known-answer geometry fixture."""

from __future__ import annotations

import pytest

from satquery.api.schemas.visual import CoordinateStatus, GroundedVisualRegion, ImageManifest
from satquery.services.spatial_grounding import (
    SpatialGroundingError,
    compute_evidence_overlap,
    normalize_provider_box,
    transform_box_to_wgs84,
)


def test_known_answer_geometry_fixture() -> None:
    """Validate spatial transformation against the exact known-answer specification.

    Specification:
    - Source raster: 1000 cols by 800 rows.
    - Projected CRS: EPSG:32644 (metre units).
    - Pixel-edge transform:
      X = 500000 + 10 * col
      Y = 2400000 - 10 * row
      [a=10.0, b=0.0, c=500000.0, d=0.0, e=-10.0, f=2400000.0]
    - Crop: col offset 200, row offset 100, width 400, height 200.
    - Resize crop to: 800 by 400 pixels.
    - Add 100 pixels top padding, 100 pixels bottom padding -> Submitted: 800 by 600 pixels.
    - Canonical predicted box: [0.25, 1/3, 0.75, 2/3].

    Expected before CRS conversion:
    - Source columns: 300 to 500.
    - Source rows: 150 to 250.
    - West / East: 503000 and 505000.
    - North / South: 2398500 and 2397500.
    """
    manifest = ImageManifest(
        manifest_id="mf-known-1",
        input_image_id="img-known-1",
        source_scene_id="S2-Known",
        source_asset_id="ast-known-1",
        content_hash="sha256:abc123known",
        submitted_width=800,
        submitted_height=600,
        content_rectangle=(0, 100, 800, 400),
        crs="EPSG:32644",
        affine_transform=[10.0, 0.0, 500000.0, 0.0, -10.0, 2400000.0],
        crop_window=(200, 100, 400, 200),
        resize_dimensions=(800, 400),
        padding=(0, 100, 0, 100),
    )

    canonical_box = [0.25, 1.0 / 3.0, 0.75, 2.0 / 3.0]

    grounded = transform_box_to_wgs84(canonical_box, manifest, observation_id="obs-1")

    assert isinstance(grounded, GroundedVisualRegion)
    assert grounded.clipping_status == CoordinateStatus.VALID
    assert grounded.projected_bbox is not None

    west, south, east, north = grounded.projected_bbox
    assert west == pytest.approx(503000.0, abs=1.0)
    assert east == pytest.approx(505000.0, abs=1.0)
    assert north == pytest.approx(2398500.0, abs=1.0)
    assert south == pytest.approx(2397500.0, abs=1.0)

    # Check WGS84 GeoJSON geometry
    assert grounded.wgs84_geometry is not None
    assert len(grounded.wgs84_geometry.coordinates[0]) == 5  # Closed ring
    assert grounded.bbox_wgs84 is not None
    min_lon, min_lat, max_lon, max_lat = grounded.bbox_wgs84
    # India UTM zone 44 coordinates should produce valid longitude (~78-84 deg E) and latitude (~20-22 deg N)
    assert 78.0 <= min_lon < max_lon <= 85.0
    assert 20.0 <= min_lat < max_lat <= 25.0


def test_normalize_provider_box_gemini() -> None:
    """Test Gemini format [ymin, xmin, ymax, xmax] in 0..1000 converted to canonical [xmin, ymin, xmax, ymax]."""
    raw_box = [200, 150, 600, 850]
    canonical = normalize_provider_box(raw_box, provider_convention="gemini")
    assert canonical == [0.15, 0.2, 0.85, 0.6]


def test_normalize_provider_box_rejections() -> None:
    """Test rejection of non-finite, reversed, or out of range coordinates."""
    # Out of range
    with pytest.raises(SpatialGroundingError):
        normalize_provider_box([1.5, 0.2, 0.8, 0.9], provider_convention="canonical")

    # Reversed X
    with pytest.raises(SpatialGroundingError):
        normalize_provider_box([0.8, 0.2, 0.3, 0.9], provider_convention="canonical")

    # Reversed Y
    with pytest.raises(SpatialGroundingError):
        normalize_provider_box([0.2, 0.9, 0.8, 0.3], provider_convention="canonical")


def test_padding_only_box_handling() -> None:
    """Test that a bounding box wholly inside padding returns INVALID_PADDING_ONLY."""
    manifest = ImageManifest(
        manifest_id="mf-pad-1",
        input_image_id="img-pad-1",
        source_scene_id="S2-Pad",
        source_asset_id="ast-pad-1",
        content_hash="sha256:pad123",
        submitted_width=800,
        submitted_height=600,
        content_rectangle=(0, 100, 800, 400),
        crs="EPSG:32644",
        affine_transform=[10.0, 0.0, 500000.0, 0.0, -10.0, 2400000.0],
        padding=(0, 100, 0, 100),
    )

    # Box in top 50 pixels (0..50 out of 600 height) -> inside top padding (0..100)
    box_in_top_padding = [0.1, 0.01, 0.9, 0.08]
    grounded = transform_box_to_wgs84(box_in_top_padding, manifest)

    assert grounded.clipping_status == CoordinateStatus.INVALID_PADDING_ONLY
    assert grounded.wgs84_geometry is None


def test_partial_padding_clamping() -> None:
    """Test that a box crossing the padding border is clamped and marked PARTIAL_CLAMPED."""
    manifest = ImageManifest(
        manifest_id="mf-clamp-1",
        input_image_id="img-clamp-1",
        source_scene_id="S2-Clamp",
        source_asset_id="ast-clamp-1",
        content_hash="sha256:clamp123",
        submitted_width=800,
        submitted_height=600,
        content_rectangle=(0, 100, 800, 400),
        crs="EPSG:32644",
        affine_transform=[10.0, 0.0, 500000.0, 0.0, -10.0, 2400000.0],
        padding=(0, 100, 0, 100),
    )

    # Box starting at y=50px (inside top padding) and ending at y=300px (inside content)
    crossing_box = [0.2, 50.0 / 600.0, 0.8, 300.0 / 600.0]
    grounded = transform_box_to_wgs84(crossing_box, manifest)

    assert grounded.clipping_status == CoordinateStatus.PARTIAL_CLAMPED
    assert grounded.wgs84_geometry is not None
    assert len(grounded.limitations) > 0


def test_non_georeferenced_image_handling() -> None:
    """Test that an image without CRS or affine transform returns image-only grounding."""
    manifest = ImageManifest(
        manifest_id="mf-nongeo-1",
        input_image_id="img-nongeo-1",
        source_scene_id="Upload-1",
        source_asset_id="ast-upload-1",
        content_hash="sha256:upload123",
        submitted_width=500,
        submitted_height=500,
        content_rectangle=(0, 0, 500, 500),
        crs=None,
        affine_transform=None,
    )

    grounded = transform_box_to_wgs84([0.1, 0.1, 0.5, 0.5], manifest)
    assert grounded.wgs84_geometry is None
    assert "lacks geospatial georeferencing" in grounded.limitations[0]


def test_compute_evidence_overlap() -> None:
    """Test geometric overlap calculation with existing change evidence regions."""
    manifest = ImageManifest(
        manifest_id="mf-ov-1",
        input_image_id="img-ov-1",
        source_scene_id="S2-Ov",
        source_asset_id="ast-ov-1",
        content_hash="sha256:ov123",
        submitted_width=400,
        submitted_height=400,
        content_rectangle=(0, 0, 400, 400),
        crs="EPSG:32644",
        affine_transform=[10.0, 0.0, 500000.0, 0.0, -10.0, 2400000.0],
    )

    grounded = transform_box_to_wgs84([0.2, 0.2, 0.6, 0.6], manifest)
    assert grounded.wgs84_geometry is not None

    evidence_regions = [
        {
            "id": "chg-reg-1",
            "geometry": grounded.wgs84_geometry.model_dump(),
        }
    ]

    matched_ids, overlap_km2 = compute_evidence_overlap(grounded, evidence_regions)
    assert "chg-reg-1" in matched_ids
    assert overlap_km2 is not None and overlap_km2 > 0.0
