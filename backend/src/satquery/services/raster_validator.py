"""Validation utilities for raster imagery, file signatures, and georeferenced metadata."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from rasterio.io import MemoryFile

from satquery.api.schemas.imagery import (
    ImageryFormat,
    ImageryProductType,
)

PNG_HEADER = b"\x89PNG\r\n\x1a\n"
JPEG_HEADER = b"\xff\xd8\xff"
TIFF_LE_HEADER = b"II*\x00"
TIFF_BE_HEADER = b"MM\x00*"


class RasterValidationError(Exception):
    """Exception raised when raster validation fails."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(slots=True)
class ValidatedRasterInfo:
    format_type: ImageryFormat
    width: int
    height: int
    band_count: int
    crs: str
    bbox: tuple[float, float, float, float]
    transform: list[float]
    data_type: str
    no_data_values: list[float | None]


def validate_image_file_signature(
    data: bytes, expected_format: ImageryFormat | None = None
) -> ImageryFormat:
    """Validate image magic bytes against standard file signatures."""
    if len(data) < 8:
        raise RasterValidationError(
            "INVALID_FILE_SIGNATURE", "File data is too short to be a valid image."
        )

    # Check if data looks like HTML or JSON error payload
    prefix = data[:128].lower()
    if b"<html" in prefix or b"<!doctype html" in prefix or b"<xml" in prefix:
        raise RasterValidationError(
            "PROVIDER_PROCESSING_FAILED", "Provider returned an HTML error page instead of imagery."
        )
    if prefix.strip().startswith(b"{") and (
        b'"error"' in prefix or b'"message"' in prefix or b'"code"' in prefix
    ):
        raise RasterValidationError(
            "PROVIDER_PROCESSING_FAILED",
            "Provider returned a JSON error payload instead of imagery.",
        )

    detected_format: ImageryFormat | None = None
    if data.startswith(PNG_HEADER):
        detected_format = ImageryFormat.PNG
    elif data.startswith(JPEG_HEADER):
        detected_format = ImageryFormat.JPEG
    elif data.startswith(TIFF_LE_HEADER) or data.startswith(TIFF_BE_HEADER):
        detected_format = ImageryFormat.GEOTIFF
    else:
        raise RasterValidationError(
            "UNSUPPORTED_IMAGERY_FORMAT", "Unrecognized or corrupted image file signature."
        )

    if expected_format is not None and detected_format != expected_format:
        # COG is also GEOTIFF in signature
        if not (expected_format == ImageryFormat.COG and detected_format == ImageryFormat.GEOTIFF):
            raise RasterValidationError(
                "UNSUPPORTED_IMAGERY_FORMAT",
                f"Expected format {expected_format.value} but detected {detected_format.value}.",
            )

    return detected_format


