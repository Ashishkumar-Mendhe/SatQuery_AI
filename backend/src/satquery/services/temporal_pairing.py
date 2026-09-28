"""Authoritative temporal pairing and scene compatibility validation service.

Calculates metadata-based spatial overlap, temporal gap, optical and SAR compatibility,
scoring breakdown, and deterministic candidate pair recommendations.
"""

from __future__ import annotations

from datetime import UTC

from satquery.api.schemas.analysis import (
    AnalysisMode,
    AnalysisWarning,
    AOIGeometry,
    BoundingBox,
    GeometryType,
    SatelliteScene,
    SceneSelection,
    SensorType,
    WarningCode,
    WarningSeverity,
)
from satquery.api.schemas.temporal import (
    CompatibilityFactorScore,
    PairCompatibilityIssue,
    PairCompatibilityStatus,
    PairingPreferences,
    RecommendedPair,
    SpatialOverlapMetrics,
    TemporalPairValidationResult,
)
from satquery.services.aoi_validator import calculate_spherical_polygon_area_km2

# ---------------------------------------------------------------------------
# Geometric helpers for 2D footprint and bbox intersection
# ---------------------------------------------------------------------------


def _bbox_to_polygon_coords(bbox: BoundingBox) -> list[list[float]]:
    """Convert [minX, minY, maxX, maxY] into a closed GeoJSON ring."""
    min_x, min_y, max_x, max_y = bbox
    return [
        [min_x, min_y],
        [max_x, min_y],
        [max_x, max_y],
        [min_x, max_y],
        [min_x, min_y],
    ]


def _extract_exterior_ring(
    geometry: AOIGeometry | None, bbox: BoundingBox | None
) -> list[list[float]]:
    """Extract closed exterior ring coordinates from AOIGeometry or fallback to bbox."""
    if (
        geometry
        and geometry.type == GeometryType.POLYGON
        and isinstance(geometry.coordinates, list)
    ):
        if len(geometry.coordinates) > 0 and isinstance(geometry.coordinates[0], list):
            ring = geometry.coordinates[0]
            if len(ring) >= 4:
                return [[float(p[0]), float(p[1])] for p in ring]
    elif (
        geometry
        and geometry.type == GeometryType.MULTI_POLYGON
        and isinstance(geometry.coordinates, list)
    ):
        if len(geometry.coordinates) > 0 and isinstance(geometry.coordinates[0], list):
            poly = geometry.coordinates[0]
            if len(poly) > 0 and isinstance(poly[0], list):
                ring = poly[0]
                if len(ring) >= 4:
                    return [[float(p[0]), float(p[1])] for p in ring]

    if bbox:
        return _bbox_to_polygon_coords(bbox)
    return []


def _bbox_intersection(b1: BoundingBox, b2: BoundingBox) -> BoundingBox | None:
    """Calculate intersection of two bounding boxes [minX, minY, maxX, maxY]."""
    min_x = max(b1[0], b2[0])
    min_y = max(b1[1], b2[1])
    max_x = min(b1[2], b2[2])
    max_y = min(b1[3], b2[3])

    if min_x < max_x and min_y < max_y:
        return (min_x, min_y, max_x, max_y)
    return None


def _bbox_area_km2(bbox: BoundingBox) -> float:
    """Compute approximate spherical area of a bounding box in square kilometers."""
    coords = _bbox_to_polygon_coords(bbox)
    return calculate_spherical_polygon_area_km2(coords)


