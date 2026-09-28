"""Authoritative geometric validation service for Areas of Interest (AOI).

Validates coordinates, ring closure, self-intersection, bounding boxes,
and calculates geodesic polygon areas on the WGS84 sphere/ellipsoid.
"""

from __future__ import annotations

import math
from typing import Any

from satquery.api.schemas.analysis import AOIGeometry, BoundingBox, GeometryType
from satquery.api.schemas.aoi import (
    AOI_VALIDATION_SCHEMA_VERSION,
    AoiIssueSeverity,
    AoiValidationCode,
    AoiValidationIssue,
    AoiValidationResponse,
)

# Mean Earth radius for authalic sphere (WGS84 equal-area sphere) in km
EARTH_RADIUS_KM = 6371.0088
MAX_VERTICES_LIMIT = 500
MIN_MEANINGFUL_AREA_KM2 = 0.00001  # ~10 m²


def _to_radians(degrees: float) -> float:
    return degrees * math.pi / 180.0


def calculate_spherical_polygon_area_km2(ring: list[list[float]]) -> float:
    """Calculate the geodesic area of a closed spherical polygon ring in square kilometers."""
    if len(ring) < 4:
        return 0.0

    # Ensure we don't double-count closed endpoint in sum
    points = ring[:-1] if (ring[0][0] == ring[-1][0] and ring[0][1] == ring[-1][1]) else ring
    n = len(points)
    if n < 3:
        return 0.0

    total_rad = 0.0
    for i in range(n):
        prev_p = points[(i - 1) % n]
        next_p = points[(i + 1) % n]
        lon_diff = _to_radians(next_p[0] - prev_p[0])
        lat_rad = _to_radians(points[i][1])
        total_rad += lon_diff * math.sin(lat_rad)

    area = abs(total_rad) * 0.5 * (EARTH_RADIUS_KM**2)
    return area


def _signed_planar_area(ring: list[list[float]]) -> float:
    """Calculate planar signed area using Shoelace formula (positive for counter-clockwise)."""
    sum_area = 0.0
    for i in range(len(ring) - 1):
        p1 = ring[i]
        p2 = ring[i + 1]
        sum_area += (p1[0] * p2[1]) - (p2[0] * p1[1])
    return sum_area * 0.5