def validate_raster_dataset(
    data: bytes,
    *,
    expected_format: ImageryFormat,
    product_type: ImageryProductType,
    max_pixels: int = 16_777_216,
    max_bytes: int = 50 * 1024 * 1024,
    required_bands: list[str] | None = None,
) -> ValidatedRasterInfo:
    """Perform rigorous georeferenced raster header, dimension, and pixel decodability checks."""
    if len(data) > max_bytes:
        raise RasterValidationError(
            "OUTPUT_TOO_LARGE",
            f"Raster size ({len(data)} bytes) exceeds limit ({max_bytes} bytes).",
        )

    detected_format = validate_image_file_signature(data, expected_format)

    # For PNG / JPEG map previews that are not full GeoTIFFs, handle basic image decoding
    if (
        detected_format in {ImageryFormat.PNG, ImageryFormat.JPEG}
        and product_type == ImageryProductType.MAP_PREVIEW
    ):
        try:
            with MemoryFile(data) as memfile:
                with memfile.open() as src:
                    width = src.width
                    height = src.height
                    band_count = src.count
                    if width <= 0 or height <= 0:
                        raise RasterValidationError(
                            "INVALID_RESOLUTION", "Image dimensions must be greater than zero."
                        )
                    if width * height > max_pixels:
                        raise RasterValidationError(
                            "PIXEL_LIMIT_EXCEEDED",
                            f"Pixel count {width * height} exceeds limit {max_pixels}.",
                        )
                    # Sample read
                    sample = src.read(1, window=((0, min(10, height)), (0, min(10, width))))
                    if sample is None or sample.size == 0:
                        raise RasterValidationError(
                            "RASTER_VALIDATION_FAILED", "Failed to decode raster pixel data."
                        )

                    crs_str = src.crs.to_string() if src.crs else "EPSG:3857"
                    bounds = src.bounds
                    bbox = (
                        bounds.left if isfinite(bounds.left) else 0.0,
                        bounds.bottom if isfinite(bounds.bottom) else 0.0,
                        bounds.right if isfinite(bounds.right) else 1.0,
                        bounds.top if isfinite(bounds.top) else 1.0,
                    )
                    transform_list = (
                        list(src.transform)[:6]
                        if src.transform
                        else [1.0, 0.0, 0.0, 0.0, -1.0, 0.0]
                    )
                    no_data = list(src.nodatavals) if src.nodatavals else [None] * band_count

                    return ValidatedRasterInfo(
                        format_type=detected_format,
                        width=width,
                        height=height,
                        band_count=band_count,
                        crs=crs_str,
                        bbox=bbox,
                        transform=transform_list,
                        data_type=src.dtypes[0] if src.dtypes else "uint8",
                        no_data_values=no_data,
                    )
        except RasterValidationError:
            raise
        except Exception as exc:
            raise RasterValidationError(
                "RASTER_VALIDATION_FAILED", f"Failed to open image: {exc}"
            ) from exc

    # For GeoTIFF / COG analysis rasters or georeferenced rasters
    try:
        with MemoryFile(data) as memfile:
            with memfile.open() as src:
                width = src.width
                height = src.height
                band_count = src.count

                if width <= 0 or height <= 0:
                    raise RasterValidationError(
                        "INVALID_RESOLUTION", "Raster dimensions must be positive."
                    )
                if width * height > max_pixels:
                    raise RasterValidationError(
                        "PIXEL_LIMIT_EXCEEDED",
                        f"Pixel count {width * height} exceeds limit {max_pixels}.",
                    )

                if not src.crs:
                    raise RasterValidationError(
                        "UNSUPPORTED_CRS", "Raster missing valid Coordinate Reference System (CRS)."
                    )

                crs_str = src.crs.to_string()

                bounds = src.bounds
                if not (
                    isfinite(bounds.left)
                    and isfinite(bounds.bottom)
                    and isfinite(bounds.right)
                    and isfinite(bounds.top)
                ):
                    raise RasterValidationError(
                        "RASTER_VALIDATION_FAILED", "Raster bounds contain non-finite coordinates."
                    )

                if bounds.left >= bounds.right or bounds.bottom >= bounds.top:
                    raise RasterValidationError(
                        "RASTER_VALIDATION_FAILED", "Raster bounds are inverted or degenerate."
                    )

                bbox = (bounds.left, bounds.bottom, bounds.right, bounds.top)
                transform_list = list(src.transform)[:6]

                if required_bands and band_count < len(required_bands):
                    raise RasterValidationError(
                        "REQUIRED_BANDS_MISSING",
                        f"Raster contains {band_count} bands, but {len(required_bands)} required.",
                    )

                # Decode a small sample to verify decodability
                sample = src.read(1, window=((0, min(10, height)), (0, min(10, width))))
                if sample is None or sample.size == 0:
                    raise RasterValidationError(
                        "RASTER_VALIDATION_FAILED", "Failed to sample raster pixel data."
                    )

                no_data = list(src.nodatavals) if src.nodatavals else [None] * band_count

                return ValidatedRasterInfo(
                    format_type=detected_format,
                    width=width,
                    height=height,
                    band_count=band_count,
                    crs=crs_str,
                    bbox=bbox,
                    transform=transform_list,
                    data_type=src.dtypes[0] if src.dtypes else "float32",
                    no_data_values=no_data,
                )
    except RasterValidationError:
        raise
    except Exception as exc:
        raise RasterValidationError(
            "RASTER_VALIDATION_FAILED", f"Corrupt or unreadable raster data: {exc}"
        ) from exc