# Sutherland-Hodgman Polygon Clipping against Convex Polygon / Bounding Box
def _clip_polygon_against_edge(
    polygon: list[list[float]],
    p1: list[float],
    p2: list[float],
) -> list[list[float]]:
    """Clip polygon against directed infinite line from p1 to p2 (keeps points on left)."""
    if len(polygon) < 3:
        return []

    def is_inside(p: list[float]) -> bool:
        return (p2[0] - p1[0]) * (p[1] - p1[1]) - (p2[1] - p1[1]) * (p[0] - p1[0]) >= -1e-12

    def line_intersection(cp1: list[float], cp2: list[float]) -> list[float]:
        dc = [cp1[0] - cp2[0], cp1[1] - cp2[1]]
        dp = [p1[0] - p2[0], p1[1] - p2[1]]
        n1 = cp1[0] * cp2[1] - cp1[1] * cp2[0]
        n2 = p1[0] * p2[1] - p1[1] * p2[0]
        denom = dc[0] * dp[1] - dc[1] * dp[0]
        if abs(denom) < 1e-14:
            return cp2
        x = (n1 * dp[0] - n2 * dc[0]) / denom
        y = (n1 * dp[1] - n2 * dc[1]) / denom
        return [x, y]

    output_list: list[list[float]] = []
    points = (
        polygon[:-1]
        if (polygon[0][0] == polygon[-1][0] and polygon[0][1] == polygon[-1][1])
        else polygon
    )
    if len(points) == 0:
        return []

    s = points[-1]
    for e in points:
        if is_inside(e):
            if not is_inside(s):
                output_list.append(line_intersection(s, e))
            output_list.append(e)
        elif is_inside(s):
            output_list.append(line_intersection(s, e))
        s = e

    if len(output_list) > 0 and (
        output_list[0][0] != output_list[-1][0] or output_list[0][1] != output_list[-1][1]
    ):
        output_list.append([output_list[0][0], output_list[0][1]])

    return output_list


def _clip_polygon(
    subject_polygon: list[list[float]], clip_polygon: list[list[float]]
) -> list[list[float]]:
    """Clip subject polygon by clip polygon using Sutherland-Hodgman algorithm."""
    if len(subject_polygon) < 4 or len(clip_polygon) < 4:
        return []

    clip_points = (
        clip_polygon[:-1]
        if (clip_polygon[0][0] == clip_polygon[-1][0] and clip_polygon[0][1] == clip_polygon[-1][1])
        else clip_polygon
    )

    output = list(subject_polygon)
    for i in range(len(clip_points)):
        p1 = clip_points[i]
        p2 = clip_points[(i + 1) % len(clip_points)]
        output = _clip_polygon_against_edge(output, p1, p2)
        if len(output) < 4:
            return []

    return output


