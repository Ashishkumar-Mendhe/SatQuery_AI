from __future__ import annotations

from math import isfinite

from rasterio.crs import CRS
from rasterio.errors import CRSError

from satquery.api.schemas.processing import OutputGrid


class AreaMeasurementError(ValueError):
    """The raster grid cannot support a defensible square-metre area measurement."""


def projected_pixel_area_square_metres(grid: OutputGrid) -> float:
    """Return affine cell area converted from the projected CRS linear unit to metres."""

    try:
        crs = CRS.from_user_input(grid.crs)
    except CRSError as exc:
        raise AreaMeasurementError("The output grid CRS is invalid.") from exc
    if not crs.is_projected:
        raise AreaMeasurementError(
            "Square-metre area requires a projected CRS; angular degrees are not metres."
        )
    try:
        unit_to_metres = float(crs.linear_units_factor[1])
    except CRSError as exc:
        raise AreaMeasurementError(
            "The projected CRS does not declare a usable linear-unit conversion."
        ) from exc
    a, b, _, d, e, _ = grid.transform
    area_in_crs_units = abs(a * e - b * d)
    area_square_metres = area_in_crs_units * unit_to_metres**2
    if not isfinite(area_square_metres) or area_square_metres <= 0:
        raise AreaMeasurementError("The output grid has no positive finite pixel area.")
    return area_square_metres
