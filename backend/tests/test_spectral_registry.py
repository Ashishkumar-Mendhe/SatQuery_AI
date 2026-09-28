"""Tests for spectral registry, index definitions, and band role resolution."""

import pytest

from satquery.api.schemas.spectral import (
    SpectralIndexName,
)
from satquery.services.spectral_registry import (
    SpectralRegistry,
    SpectralRegistryError,
)


def test_get_all_index_definitions() -> None:
    """Verify all 6 MVP and optional indices are properly registered."""
    defs = SpectralRegistry.get_all_index_definitions()
    assert len(defs) == 6
    names = {d.name for d in defs}
    assert names == {
        SpectralIndexName.NDVI,
        SpectralIndexName.NDWI,
        SpectralIndexName.NDBI,
        SpectralIndexName.EVI,
        SpectralIndexName.SAVI,
        SpectralIndexName.MNDWI,
    }


def test_get_individual_index_definitions() -> None:
    """Verify definitions have required bands, formulas, and expected ranges."""
    ndvi_def = SpectralRegistry.get_index_definition(SpectralIndexName.NDVI)
    assert ndvi_def.name == SpectralIndexName.NDVI
    assert ndvi_def.required_bands == ["nir", "red"]
    assert ndvi_def.expected_range == (-1.0, 1.0)
    assert ndvi_def.default_color_ramp == "RdYlGn"

    ndwi_def = SpectralRegistry.get_index_definition("ndwi")
    assert ndwi_def.name == SpectralIndexName.NDWI
    assert ndwi_def.required_bands == ["green", "nir"]

    ndbi_def = SpectralRegistry.get_index_definition("ndbi")
    assert ndbi_def.name == SpectralIndexName.NDBI
    assert ndbi_def.required_bands == ["swir1", "nir"]


def test_unsupported_index_raises_error() -> None:
    """Verify unsupported index name raises structured error."""
    with pytest.raises(SpectralRegistryError) as exc_info:
        SpectralRegistry.get_index_definition("invalid_index")
    assert exc_info.value.code == "UNSUPPORTED_INDEX"


def test_resolve_band_indices_sentinel2_stac() -> None:
    """Verify resolution of Sentinel-2 STAC asset names."""
    available = ["B02", "B03", "B04", "B08", "B11", "B12"]
    band_map = SpectralRegistry.resolve_band_indices(
        available_band_names=available,
        required_roles=["nir", "red", "green", "blue", "swir1"],
    )
    assert band_map["blue"] == 0  # B02
    assert band_map["green"] == 1  # B03
    assert band_map["red"] == 2  # B04
    assert band_map["nir"] == 3  # B08
    assert band_map["swir1"] == 4  # B11


def test_resolve_band_indices_canonical_names() -> None:
    """Verify resolution of lowercase canonical band names."""
    available = ["red", "green", "blue", "nir", "swir1", "swir2"]
    band_map = SpectralRegistry.resolve_band_indices(
        available_band_names=available,
        required_roles=["nir", "red"],
    )
    assert band_map["red"] == 0
    assert band_map["nir"] == 3


def test_resolve_band_indices_missing_band_raises() -> None:
    """Verify missing required band raises structured error."""
    available = ["B02", "B03", "B04"]  # No NIR
    with pytest.raises(SpectralRegistryError) as exc_info:
        SpectralRegistry.resolve_band_indices(
            available_band_names=available,
            required_roles=["nir", "red"],
        )
    assert exc_info.value.code == "REQUIRED_BAND_MISSING"
    assert "nir" in exc_info.value.message.lower()
