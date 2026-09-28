"""Spatial grounding engine for transforming image-space bounding boxes to georeferenced map coordinates."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from pyproj import Transformer

from satquery.api.schemas.analysis import AOIGeometry, GeometryType
from satquery.api.schemas.visual import (
    CoordinateStatus,
    GroundedVisualRegion,
    ImageManifest,
)
from satquery.services.aoi_validator import calculate_spherical_polygon_area_km2

logger = logging.getLogger(__name__)


class SpatialGroundingError(Exception):
    """Exception raised for spatial transformation or coordinate errors."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def normalize_provider_box(
    box: Sequence[float | int],
    provider_convention: str = "gemini",
) -> list[float]:
    """Convert native provider bounding box convention into canonical [xmin, ymin, xmax, ymax] in 0.0..1.0.

    Canonical convention:
    - [xmin, ymin, xmax, ymax]
    - Normalized range: 0.0 to 1.0
    - Origin: Top-left of submitted image
    - X increases rightward, Y increases downward
    - Continuous pixel edges
    """
    if len(box) != 4:
        raise SpatialGroundingError(
            "INVALID_BOX_LENGTH", f"Bounding box must contain exactly 4 numbers, got {len(box)}."
        )

    for val in box:
        if not isinstance(val, (int, float)) or val != val:  # NaN check
            raise SpatialGroundingError(
                "NON_FINITE_COORDINATE", "Bounding box contains non-finite numbers."
            )

    if provider_convention == "gemini":
        # Gemini provides [ymin, xmin, ymax, xmax] on a 0..1000 scale or 0.0..1.0 scale
        ymin_raw, xmin_raw, ymax_raw, xmax_raw = (
            float(box[0]),
            float(box[1]),
            float(box[2]),
            float(box[3]),
        )
        if any(v > 1.0 + 1e-3 for v in (ymin_raw, xmin_raw, ymax_raw, xmax_raw)):
            ymin = ymin_raw / 1000.0
            xmin = xmin_raw / 1000.0
            ymax = ymax_raw / 1000.0
            xmax = xmax_raw / 1000.0
        else:
            ymin, xmin, ymax, xmax = ymin_raw, xmin_raw, ymax_raw, xmax_raw
    elif provider_convention == "canonical":
        xmin, ymin, xmax, ymax = (
            float(box[0]),
            float(box[1]),
            float(box[2]),
            float(box[3]),
        )
    else:
        raise SpatialGroundingError(
            "UNSUPPORTED_CONVENTION", f"Unknown provider convention '{provider_convention}'."
        )

    # Numerical clamping tolerance for small edge overshoots
    eps = 1e-4
    xmin = max(0.0, min(1.0, xmin)) if abs(xmin) < eps or abs(xmin - 1.0) < eps else xmin
    ymin = max(0.0, min(1.0, ymin)) if abs(ymin) < eps or abs(ymin - 1.0) < eps else ymin
    xmax = max(0.0, min(1.0, xmax)) if abs(xmax) < eps or abs(xmax - 1.0) < eps else xmax
    ymax = max(0.0, min(1.0, ymax)) if abs(ymax) < eps or abs(ymax - 1.0) < eps else ymax

    if xmin < 0.0 or xmax > 1.0 or ymin < 0.0 or ymax > 1.0:
        raise SpatialGroundingError(
            "OUT_OF_RANGE_COORDINATES",
            f"Box coordinates [{xmin}, {ymin}, {xmax}, {ymax}] out of [0.0, 1.0] range.",
        )

    if xmin >= xmax:
        raise SpatialGroundingError(
            "REVERSED_OR_EMPTY_X", f"Invalid X coordinates: xmin ({xmin}) >= xmax ({xmax})."
        )
    if ymin >= ymax:
        raise SpatialGroundingError(
            "REVERSED_OR_EMPTY_Y", f"Invalid Y coordinates: ymin ({ymin}) >= ymax ({ymax})."
        )

    return [round(xmin, 6), round(ymin, 6), round(xmax, 6), round(ymax, 6)]


