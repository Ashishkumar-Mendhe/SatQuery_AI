"""Authoritative registry of supported pixel-level change detection methods."""

from __future__ import annotations

from satquery.api.schemas.change import (
    CHANGE_SCHEMA_VERSION,
    ChangeDetectionDefinition,
    ChangeDetectionMethod,
    ChangeDirectionality,
    ChangeThresholdConfig,
    ThresholdStrategy,
)


class ChangeRegistryError(ValueError):
    """Error raised when an unsupported or invalid change method is requested."""

    def __init__(self, code: str, message: str, details: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


SUPPORTED_CHANGE_METHODS: dict[ChangeDetectionMethod, ChangeDetectionDefinition] = {
    ChangeDetectionMethod.NDVI_DIFFERENCE: ChangeDetectionDefinition(
        method=ChangeDetectionMethod.NDVI_DIFFERENCE,
        display_name="NDVI Spectral Difference",
        formula="afterNDVI - beforeNDVI",
        input_type="spectral_index",
        directionality=ChangeDirectionality.BIDIRECTIONAL,
        expected_range=(-2.0, 2.0),
        default_threshold_config=ChangeThresholdConfig(
            strategy=ThresholdStrategy.FIXED,
            positive_threshold=0.15,
            negative_threshold=-0.15,
            min_cluster_size_pixels=5,
            simplify_tolerance_meters=5.0,
        ),
        supported_sensors=["Sentinel-2", "Landsat-8", "Landsat-9"],
        description=(
            "Calculates pixel-by-pixel difference in Normalized Difference "
            "Vegetation Index (NDVI). Positive values indicate an increase in "
            "vegetation-related spectral response; negative values indicate a decrease."
        ),
        limitations=(
            "Does not independently prove deforestation, crop harvesting, or vegetation loss "
            "without contextual ground truth. Phenology, solar angle, and soil moisture can "
            "influence differences."
        ),
        default_color_ramp="RdYlGn",
        version=CHANGE_SCHEMA_VERSION,
    ),
    ChangeDetectionMethod.NDWI_DIFFERENCE: ChangeDetectionDefinition(
        method=ChangeDetectionMethod.NDWI_DIFFERENCE,
        display_name="NDWI Spectral Difference",
        formula="afterNDWI - beforeNDWI",
        input_type="spectral_index",
        directionality=ChangeDirectionality.BIDIRECTIONAL,
        expected_range=(-2.0, 2.0),
        default_threshold_config=ChangeThresholdConfig(
            strategy=ThresholdStrategy.FIXED,
            positive_threshold=0.15,
            negative_threshold=-0.15,
            min_cluster_size_pixels=5,
            simplify_tolerance_meters=5.0,
        ),
        supported_sensors=["Sentinel-2", "Landsat-8", "Landsat-9"],
        description=(
            "Calculates pixel-by-pixel difference in Normalized Difference "
            "Water Index (NDWI - McFeeters). Positive values indicate increased surface "
            "moisture/water response; negative values indicate drying or water recession."
        ),
        limitations=(
            "May confuse dark shadow dynamics, urban asphalt, or moist soil with open water "
            "expansion. Does not constitute confirmed flood or inundation boundary."
        ),
        default_color_ramp="RdBu_r",
        version=CHANGE_SCHEMA_VERSION,
    ),
    ChangeDetectionMethod.NDBI_DIFFERENCE: ChangeDetectionDefinition(
        method=ChangeDetectionMethod.NDBI_DIFFERENCE,
        display_name="NDBI Spectral Difference",
        formula="afterNDBI - beforeNDBI",
        input_type="spectral_index",
        directionality=ChangeDirectionality.BIDIRECTIONAL,
        expected_range=(-2.0, 2.0),
        default_threshold_config=ChangeThresholdConfig(
            strategy=ThresholdStrategy.FIXED,
            positive_threshold=0.15,
            negative_threshold=-0.15,
            min_cluster_size_pixels=5,
            simplify_tolerance_meters=5.0,
        ),
        supported_sensors=["Sentinel-2", "Landsat-8", "Landsat-9"],
        description=(
            "Calculates pixel-by-pixel difference in Normalized Difference Built-up Index (NDBI). "
            "Positive values indicate increased built-up/impervious spectral response."
        ),
        limitations=(
            "Positive NDBI change does NOT prove newly constructed buildings. "
            "Dry soil, cleared land, seasonal crop clearing, and tarmac show "
            "identical positive responses."
        ),
        default_color_ramp="YlOrRd",
        version=CHANGE_SCHEMA_VERSION,
    ),
    ChangeDetectionMethod.ABSOLUTE_INDEX_DIFFERENCE: ChangeDetectionDefinition(
        method=ChangeDetectionMethod.ABSOLUTE_INDEX_DIFFERENCE,
        display_name="Absolute Spectral Magnitude Difference",
        formula="|afterNDVI - beforeNDVI|",
        input_type="spectral_index",
        directionality=ChangeDirectionality.MAGNITUDE_ONLY,
        expected_range=(0.0, 2.0),
        default_threshold_config=ChangeThresholdConfig(
            strategy=ThresholdStrategy.FIXED,
            positive_threshold=0.20,
            negative_threshold=0.0,
            min_cluster_size_pixels=5,
            simplify_tolerance_meters=5.0,
        ),
        supported_sensors=["Sentinel-2", "Landsat-8", "Landsat-9"],
        description=(
            "Calculates the absolute magnitude of spectral change (|Δ|), highlighting areas "
            "with significant disturbance regardless of change direction."
        ),
        limitations=(
            "Does not differentiate between growth and depletion. Used strictly as an anomaly "
            "and disturbance magnitude screening layer."
        ),
        default_color_ramp="viridis",
        version=CHANGE_SCHEMA_VERSION,
    ),
    ChangeDetectionMethod.MULTIBAND_CHANGE_MAGNITUDE: ChangeDetectionDefinition(
        method=ChangeDetectionMethod.MULTIBAND_CHANGE_MAGNITUDE,
        display_name="Multiband Change Vector Magnitude",
        formula="sqrt(sum((afterBand_i - beforeBand_i)^2))",
        input_type="multiband_reflectance",
        directionality=ChangeDirectionality.MAGNITUDE_ONLY,
        expected_range=(0.0, 3.0),
        default_threshold_config=ChangeThresholdConfig(
            strategy=ThresholdStrategy.FIXED,
            positive_threshold=0.25,
            negative_threshold=0.0,
            min_cluster_size_pixels=5,
            simplify_tolerance_meters=5.0,
        ),
        supported_sensors=["Sentinel-2", "Landsat-8", "Landsat-9"],
        description=(
            "Computes the Euclidean distance across all mutual spectral bands "
            "(B02, B03, B04, B08), providing a holistic measure of "
            "multi-spectral radiometric shift."
        ),
        limitations=(
            "Sensitive to atmospheric scattering differences, illumination variations, "
            "and sun angle. Inputs must be surface-reflectance harmonized."
        ),
        default_color_ramp="magma",
        version=CHANGE_SCHEMA_VERSION,
    ),
}


class ChangeRegistry:
    """Registry providing authoritative metadata, validation, and defaults for change methods."""

    @classmethod
    def get_method_definition(
        cls, method: ChangeDetectionMethod | str
    ) -> ChangeDetectionDefinition:
        """Retrieve definition for a specific change method."""
        try:
            enum_method = (
                ChangeDetectionMethod(method.lower()) if isinstance(method, str) else method
            )
        except ValueError as err:
            supported = [m.value for m in ChangeDetectionMethod]
            raise ChangeRegistryError(
                "UNSUPPORTED_CHANGE_METHOD",
                f"Change method '{method}' is not supported. Supported: {supported}",
                {"requested_method": str(method)},
            ) from err
        return SUPPORTED_CHANGE_METHODS[enum_method]

    @classmethod
    def get_all_method_definitions(cls) -> list[ChangeDetectionDefinition]:
        """Return list of all registered change detection method definitions."""
        return list(SUPPORTED_CHANGE_METHODS.values())