def calculate_spatial_overlap_metrics(
    aoi: AOIGeometry,
    before_scene: SatelliteScene,
    after_scene: SatelliteScene,
) -> SpatialOverlapMetrics:
    """Calculate geometric intersection and AOI coverage metrics for scene pair."""
    aoi_ring = _extract_exterior_ring(aoi, aoi.bbox)
    before_ring = _extract_exterior_ring(before_scene.geometry, before_scene.bbox)
    after_ring = _extract_exterior_ring(after_scene.geometry, after_scene.bbox)

    aoi_area = calculate_spherical_polygon_area_km2(aoi_ring)
    if aoi_area <= 0.0 and aoi.bbox:
        aoi_area = _bbox_area_km2(aoi.bbox)
    if aoi_area <= 0.0:
        aoi_area = 1.0  # Safe denominator fallback

    # Compute bounding box intersections
    shared_scenes_bbox = _bbox_intersection(before_scene.bbox, after_scene.bbox)
    if not shared_scenes_bbox:
        return SpatialOverlapMetrics(
            before_aoi_coverage_percent=0.0,
            after_aoi_coverage_percent=0.0,
            mutual_aoi_coverage_percent=0.0,
            scene_overlap_percent=0.0,
            shared_bbox=None,
        )

    # 1. Before intersection with AOI
    before_clip = _clip_polygon(aoi_ring, before_ring)
    before_inter_area = (
        calculate_spherical_polygon_area_km2(before_clip) if len(before_clip) >= 4 else 0.0
    )
    if before_inter_area <= 0.0:
        b_box_inter = _bbox_intersection(aoi.bbox or (0, 0, 0, 0), before_scene.bbox)
        if b_box_inter:
            before_inter_area = _bbox_area_km2(b_box_inter)

    # 2. After intersection with AOI
    after_clip = _clip_polygon(aoi_ring, after_ring)
    after_inter_area = (
        calculate_spherical_polygon_area_km2(after_clip) if len(after_clip) >= 4 else 0.0
    )
    if after_inter_area <= 0.0:
        a_box_inter = _bbox_intersection(aoi.bbox or (0, 0, 0, 0), after_scene.bbox)
        if a_box_inter:
            after_inter_area = _bbox_area_km2(a_box_inter)

    # 3. Mutual intersection (AOI ∩ Before ∩ After)
    mutual_clip = _clip_polygon(before_clip if len(before_clip) >= 4 else aoi_ring, after_ring)
    mutual_inter_area = (
        calculate_spherical_polygon_area_km2(mutual_clip) if len(mutual_clip) >= 4 else 0.0
    )
    if mutual_inter_area <= 0.0:
        m_box_inter = _bbox_intersection(aoi.bbox or (0, 0, 0, 0), shared_scenes_bbox)
        if m_box_inter:
            mutual_inter_area = _bbox_area_km2(m_box_inter)

    # 4. Scene-to-scene overlap percentage
    before_scene_area = _bbox_area_km2(before_scene.bbox)
    after_scene_area = _bbox_area_km2(after_scene.bbox)
    min_scene_area = max(0.0001, min(before_scene_area, after_scene_area))
    scenes_inter_area = _bbox_area_km2(shared_scenes_bbox)

    before_coverage = min(100.0, max(0.0, (before_inter_area / aoi_area) * 100.0))
    after_coverage = min(100.0, max(0.0, (after_inter_area / aoi_area) * 100.0))
    mutual_coverage = min(100.0, max(0.0, (mutual_inter_area / aoi_area) * 100.0))
    scene_overlap = min(100.0, max(0.0, (scenes_inter_area / min_scene_area) * 100.0))

    return SpatialOverlapMetrics(
        before_aoi_coverage_percent=round(before_coverage, 2),
        after_aoi_coverage_percent=round(after_coverage, 2),
        mutual_aoi_coverage_percent=round(mutual_coverage, 2),
        scene_overlap_percent=round(scene_overlap, 2),
        shared_bbox=shared_scenes_bbox,
    )


# ---------------------------------------------------------------------------
# Authoritative Compatibility Engine
# ---------------------------------------------------------------------------


