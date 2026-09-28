"""Unit tests for ChangeRegistry and change method specifications."""

import pytest

from satquery.api.schemas.change import (
    ChangeDetectionMethod,
    ChangeDirectionality,
    ThresholdStrategy,
)
from satquery.services.change_registry import (
    ChangeRegistry,
    ChangeRegistryError,
)


def test_get_all_change_definitions() -> None:
    """Verify all 5 supported change methods are registered."""
    defs = ChangeRegistry.get_all_method_definitions()
    assert len(defs) == 5
    method_ids = {d.method for d in defs}
    assert ChangeDetectionMethod.NDVI_DIFFERENCE in method_ids
    assert ChangeDetectionMethod.NDWI_DIFFERENCE in method_ids
    assert ChangeDetectionMethod.NDBI_DIFFERENCE in method_ids
    assert ChangeDetectionMethod.ABSOLUTE_INDEX_DIFFERENCE in method_ids
    assert ChangeDetectionMethod.MULTIBAND_CHANGE_MAGNITUDE in method_ids


def test_ndvi_difference_definition() -> None:
    """Verify NDVI differencing specifications."""
    defn = ChangeRegistry.get_method_definition(ChangeDetectionMethod.NDVI_DIFFERENCE)
    assert defn.method == ChangeDetectionMethod.NDVI_DIFFERENCE
    assert defn.display_name == "NDVI Spectral Difference"
    assert defn.directionality == ChangeDirectionality.BIDIRECTIONAL
    assert defn.expected_range == (-2.0, 2.0)
    assert defn.default_threshold_config.strategy == ThresholdStrategy.FIXED
    assert defn.default_threshold_config.positive_threshold == 0.15
    assert defn.default_threshold_config.negative_threshold == -0.15
    assert defn.default_color_ramp == "RdYlGn"


def test_ndbi_difference_definition_limitations() -> None:
    """Verify NDBI built-up difference contains explicit non-definitive construction warning."""
    defn = ChangeRegistry.get_method_definition(ChangeDetectionMethod.NDBI_DIFFERENCE)
    assert "NOT prove newly constructed buildings" in defn.limitations
    assert defn.directionality == ChangeDirectionality.BIDIRECTIONAL


def test_multiband_change_magnitude_definition() -> None:
    """Verify Multiband Change Vector Magnitude is magnitude-only."""
    defn = ChangeRegistry.get_method_definition(ChangeDetectionMethod.MULTIBAND_CHANGE_MAGNITUDE)
    assert defn.directionality == ChangeDirectionality.MAGNITUDE_ONLY
    assert defn.input_type == "multiband_reflectance"


def test_unsupported_change_method_raises_error() -> None:
    """Verify requesting an unsupported change method raises ChangeRegistryError."""
    with pytest.raises(ChangeRegistryError) as exc_info:
        ChangeRegistry.get_method_definition("unsupported_method_xyz")
    assert exc_info.value.code == "UNSUPPORTED_CHANGE_METHOD"