def transform_box_to_wgs84(
    canonical_box: list[float],
    manifest: ImageManifest,
    observation_id: str = "",
) -> GroundedVisualRegion:
    """Transform canonical image-space box [xmin, ymin, xmax, ymax] into georeferenced WGS84 polygon.

    Applies the complete inverse transformation chain:
    1. Denormalize to submitted image pixel coordinates.
    2. Undo outer padding and perform content boundary intersection check.
    3. Undo resize scaling from content dimensions to crop window.
    4. Undo crop window offset to obtain source raster grid coordinates.
    5. Apply pixel-edge affine transform to obtain projected metric coordinates.
    6. Reproject projected coordinates to WGS84 GeoJSON polygon.
    """
    region_id = f"gvr-{uuid4().hex[:8]}"
    obs_id = observation_id or f"obs-{uuid4().hex[:8]}"

    # Non-georeferenced image handling
    if not manifest.crs or not manifest.affine_transform:
        return GroundedVisualRegion(
            region_id=region_id,
            observation_id=obs_id,
            manifest_id=manifest.manifest_id,
            source_image_box=canonical_box,
            wgs84_geometry=None,
            bbox_wgs84=None,
            projected_bbox=None,
            transform_provenance="Non-georeferenced image (image-space only)",
            clipping_status=CoordinateStatus.VALID,
            limitations=[
                "Image lacks geospatial georeferencing metadata; map placement unavailable."
            ],
        )

    xmin, ymin, xmax, ymax = canonical_box
    w_sub = float(manifest.submitted_width)
    h_sub = float(manifest.submitted_height)

    # 1. Denormalize to submitted image pixel edges
    px_min = xmin * w_sub
    py_min = ymin * h_sub
    px_max = xmax * w_sub
    py_max = ymax * h_sub

    # 2. Undo padding
    pad_left, pad_top, _pad_right, _pad_bottom = (
        manifest.padding if manifest.padding else (0, 0, 0, 0)
    )
    cx_min = px_min - float(pad_left)
    cy_min = py_min - float(pad_top)
    cx_max = px_max - float(pad_left)
    cy_max = py_max - float(pad_top)

    w_content = float(manifest.content_rectangle[2])
    h_content = float(manifest.content_rectangle[3])

    # Check if box is wholly within padding
    if cx_max <= 0.0 or cx_min >= w_content or cy_max <= 0.0 or cy_min >= h_content:
        return GroundedVisualRegion(
            region_id=region_id,
            observation_id=obs_id,
            manifest_id=manifest.manifest_id,
            source_image_box=canonical_box,
            wgs84_geometry=None,
            bbox_wgs84=None,
            projected_bbox=None,
            transform_provenance="Box falls entirely within image padding border",
            clipping_status=CoordinateStatus.INVALID_PADDING_ONLY,
            limitations=["Bounding box is wholly located inside padding; no ground coverage."],
        )

    # Content clamping check
    clamped_cx_min = max(0.0, min(cx_min, w_content))
    clamped_cx_max = max(0.0, min(cx_max, w_content))
    clamped_cy_min = max(0.0, min(cy_min, h_content))
    clamped_cy_max = max(0.0, min(cy_max, h_content))

    clipping_status = CoordinateStatus.VALID
    if (
        clamped_cx_min != cx_min
        or clamped_cx_max != cx_max
        or clamped_cy_min != cy_min
        or clamped_cy_max != cy_max
    ):
        clipping_status = CoordinateStatus.PARTIAL_CLAMPED

    # 3. Undo resize scaling (from content rectangle to crop window)
    if manifest.crop_window:
        w_crop = float(manifest.crop_window[2])
        h_crop = float(manifest.crop_window[3])
    else:
        w_crop = w_content
        h_crop = h_content

    scale_x = w_crop / w_content
    scale_y = h_crop / h_content

    crop_x_min = clamped_cx_min * scale_x
    crop_x_max = clamped_cx_max * scale_x
    crop_y_min = clamped_cy_min * scale_y
    crop_y_max = clamped_cy_max * scale_y

    # 4. Undo crop window offset
    col_offset = float(manifest.crop_window[0]) if manifest.crop_window else 0.0
    row_offset = float(manifest.crop_window[1]) if manifest.crop_window else 0.0

    col_min = crop_x_min + col_offset
    col_max = crop_x_max + col_offset
    row_min = crop_y_min + row_offset
    row_max = crop_y_max + row_offset

    # 5. Affine Transform to Projected Metric Coordinates
    # X = a*col + b*row + c
    # Y = d*col + e*row + f
    a, b, c, d, e, f = manifest.affine_transform

    def apply_affine(col: float, row: float) -> tuple[float, float]:
        proj_x = a * col + b * row + c
        proj_y = d * col + e * row + f
        return proj_x, proj_y

    # 4 Corners in continuous pixel edge grid: TL, TR, BR, BL
    tl_x, tl_y = apply_affine(col_min, row_min)
    tr_x, tr_y = apply_affine(col_max, row_min)
    br_x, br_y = apply_affine(col_max, row_max)
    bl_x, bl_y = apply_affine(col_min, row_max)

    proj_west = min(tl_x, tr_x, br_x, bl_x)
    proj_east = max(tl_x, tr_x, br_x, bl_x)
    proj_south = min(tl_y, tr_y, br_y, bl_y)
    proj_north = max(tl_y, tr_y, br_y, bl_y)
    projected_bbox = (
        round(proj_west, 2),
        round(proj_south, 2),
        round(proj_east, 2),
        round(proj_north, 2),
    )

    # 6. Reproject Corners to WGS84 GeoJSON Polygon
    try:
        transformer = Transformer.from_crs(manifest.crs, "EPSG:4326", always_xy=True)
        lon_tl, lat_tl = transformer.transform(tl_x, tl_y)
        lon_tr, lat_tr = transformer.transform(tr_x, tr_y)
        lon_br, lat_br = transformer.transform(br_x, br_y)
        lon_bl, lat_bl = transformer.transform(bl_x, bl_y)

        coords = [
            [round(lon_tl, 7), round(lat_tl, 7)],
            [round(lon_tr, 7), round(lat_tr, 7)],
            [round(lon_br, 7), round(lat_br, 7)],
            [round(lon_bl, 7), round(lat_bl, 7)],
            [round(lon_tl, 7), round(lat_tl, 7)],  # Closed ring
        ]

        wgs_lons = [c[0] for c in coords]
        wgs_lats = [c[1] for c in coords]
        bbox_wgs84 = (
            min(wgs_lons),
            min(wgs_lats),
            max(wgs_lons),
            max(wgs_lats),
        )

        wgs84_geometry = AOIGeometry(
            type=GeometryType.POLYGON,
            coordinates=[coords],
            crs="EPSG:4326",
            bbox=bbox_wgs84,
        )
    except Exception as exc:
        logger.warning(f"Failed to transform coordinates from {manifest.crs} to WGS84: {exc}")
        return GroundedVisualRegion(
            region_id=region_id,
            observation_id=obs_id,
            manifest_id=manifest.manifest_id,
            source_image_box=canonical_box,
            wgs84_geometry=None,
            bbox_wgs84=None,
            projected_bbox=projected_bbox,
            transform_provenance=f"Affine applied, WGS84 reprojection failed: {exc}",
            clipping_status=CoordinateStatus.UNAVAILABLE,
            limitations=["Geographic transformation failed during CRS reprojection."],
        )

    provenance = (
        f"Transform chain: denorm [{w_sub}x{h_sub}] -> unpad {manifest.padding} "
        f"-> uncrop/unresize -> affine ({manifest.crs}) -> WGS84"
    )

    limitations: list[str] = []
    if clipping_status == CoordinateStatus.PARTIAL_CLAMPED:
        limitations.append(
            "Observation partially crossed the image padding border and was clamped to valid content."
        )

    return GroundedVisualRegion(
        region_id=region_id,
        observation_id=obs_id,
        manifest_id=manifest.manifest_id,
        source_image_box=canonical_box,
        wgs84_geometry=wgs84_geometry,
        bbox_wgs84=bbox_wgs84,
        projected_bbox=projected_bbox,
        transform_provenance=provenance,
        clipping_status=clipping_status,
        limitations=limitations,
    )