def validate_temporal_pair(
    aoi: AOIGeometry,
    before_scene: SatelliteScene,
    after_scene: SatelliteScene,
    analysis_mode: AnalysisMode = AnalysisMode.CHANGE_DETECTION,
    pairing_preferences: PairingPreferences | None = None,
) -> TemporalPairValidationResult:
    """Evaluate metadata-based compatibility between before and after scenes."""
    prefs = pairing_preferences or PairingPreferences()
    issues: list[PairCompatibilityIssue] = []
    warnings: list[AnalysisWarning] = []

    # 1. Identity & Duplicate check
    if before_scene.id == after_scene.id:
        issues.append(
            PairCompatibilityIssue(
                code="SAME_SCENE_SELECTED",
                severity=WarningSeverity.CRITICAL,
                title="Identical Scene Selected",
                message="Before and after scenes must be distinct for change detection.",
                field="after_scene_id",
                suggested_action="Select a different scene for either period.",
                blocking=True,
            )
        )

    # 2. Chronological Ordering check
    t_before = before_scene.acquisition_time.astimezone(UTC)
    t_after = after_scene.acquisition_time.astimezone(UTC)
    gap_seconds = (t_after - t_before).total_seconds()
    gap_days = gap_seconds / 86400.0
    gap_hours = gap_seconds / 3600.0

    if gap_seconds <= 0 and before_scene.id != after_scene.id:
        issues.append(
            PairCompatibilityIssue(
                code="TEMPORAL_ORDER_REVERSED",
                severity=WarningSeverity.CRITICAL,
                title="Temporal Order Reversed",
                message=(
                    f"Baseline scene acquisition ({t_before.isoformat()}) must precede "
                    f"comparative scene acquisition ({t_after.isoformat()})."
                ),
                field="acquisition_time",
                suggested_action="Swap the before and after scene assignments.",
                blocking=True,
            )
        )

    # 3. Data Origin check
    before_origin = (before_scene.metadata or {}).get("data_origin", "real")
    after_origin = (after_scene.metadata or {}).get("data_origin", "real")
    origin_status = "real"

    if before_origin != after_origin:
        origin_status = "mixed"
        issues.append(
            PairCompatibilityIssue(
                code="MIXED_DATA_ORIGIN",
                severity=WarningSeverity.CRITICAL,
                title="Mixed Data Origin Incompatibility",
                message=(
                    f"Cannot pair a '{before_origin}' scene with a '{after_origin}' scene for "
                    "scientific change detection."
                ),
                field="data_origin",
                suggested_action="Ensure both scenes originate from real satellite data.",
                blocking=True,
            )
        )
    elif before_origin == "mock" or before_origin == "fallback":
        origin_status = before_origin

    # 4. Cross-Sensor & Sensor Type Validation
    is_before_optical = before_scene.sensor_type in (
        SensorType.OPTICAL,
        SensorType.MULTISPECTRAL,
    )
    is_after_optical = after_scene.sensor_type in (
        SensorType.OPTICAL,
        SensorType.MULTISPECTRAL,
    )
    is_before_sar = before_scene.sensor_type == SensorType.SAR
    is_after_sar = after_scene.sensor_type == SensorType.SAR

    is_cross_sensor = (is_before_optical and is_after_sar) or (is_before_sar and is_after_optical)
    if is_cross_sensor:
        issues.append(
            PairCompatibilityIssue(
                code="CROSS_SENSOR_PAIR_REQUIRES_MULTIMODAL_PIPELINE",
                severity=WarningSeverity.CRITICAL,
                title="Cross-Sensor Modality Incompatible",
                message=(
                    "Direct bi-temporal spectral change detection cannot compare optical surface "
                    "reflectance directly with SAR backscatter. Multimodal pipeline required."
                ),
                field="sensor_type",
                suggested_action=(
                    "Select either two optical or two SAR scenes for standard change analysis."
                ),
                blocking=True,
            )
        )

    # 5. Collection & Platform Compatibility
    collection_match = before_scene.collection == after_scene.collection
    if not collection_match and not is_cross_sensor:
        issues.append(
            PairCompatibilityIssue(
                code="DIFFERENT_COLLECTIONS",
                severity=WarningSeverity.MEDIUM,
                title="Different Satellite Collections",
                message=(
                    f"Scenes originate from different collections ({before_scene.collection} vs "
                    f"{after_scene.collection}). Spectral bands/calibration may differ."
                ),
                field="collection",
                suggested_action="Select scenes from identical collections for comparison.",
                blocking=False,
            )
        )

    platform_match = True
    if before_scene.platform and after_scene.platform:
        p1 = before_scene.platform.lower().replace("-", "").replace(" ", "")
        p2 = after_scene.platform.lower().replace("-", "").replace(" ", "")
        fam1 = p1.rstrip("abc")
        fam2 = p2.rstrip("abc")
        if fam1 != fam2:
            platform_match = False
            issues.append(
                PairCompatibilityIssue(
                    code="DIFFERENT_PLATFORMS",
                    severity=WarningSeverity.MEDIUM,
                    title="Different Sensor Platforms",
                    message=(
                        f"Acquisitions originate from different platforms ({before_scene.platform} "
                        f"and {after_scene.platform})."
                    ),
                    field="platform",
                    blocking=False,
                )
            )

    # 6. Spatial Overlap and AOI Coverage
    spatial_metrics = calculate_spatial_overlap_metrics(aoi, before_scene, after_scene)
    if (
        spatial_metrics.before_aoi_coverage_percent < 0.1
        or spatial_metrics.after_aoi_coverage_percent < 0.1
    ):
        issues.append(
            PairCompatibilityIssue(
                code="NO_AOI_COVERAGE",
                severity=WarningSeverity.CRITICAL,
                title="No AOI Intersection",
                message="One or both selected scenes do not intersect the defined AOI.",
                field="geometry",
                suggested_action="Select scenes whose footprints cover the active AOI.",
                blocking=True,
            )
        )
    elif spatial_metrics.mutual_aoi_coverage_percent < prefs.min_aoi_coverage_percent:
        issues.append(
            PairCompatibilityIssue(
                code="LOW_AOI_COVERAGE",
                severity=WarningSeverity.HIGH,
                title="Low Mutual AOI Coverage",
                message=(
                    f"Combined AOI coverage is {spatial_metrics.mutual_aoi_coverage_percent:.1f}%, "
                    f"below recommended threshold {prefs.min_aoi_coverage_percent:.1f}%."
                ),
                field="mutual_aoi_coverage_percent",
                suggested_action="Select scenes providing fuller spatial coverage over AOI.",
                blocking=False,
            )
        )
        warnings.append(
            AnalysisWarning(
                code=WarningCode.PARTIAL_COVERAGE,
                severity=WarningSeverity.HIGH,
                title="Partial AOI Coverage",
                message=(
                    f"Scene pair covers only {spatial_metrics.mutual_aoi_coverage_percent:.1f}% "
                    "of the AOI."
                ),
            )
        )

    # 7. Optical Cloud Cover checks
    cloud_score = 1.0
    if is_before_optical and is_after_optical:
        c1 = before_scene.cloud_cover if before_scene.cloud_cover is not None else 0.0
        c2 = after_scene.cloud_cover if after_scene.cloud_cover is not None else 0.0

        if c1 > 20.0 or c2 > 20.0:
            max_cloud = max(c1, c2)
            issues.append(
                PairCompatibilityIssue(
                    code="HIGH_CLOUD_COVER",
                    severity=WarningSeverity.MEDIUM,
                    title="Elevated Cloud Cover",
                    message=(
                        f"One or both scenes contain significant cloud cover "
                        f"(Before: {c1:.1f}%, After: {c2:.1f}%). Note: Granule-level cloud "
                        "percentage may not reflect exact cloud over the AOI."
                    ),
                    field="cloud_cover",
                    suggested_action="Inspect preview or select clearer acquisitions if available.",
                    blocking=False,
                )
            )
            warnings.append(
                AnalysisWarning(
                    code=WarningCode.HIGH_CLOUD_COVER,
                    severity=WarningSeverity.MEDIUM,
                    title="Elevated Cloud Cover",
                    message=(
                        f"High cloud cover detected in candidate scenes (up to {max_cloud:.1f}%)."
                    ),
                )
            )

        if abs(c1 - c2) > 30.0:
            issues.append(
                PairCompatibilityIssue(
                    code="CLOUD_COVER_MISMATCH",
                    severity=WarningSeverity.LOW,
                    title="Significant Cloud Cover Discrepancy",
                    message=(
                        f"Cloud cover differs by {abs(c1 - c2):.1f}% between the two acquisitions."
                    ),
                    field="cloud_cover",
                    blocking=False,
                )
            )

        cloud_penalty = 0.5 * (max(c1, c2) / 100.0) + 0.5 * (abs(c1 - c2) / 100.0)
        cloud_score = max(0.0, min(1.0, 1.0 - cloud_penalty))

    # 8. SAR Compatibility checks
    sar_geometry_score = 1.0
    if is_before_sar and is_after_sar:
        meta_b = before_scene.metadata or {}
        meta_a = after_scene.metadata or {}

        # Polarizations
        pols_b = set(meta_b.get("polarizations", []))
        pols_a = set(meta_a.get("polarizations", []))
        if pols_b and pols_a and not (pols_b & pols_a):
            issues.append(
                PairCompatibilityIssue(
                    code="POLARIZATION_MISMATCH",
                    severity=WarningSeverity.CRITICAL,
                    title="No Shared SAR Polarizations",
                    message=(
                        f"Before ({pols_b}) and After ({pols_a}) scenes do not share polarizations."
                    ),
                    field="polarizations",
                    suggested_action="Select SAR scenes with matching polarizations (e.g. VV/VH).",
                    blocking=True,
                )
            )

        # Orbit direction
        orbit_b = meta_b.get("orbit_direction")
        orbit_a = meta_a.get("orbit_direction")
        if orbit_b and orbit_a and str(orbit_b).lower() != str(orbit_a).lower():
            issues.append(
                PairCompatibilityIssue(
                    code="DIFFERENT_ORBIT_DIRECTION",
                    severity=WarningSeverity.MEDIUM,
                    title="Different SAR Orbit Directions",
                    message=(
                        f"Opposing orbit passes ({orbit_b} vs {orbit_a}) alter radar look angle "
                        "and terrain layover."
                    ),
                    field="orbit_direction",
                    suggested_action="Prefer identical orbit directions (Ascending or Descending).",
                    blocking=False,
                )
            )
            sar_geometry_score *= 0.7

    # 9. Resolution and Spectral Band Compatibility
    res_b = before_scene.resolution_meters or 10.0
    res_a = after_scene.resolution_meters or 10.0
    res_ratio = min(res_b, res_a) / max(res_b, res_a)
    if res_ratio < 0.5:
        issues.append(
            PairCompatibilityIssue(
                code="RESOLUTION_MISMATCH",
                severity=WarningSeverity.HIGH,
                title="Spatial Resolution Disparity",
                message=f"Spatial resolution difference is large ({res_b}m vs {res_a}m).",
                field="resolution_meters",
                blocking=False,
            )
        )

    # Required bands
    if prefs.required_bands:
        missing_b = [b for b in prefs.required_bands if b not in before_scene.available_bands]
        missing_a = [b for b in prefs.required_bands if b not in after_scene.available_bands]
        if missing_b or missing_a:
            issues.append(
                PairCompatibilityIssue(
                    code="REQUIRED_BANDS_MISSING",
                    severity=WarningSeverity.HIGH,
                    title="Required Spectral Bands Missing",
                    message=f"Missing required bands: Before ({missing_b}), After ({missing_a}).",
                    field="available_bands",
                    blocking=True,
                )
            )

    # 10. Temporal Gap & Seasonal Phenology
    if prefs.maximum_temporal_gap_days and gap_days > prefs.maximum_temporal_gap_days:
        issues.append(
            PairCompatibilityIssue(
                code="TEMPORAL_GAP_TOO_LARGE",
                severity=WarningSeverity.MEDIUM,
                title="Large Temporal Gap",
                message=(
                    f"Temporal gap ({gap_days:.1f} days) exceeds preferred limit "
                    f"({prefs.maximum_temporal_gap_days} days)."
                ),
                field="temporal_gap_days",
                blocking=False,
            )
        )
        warnings.append(
            AnalysisWarning(
                code=WarningCode.TEMPORAL_GAP_TOO_LARGE,
                severity=WarningSeverity.MEDIUM,
                title="Large Temporal Separation",
                message=f"Large temporal separation ({gap_days:.0f} days) between acquisitions.",
            )
        )

    # Seasonal phenology check (day of year delta)
    doy_b = t_before.timetuple().tm_yday
    doy_a = t_after.timetuple().tm_yday
    seasonal_gap = abs(doy_b - doy_a)
    if seasonal_gap > 182:
        seasonal_gap = 365 - seasonal_gap

    if gap_days > 200 and seasonal_gap > 60:
        issues.append(
            PairCompatibilityIssue(
                code="SEASONAL_MISMATCH",
                severity=WarningSeverity.LOW,
                title="Seasonal Phenology Difference",
                message=(
                    f"Acquisitions occur in different seasons (DOY delta: {seasonal_gap} days). "
                    "Vegetation phenology or sun angle differences may be present."
                ),
                field="acquisition_time",
                blocking=False,
            )
        )

    # -----------------------------------------------------------------------
    # Compute Factor Breakdown & Overall Compatibility Score
    # -----------------------------------------------------------------------
    factors: list[CompatibilityFactorScore] = []

    # Factor 1: Collection & Platform (weight: 0.25)
    f1_score = 1.0 if collection_match and platform_match else (0.7 if collection_match else 0.4)
    if is_cross_sensor:
        f1_score = 0.0
    factors.append(
        CompatibilityFactorScore(
            name="collection_platform",
            score=round(f1_score, 2),
            weight=0.25,
            weighted_score=round(0.25 * f1_score, 3),
            status=(
                "optimal"
                if f1_score >= 0.9
                else ("acceptable" if f1_score >= 0.6 else "suboptimal")
            ),
            details=(
                "Same collection and platform family"
                if f1_score >= 0.9
                else f"Collection match: {collection_match}, Platform match: {platform_match}"
            ),
        )
    )

    # Factor 2: Spatial Coverage & Overlap (weight: 0.25)
    f2_score = (spatial_metrics.mutual_aoi_coverage_percent / 100.0) * 0.8 + (
        spatial_metrics.scene_overlap_percent / 100.0
    ) * 0.2
    f2_score = max(0.0, min(1.0, f2_score))
    factors.append(
        CompatibilityFactorScore(
            name="spatial_coverage",
            score=round(f2_score, 2),
            weight=0.25,
            weighted_score=round(0.25 * f2_score, 3),
            status=(
                "optimal"
                if f2_score >= 0.85
                else ("acceptable" if f2_score >= 0.6 else "suboptimal")
            ),
            details=(
                f"Mutual AOI: {spatial_metrics.mutual_aoi_coverage_percent:.1f}%, "
                f"Scene overlap: {spatial_metrics.scene_overlap_percent:.1f}%"
            ),
        )
    )

    # Factor 3: Quality / Atmosphere / Radar Geometry (weight: 0.20)
    f3_score = cloud_score if is_before_optical else sar_geometry_score
    factors.append(
        CompatibilityFactorScore(
            name="quality_atmosphere",
            score=round(f3_score, 2),
            weight=0.20,
            weighted_score=round(0.20 * f3_score, 3),
            status=(
                "optimal"
                if f3_score >= 0.8
                else ("acceptable" if f3_score >= 0.6 else "suboptimal")
            ),
            details=(
                f"Optical cloud suitability score: {f3_score:.2f}"
                if is_before_optical
                else f"SAR acquisition geometry score: {f3_score:.2f}"
            ),
        )
    )

    # Factor 4: Temporal & Seasonal Suitability (weight: 0.15)
    temporal_penalty = min(0.5, gap_days / 1825.0)  # Max 0.5 penalty over 5 years
    seasonal_penalty = (seasonal_gap / 182.0) * 0.3 if gap_days > 200 else 0.0
    f4_score = max(0.0, min(1.0, 1.0 - temporal_penalty - seasonal_penalty))
    factors.append(
        CompatibilityFactorScore(
            name="temporal_suitability",
            score=round(f4_score, 2),
            weight=0.15,
            weighted_score=round(0.15 * f4_score, 3),
            status=(
                "optimal"
                if f4_score >= 0.8
                else ("acceptable" if f4_score >= 0.5 else "suboptimal")
            ),
            details=f"Temporal gap: {gap_days:.1f}d, Seasonal delta: {seasonal_gap}d",
        )
    )

    # Factor 5: Spectral Bands & Spatial Resolution (weight: 0.15)
    f5_score = res_ratio * 0.7 + (1.0 if not prefs.required_bands else 0.3)
    f5_score = max(0.0, min(1.0, f5_score))
    factors.append(
        CompatibilityFactorScore(
            name="spectral_resolution",
            score=round(f5_score, 2),
            weight=0.15,
            weighted_score=round(0.15 * f5_score, 3),
            status=(
                "optimal"
                if f5_score >= 0.85
                else ("acceptable" if f5_score >= 0.6 else "suboptimal")
            ),
            details=f"Resolution ratio: {res_ratio:.2f} ({res_b}m vs {res_a}m)",
        )
    )

    # Overall compatibility score
    raw_score = sum(f.weighted_score for f in factors)
    compatibility_score = round(max(0.0, min(1.0, raw_score)), 2)

    has_blocking = any(issue.blocking for issue in issues)

    if has_blocking:
        valid = False
        status = PairCompatibilityStatus.INCOMPATIBLE
    elif compatibility_score >= 0.80 and len(issues) == 0:
        valid = True
        status = PairCompatibilityStatus.COMPATIBLE
    elif compatibility_score >= 0.60:
        valid = True
        status = PairCompatibilityStatus.COMPATIBLE_WITH_WARNINGS
    else:
        valid = False
        status = PairCompatibilityStatus.INCOMPATIBLE

    normalized_selection = SceneSelection(
        before_scene_id=before_scene.id,
        after_scene_id=after_scene.id,
        primary_scene_id=after_scene.id,
        supporting_scene_ids=[before_scene.id],
        selection_reason=(
            f"Validated temporal pair with score {compatibility_score:.2f} ({status.value})"
        ),
    )

    return TemporalPairValidationResult(
        valid=valid,
        status=status,
        before_scene_id=before_scene.id,
        after_scene_id=after_scene.id,
        temporal_gap_days=round(gap_days, 2),
        temporal_gap_hours=round(gap_hours, 2),
        compatibility_score=compatibility_score,
        factors=factors,
        issues=issues,
        warnings=warnings,
        spatial_metrics=spatial_metrics,
        normalized_selection=normalized_selection,
        data_origin_status=origin_status,
    )


