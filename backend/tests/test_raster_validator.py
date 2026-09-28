"""Unit tests for the raster validator module."""

from __future__ import annotations

import io

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from rio_tiler.utils import render

from satquery.api.schemas.imagery import ImageryFormat, ImageryProductType
from satquery.services.raster_validator import (
    RasterValidationError,
    validate_image_file_signature,
    validate_raster_dataset,
)


def create_synthetic_png(width: int = 64, height: int = 64) -> bytes:
    data = (np.random.rand(3, height, width) * 255).astype(np.uint8)
    return render(data, img_format="PNG")


def create_synthetic_geotiff(width: int = 64, height: int = 64) -> bytes:
    data = (np.random.rand(3, height, width) * 1000).astype(np.float32)
    transform = from_bounds(77.45, 12.85, 77.75, 13.15, width, height)
    with io.BytesIO() as bio:
        with rasterio.open(
            bio,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=3,
            dtype="float32",
            crs="EPSG:4326",
            transform=transform,
        ) as dst:
            dst.write(data)
        return bio.getvalue()


def test_signature_validation_png() -> None:
    png_bytes = create_synthetic_png()
    fmt = validate_image_file_signature(png_bytes)
    assert fmt == ImageryFormat.PNG


def test_signature_validation_geotiff() -> None:
    tif_bytes = create_synthetic_geotiff()
    fmt = validate_image_file_signature(tif_bytes)
    assert fmt == ImageryFormat.GEOTIFF


def test_reject_html_error_payload() -> None:
    html_data = b"<!DOCTYPE html><html><body>Error 500: Server Failed</body></html>"
    with pytest.raises(RasterValidationError) as exc:
        validate_image_file_signature(html_data)
    assert "HTML error page" in str(exc.value)


def test_reject_json_error_payload() -> None:
    json_data = b'{"error": "SceneNotAvailable", "code": 404, "message": "Item missing"}'
    with pytest.raises(RasterValidationError) as exc:
        validate_image_file_signature(json_data)
    assert "JSON error payload" in str(exc.value)


def test_validate_valid_map_preview_png() -> None:
    png_bytes = create_synthetic_png(128, 128)
    info = validate_raster_dataset(
        png_bytes,
        expected_format=ImageryFormat.PNG,
        product_type=ImageryProductType.MAP_PREVIEW,
    )
    assert info.width == 128
    assert info.height == 128
    assert info.format_type == ImageryFormat.PNG


def test_validate_valid_analysis_geotiff() -> None:
    tif_bytes = create_synthetic_geotiff(128, 128)
    info = validate_raster_dataset(
        tif_bytes,
        expected_format=ImageryFormat.GEOTIFF,
        product_type=ImageryProductType.ANALYSIS_RASTER,
    )
    assert info.width == 128
    assert info.height == 128
    assert info.crs == "EPSG:4326"
    assert info.band_count == 3