def _ccw(a: list[float], b: list[float], c: list[float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(p1: list[float], p2: list[float], p3: list[float], p4: list[float]) -> bool:
    """Check if line segment p1-p2 and p3-p4 strictly intersect or overlap."""
    d1 = _ccw(p3, p4, p1)
    d2 = _ccw(p3, p4, p2)
    d3 = _ccw(p1, p2, p3)
    d4 = _ccw(p1, p2, p4)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
        (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
    ):
        return True

    # Check collinear overlap
    def on_segment(p: list[float], a: list[float], b: list[float]) -> bool:
        return (
            min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
            and abs(_ccw(a, b, p)) < 1e-12
        )

    if on_segment(p1, p3, p4) and p1 != p3 and p1 != p4:
        return True
    if on_segment(p2, p3, p4) and p2 != p3 and p2 != p4:
        return True
    if on_segment(p3, p1, p2) and p3 != p1 and p3 != p2:
        return True
    if on_segment(p4, p1, p2) and p4 != p1 and p4 != p2:
        return True

    return False


def _has_self_intersection(ring: list[list[float]]) -> bool:
    """Detect self-intersections or collinear overlapping edges in a polygon ring."""
    n = len(ring) - 1
    for i in range(n):
        p1, p2 = ring[i], ring[i + 1]
        for j in range(i + 1, n):
            # Skip adjacent segments sharing a vertex
            if abs(i - j) <= 1 or (i == 0 and j == n - 1):
                continue
            p3, p4 = ring[j], ring[j + 1]
            if _segments_intersect(p1, p2, p3, p4):
                return True
    return False


def validate_aoi_geometry(
    geometry: AOIGeometry,
    max_area_km2: float = 10000.0,
    min_area_km2: float = MIN_MEANINGFUL_AREA_KM2,
) -> AoiValidationResponse:
    """Authoritatively validate an Area of Interest geometry."""
    errors: list[AoiValidationIssue] = []
    warnings: list[AoiValidationIssue] = []

    if geometry.type != GeometryType.POLYGON:
        errors.append(
            AoiValidationIssue(
                code=AoiValidationCode.UNSUPPORTED_GEOMETRY,
                message=(
                    f"Only Polygon geometries are supported for satellite analysis; "
                    f"received '{geometry.type}'."
                ),
                severity=AoiIssueSeverity.ERROR,
                field="type",
            )
        )
        return AoiValidationResponse(
            valid=False,
            geometry_type=geometry.type,
            errors=errors,
            warnings=warnings,
        )

    coords: Any = geometry.coordinates
    if not isinstance(coords, list) or len(coords) == 0:
        errors.append(
            AoiValidationIssue(
                code=AoiValidationCode.AOI_EMPTY,
                message="The submitted polygon geometry has no coordinate rings.",
                severity=AoiIssueSeverity.ERROR,
                field="coordinates",
            )
        )
        return AoiValidationResponse(
            valid=False,
            geometry_type=geometry.type,
            errors=errors,
            warnings=warnings,
        )

    if len(coords) > 1:
        errors.append(
            AoiValidationIssue(
                code=AoiValidationCode.POLYGON_HOLES_UNSUPPORTED,
                message=(
                    "Polygon interior holes are not supported in this analysis phase. "
                    "Submit a single exterior ring."
                ),
                severity=AoiIssueSeverity.ERROR,
                field="coordinates",
            )
        )

    raw_ring = coords[0]
    if not isinstance(raw_ring, list):
        errors.append(
            AoiValidationIssue(
                code=AoiValidationCode.INVALID_COORDINATE,
                message="Polygon exterior ring must be an array of positions.",
                severity=AoiIssueSeverity.ERROR,
                field="coordinates[0]",
            )
        )
        return AoiValidationResponse(
            valid=False,
            geometry_type=geometry.type,
            errors=errors,
            warnings=warnings,
        )

    if len(raw_ring) > MAX_VERTICES_LIMIT:
        errors.append(
            AoiValidationIssue(
                code=AoiValidationCode.TOO_MANY_COORDINATES,
                message=(
                    f"Polygon ring exceeds maximum allowed vertex limit "
                    f"({len(raw_ring)} > {MAX_VERTICES_LIMIT})."
                ),
                severity=AoiIssueSeverity.ERROR,
                field="coordinates[0]",
            )
        )

    if len(raw_ring) < 4:
        errors.append(
            AoiValidationIssue(
                code=AoiValidationCode.INSUFFICIENT_VERTICES,
                message=(
                    "A polygon ring must contain at least 4 positions "
                    "(3 distinct vertices plus closing point)."
                ),
                severity=AoiIssueSeverity.ERROR,
                field="coordinates[0]",
            )
        )
        return AoiValidationResponse(
            valid=False,
            geometry_type=geometry.type,
            coordinate_count=len(raw_ring),
            errors=errors,
            warnings=warnings,
        )

    parsed_ring: list[list[float]] = []
    for idx, pos in enumerate(raw_ring):
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            errors.append(
                AoiValidationIssue(
                    code=AoiValidationCode.INVALID_COORDINATE,
                    message=f"Vertex {idx + 1} must contain [longitude, latitude] pair.",
                    severity=AoiIssueSeverity.ERROR,
                    field=f"coordinates[0][{idx}]",
                )
            )
            continue
        lon, lat = float(pos[0]), float(pos[1])
        if not (math.isfinite(lon) and math.isfinite(lat)):
            errors.append(
                AoiValidationIssue(
                    code=AoiValidationCode.INVALID_COORDINATE,
                    message=f"Vertex {idx + 1} contains non-finite coordinates ({lon}, {lat}).",
                    severity=AoiIssueSeverity.ERROR,
                    field=f"coordinates[0][{idx}]",
                )
            )
        if not (-180.0 <= lon <= 180.0):
            errors.append(
                AoiValidationIssue(
                    code=AoiValidationCode.LONGITUDE_OUT_OF_RANGE,
                    message=(
                        f"Vertex {idx + 1} longitude {lon} is out of valid range [-180.0, 180.0]."
                    ),
                    severity=AoiIssueSeverity.ERROR,
                    field=f"coordinates[0][{idx}][0]",
                )
            )
        if not (-90.0 <= lat <= 90.0):
            errors.append(
                AoiValidationIssue(
                    code=AoiValidationCode.LATITUDE_OUT_OF_RANGE,
                    message=f"Vertex {idx + 1} latitude {lat} is out of valid range [-90.0, 90.0].",
                    severity=AoiIssueSeverity.ERROR,
                    field=f"coordinates[0][{idx}][1]",
                )
            )
        parsed_ring.append([lon, lat])

    if errors:
        return AoiValidationResponse(
            valid=False,
            geometry_type=geometry.type,
            coordinate_count=len(parsed_ring),
            errors=errors,
            warnings=warnings,
        )

    # Check ring closure
    if parsed_ring[0] != parsed_ring[-1]:
        errors.append(
            AoiValidationIssue(
                code=AoiValidationCode.POLYGON_NOT_CLOSED,
                message="Polygon ring must be closed with identical first and last coordinates.",
                severity=AoiIssueSeverity.ERROR,
                field="coordinates[0]",
            )
        )

    # Check distinct vertices
    distinct = {(p[0], p[1]) for p in parsed_ring[:-1]}
    if len(distinct) < 3:
        errors.append(
            AoiValidationIssue(
                code=AoiValidationCode.INSUFFICIENT_VERTICES,
                message="Polygon must contain at least 3 distinct non-collinear vertices.",
                severity=AoiIssueSeverity.ERROR,
                field="coordinates[0]",
            )
        )

    # Check antimeridian crossing
    for idx in range(len(parsed_ring) - 1):
        if abs(parsed_ring[idx][0] - parsed_ring[idx + 1][0]) > 180.0:
            errors.append(
                AoiValidationIssue(
                    code=AoiValidationCode.UNSUPPORTED_ANTIMERIDIAN_CROSSING,
                    message=(
                        "Antimeridian-crossing AOIs (>180° longitude span) are not supported. "
                        "Split the shape at ±180°."
                    ),
                    severity=AoiIssueSeverity.ERROR,
                    field=f"coordinates[0][{idx}]",
                )
            )
            break

    # Check self intersection
    if _has_self_intersection(parsed_ring):
        errors.append(
            AoiValidationIssue(
                code=AoiValidationCode.AOI_SELF_INTERSECTION,
                message=(
                    "The polygon edges intersect or overlap themselves. "
                    "Adjust vertices to form a simple polygon."
                ),
                severity=AoiIssueSeverity.ERROR,
                field="coordinates[0]",
            )
        )

    # Compute bounding box
    min_lon = min(p[0] for p in parsed_ring)
    min_lat = min(p[1] for p in parsed_ring)
    max_lon = max(p[0] for p in parsed_ring)
    max_lat = max(p[1] for p in parsed_ring)
    bbox: BoundingBox = (min_lon, min_lat, max_lon, max_lat)

    # Calculate geodesic area
    area_km2 = calculate_spherical_polygon_area_km2(parsed_ring)

    if area_km2 < min_area_km2:
        errors.append(
            AoiValidationIssue(
                code=AoiValidationCode.AOI_TOO_SMALL,
                message=(
                    f"Calculated AOI area ({area_km2:.6f} km²) is below the "
                    f"minimum threshold ({min_area_km2:.6f} km²)."
                ),
                severity=AoiIssueSeverity.ERROR,
            )
        )
    elif area_km2 > max_area_km2:
        errors.append(
            AoiValidationIssue(
                code=AoiValidationCode.AOI_TOO_LARGE,
                message=(
                    f"Calculated AOI area ({area_km2:.2f} km²) exceeds the "
                    f"maximum allowed limit ({max_area_km2:.2f} km²)."
                ),
                severity=AoiIssueSeverity.ERROR,
            )
        )

    # Check resolution limits (warning)
    if area_km2 < 0.1:
        warnings.append(
            AoiValidationIssue(
                code=AoiValidationCode.AOI_TOO_SMALL,
                message=(
                    "The selected AOI is smaller than 0.1 km²; 10m Sentinel-2 pixels "
                    "may provide low spatial granularity."
                ),
                severity=AoiIssueSeverity.WARNING,
            )
        )

    if errors:
        return AoiValidationResponse(
            valid=False,
            geometry_type=GeometryType.POLYGON,
            coordinate_count=len(parsed_ring),
            bbox=bbox,
            area_km2=round(area_km2, 6) if area_km2 > 0 else None,
            errors=errors,
            warnings=warnings,
            validation_version=AOI_VALIDATION_SCHEMA_VERSION,
        )

    # Ensure counter-clockwise winding for RFC 7946 GeoJSON compliance
    # Positive signed planar area is CCW; if negative (clockwise), reverse the closed ring
    normalized_ring = list(parsed_ring)
    if _signed_planar_area(parsed_ring) < 0:
        normalized_ring = list(reversed(parsed_ring))

    normalized_geom = AOIGeometry(
        type=GeometryType.POLYGON,
        coordinates=[normalized_ring],
        bbox=bbox,
        area_km2=round(area_km2, 6),
        crs="EPSG:4326",
    )

    return AoiValidationResponse(
        valid=True,
        normalized_geometry=normalized_geom,
        bbox=bbox,
        area_km2=round(area_km2, 6),
        geometry_type=GeometryType.POLYGON,
        coordinate_count=len(parsed_ring),
        warnings=warnings,
        errors=[],
        validation_version=AOI_VALIDATION_SCHEMA_VERSION,
    )