# ---------------------------------------------------------------------------
# Automatic Deterministic Pair Recommendation
# ---------------------------------------------------------------------------


def recommend_best_temporal_pair(
    aoi: AOIGeometry,
    before_scenes: list[SatelliteScene],
    after_scenes: list[SatelliteScene],
    preferences: PairingPreferences | None = None,
    max_candidates_to_eval: int = 10,
) -> RecommendedPair | None:
    """Deterministically discover and recommend the highest scoring valid scene pair."""
    if not before_scenes or not after_scenes:
        return None

    prefs = preferences or PairingPreferences()
    eval_before = before_scenes[:max_candidates_to_eval]
    eval_after = after_scenes[:max_candidates_to_eval]

    best_result: TemporalPairValidationResult | None = None
    best_score: float = -1.0

    for b_scene in eval_before:
        for a_scene in eval_after:
            if b_scene.id == a_scene.id:
                continue
            if b_scene.acquisition_time >= a_scene.acquisition_time:
                continue

            result = validate_temporal_pair(aoi, b_scene, a_scene, pairing_preferences=prefs)
            if not result.valid or any(i.blocking for i in result.issues):
                continue

            # Prioritize score
            if result.compatibility_score > best_score:
                best_score = result.compatibility_score
                best_result = result

    if not best_result:
        return None

    explanation: list[str] = [
        f"Score: {best_result.compatibility_score:.2f} ({best_result.status.value}).",
        f"Temporal gap: {best_result.temporal_gap_days:.1f} days.",
    ]
    if best_result.spatial_metrics:
        explanation.append(
            f"Mutual AOI coverage: {best_result.spatial_metrics.mutual_aoi_coverage_percent:.1f}%."
        )

    return RecommendedPair(
        before_scene_id=best_result.before_scene_id,
        after_scene_id=best_result.after_scene_id,
        compatibility_score=best_result.compatibility_score,
        status=best_result.status,
        reason=(
            f"Best candidate pair with {best_result.compatibility_score * 100:.0f}% score "
            f"and {best_result.temporal_gap_days:.0f}d separation."
        ),
        explanation=explanation,
    )
