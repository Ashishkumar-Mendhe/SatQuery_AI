"""Unit and API integration tests for Area of Interest (AOI) validation."""

from __future__ import annotations

from starlette.testclient import TestClient

from satquery.api.schemas.analysis import AOIGeometry, GeometryType
from satquery.api.schemas.aoi import (
    AoiValidationCode,
)
from satquery.services.aoi_validator import (
    calculate_spherical_polygon_area_km2,
    validate_aoi_geometry,
)

# Standard synthetic Bengaluru sample polygon (~110 km²)
VALID_POLYGON_COORDS = [
    [
        [77.55, 12.90],
        [77.65, 12.90],
        [77.65, 13.00],
        [77.55, 13.00],
        [77.55, 12.90],
    ]
]


def test_valid_polygon_validation() -> None:
    geom = AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=VALID_POLYGON_COORDS,
    )
    res = validate_aoi_geometry(geom, max_area_km2=10000.0)

    assert res.valid is True
    assert res.geometry_type == GeometryType.POLYGON
    assert res.coordinate_count == 5
    assert len(res.errors) == 0
    assert res.bbox == (77.55, 12.90, 77.65, 13.00)
    assert res.area_km2 is not None
    assert 100.0 < res.area_km2 < 140.0
    assert res.normalized_geometry is not None
    assert res.normalized_geometry.coordinates[0][0] == [77.55, 12.90]


def test_area_calculation_precision() -> None:
    # 1-degree square near equator (~111 km * 111 km ≈ 12300 km²)
    equator_poly = [
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
            [0.0, 0.0],
        ]
    ]
    area = calculate_spherical_polygon_area_km2(equator_poly[0])
    assert 12200.0 < area < 12500.0


def test_unclosed_ring_validation() -> None:
    # Model validator enforces closure on construction if type=Polygon,
    # but service handles unclosed rings safely.
    geom = AOIGeometry.model_construct(
        type=GeometryType.POLYGON,
        coordinates=[
            [
                [77.55, 12.90],
                [77.65, 12.90],
                [77.65, 13.00],
                [77.55, 13.00],
            ]
        ],
    )
    res = validate_aoi_geometry(geom)
    assert res.valid is False
    assert any(e.code == AoiValidationCode.POLYGON_NOT_CLOSED for e in res.errors)


def test_insufficient_vertices_validation() -> None:
    geom = AOIGeometry.model_construct(
        type=GeometryType.POLYGON,
        coordinates=[
            [
                [77.55, 12.90],
                [77.65, 12.90],
                [77.55, 12.90],
            ]
        ],
    )
    res = validate_aoi_geometry(geom)
    assert res.valid is False
    assert any(e.code == AoiValidationCode.INSUFFICIENT_VERTICES for e in res.errors)


def test_self_intersection_detection() -> None:
    # Bowtie / self-intersecting polygon
    bowtie_coords = [
        [
            [0.0, 0.0],
            [1.0, 1.0],
            [1.0, 0.0],
            [0.0, 1.0],
            [0.0, 0.0],
        ]
    ]
    geom = AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=bowtie_coords,
    )
    res = validate_aoi_geometry(geom)
    assert res.valid is False
    assert any(e.code == AoiValidationCode.AOI_SELF_INTERSECTION for e in res.errors)


def test_oversized_aoi_validation() -> None:
    # Huge polygon spanning several degrees
    huge_coords = [
        [
            [70.0, 10.0],
            [85.0, 10.0],
            [85.0, 25.0],
            [70.0, 25.0],
            [70.0, 10.0],
        ]
    ]
    geom = AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=huge_coords,
    )
    res = validate_aoi_geometry(geom, max_area_km2=10000.0)
    assert res.valid is False
    assert any(e.code == AoiValidationCode.AOI_TOO_LARGE for e in res.errors)


def test_small_aoi_resolution_warning() -> None:
    # Tiny ~500m x 500m box (~0.25 km², but let's test a 0.05 km² box)
    tiny_coords = [
        [
            [77.550, 12.900],
            [77.552, 12.900],
            [77.552, 12.902],
            [77.550, 12.902],
            [77.550, 12.900],
        ]
    ]
    geom = AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=tiny_coords,
    )
    res = validate_aoi_geometry(geom)
    assert res.valid is True
    assert any(w.severity.value == "warning" for w in res.warnings)


def test_aoi_validation_api_endpoint(ready_client: TestClient) -> None:
    payload = {
        "geometry": {
            "type": "Polygon",
            "coordinates": VALID_POLYGON_COORDS,
        },
        "client_area_km2": 120.5,
    }
    response = ready_client.post("/api/v1/aoi/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["geometry_type"] == "Polygon"
    assert data["bbox"] == [77.55, 12.90, 77.65, 13.00]
    assert data["area_km2"] > 100.0
    assert data["validation_version"] == "1.0"