def compute_evidence_overlap(
    grounded_region: GroundedVisualRegion,
    evidence_regions: list[dict[str, Any]],
) -> tuple[list[str], float | None]:
    """Compute geometric overlap between a grounded visual region and computed evidence regions.

    Returns:
    - matched_evidence_ids: list of overlapping computed region IDs
    - overlap_area_km2: total intersected area in square kilometers
    """
    if not grounded_region.bbox_wgs84:
        return [], None

    p_min_lon, p_min_lat, p_max_lon, p_max_lat = grounded_region.bbox_wgs84
    matched_ids: list[str] = []
    total_overlap_km2 = 0.0

    for ev_reg in evidence_regions:
        reg_id = str(ev_reg.get("id") or "")
        geom_dict = ev_reg.get("geometry")
        bbox = ev_reg.get("bbox")

        # Extract bbox from geometry if not directly present
        if not bbox and geom_dict and "coordinates" in geom_dict:
            coords = geom_dict["coordinates"]
            if coords and isinstance(coords[0], list):
                ring = coords[0]
                lons = [float(pt[0]) for pt in ring]
                lats = [float(pt[1]) for pt in ring]
                if lons and lats:
                    bbox = (min(lons), min(lats), max(lons), max(lats))

        if not bbox:
            continue

        e_min_lon, e_min_lat, e_max_lon, e_max_lat = bbox

        # Compute intersection box
        inter_min_lon = max(p_min_lon, e_min_lon)
        inter_min_lat = max(p_min_lat, e_min_lat)
        inter_max_lon = min(p_max_lon, e_max_lon)
        inter_max_lat = min(p_max_lat, e_max_lat)

        if inter_min_lon < inter_max_lon and inter_min_lat < inter_max_lat:
            matched_ids.append(reg_id)
            inter_poly = [
                [inter_min_lon, inter_min_lat],
                [inter_max_lon, inter_min_lat],
                [inter_max_lon, inter_max_lat],
                [inter_min_lon, inter_max_lat],
                [inter_min_lon, inter_min_lat],
            ]
            area = calculate_spherical_polygon_area_km2(inter_poly)
            total_overlap_km2 += area

    return matched_ids, round(total_overlap_km2, 4) if total_overlap_km2 > 0 else None
