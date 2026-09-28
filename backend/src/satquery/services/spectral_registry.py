"""Registry for scientifically defensible spectral indices, band mappings, and color ramps."""

from __future__ import annotations

from typing import Any

from satquery.api.schemas.spectral import (
    SpectralIndexDefinition,
    SpectralIndexName,
)


class SpectralRegistryError(Exception):
    """Exception raised when an index is unsupported or required bands are missing."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


# Canonical role aliases per satellite provider/collection
BAND_ROLE_ALIASES: dict[str, list[str]] = {
    "blue": ["b02", "b2", "blue", "band2", "b02_10m", "band02"],
    "green": ["b03", "b3", "green", "band3", "b03_10m", "band03"],
    "red": ["b04", "b4", "red", "band4", "b04_10m", "band04"],
    "nir": ["b08", "b8", "nir", "band8", "b08_10m", "band08", "b8a", "b08a"],
    "swir1": ["b11", "swir1", "swir", "band11", "b11_20m", "band11_20m", "b11_10m"],
    "swir2": ["b12", "swir2", "band12", "b12_20m", "band12_20m", "b12_10m"],
    "quality_mask": ["scl", "qa60", "quality", "mask", "quality_mask"],
    "cloud_mask": ["cloud", "cloud_mask", "cld", "cldprb"],
}

SUPPORTED_SPECTRAL_INDICES: dict[SpectralIndexName, SpectralIndexDefinition] = {
    SpectralIndexName.NDVI: SpectralIndexDefinition(
        name=SpectralIndexName.NDVI,
        display_name="Normalized Difference Vegetation Index (NDVI)",
        formula="(NIR - RED) / (NIR + RED)",
        required_bands=["nir", "red"],
        expected_range=(-1.0, 1.0),
        description=(
            "Measures relative green vegetation density and canopy vigor based on "
            "chlorophyll red light absorption and mesophyll near-infrared reflectance."
        ),
        limitations=(
            "Sensitive to atmospheric aerosol, soil brightness, and cloud shadows. High NDVI "
            "indicates vegetation response but does not identify species or canopy structure."
        ),
        default_color_ramp="RdYlGn",
        version="1.0.0",
    ),
    SpectralIndexName.NDWI: SpectralIndexDefinition(
        name=SpectralIndexName.NDWI,
        display_name="Normalized Difference Water Index (NDWI - McFeeters 1996)",
        formula="(GREEN - NIR) / (GREEN + NIR)",
        required_bands=["green", "nir"],
        expected_range=(-1.0, 1.0),
        description=(
            "Delineates open water features while suppressing terrestrial vegetation and soil "
            "features using the McFeeters (1996) green and near-infrared formulation."
        ),
        limitations=(
            "Built-up surfaces, asphalt, and topographic or cloud shadows can yield positive "
            "values leading to false-positive water detections."
        ),
        default_color_ramp="YlGnBu",
        version="1.0.0",
    ),
    SpectralIndexName.NDBI: SpectralIndexDefinition(
        name=SpectralIndexName.NDBI,
        display_name="Normalized Difference Built-up Index (NDBI)",
        formula="(SWIR1 - NIR) / (SWIR1 + NIR)",
        required_bands=["swir1", "nir"],
        expected_range=(-1.0, 1.0),
        description=(
            "Highlights built-up and impervious surface spectral response by exploiting higher "
            "reflectance in the shortwave-infrared (SWIR1) relative to near-infrared (NIR)."
        ),
        limitations=(
            "Dry bare soil, fallow agricultural parcels, and sandy surfaces have similar SWIR/NIR "
            "ratios. Positive NDBI alone does not prove construction or building presence."
        ),
        default_color_ramp="YlOrRd",
        version="1.0.0",
    ),
    SpectralIndexName.EVI: SpectralIndexDefinition(
        name=SpectralIndexName.EVI,
        display_name="Enhanced Vegetation Index (EVI)",
        formula="2.5 * (NIR - RED) / (NIR + 6.0 * RED - 7.5 * BLUE + 1.0)",
        required_bands=["nir", "red", "blue"],
        expected_range=(-1.0, 1.0),
        description=(
            "Optimizes the vegetation signal with improved sensitivity in high biomass regions "
            "and decouples the canopy background signal using the blue band for aerosol resistance."
        ),
        limitations=(
            "Requires an accurate blue surface reflectance band; susceptible to "
            "blue-band calibration errors or atmospheric residual over water and shadows."
        ),
        default_color_ramp="YlGn",
        version="1.0.0",
    ),
    SpectralIndexName.SAVI: SpectralIndexDefinition(
        name=SpectralIndexName.SAVI,
        display_name="Soil-Adjusted Vegetation Index (SAVI)",
        formula="((NIR - RED) / (NIR + RED + 0.5)) * 1.5",
        required_bands=["nir", "red"],
        expected_range=(-1.0, 1.0),
        description=(
            "Corrects NDVI for the influence of soil brightness in sparse vegetation canopies "
            "using a standardized soil adjustment factor L = 0.5."
        ),
        limitations=(
            "Fixed L = 0.5 is optimal for intermediate vegetation density (~50%); "
            "high canopy cover converges to NDVI response."
        ),
        default_color_ramp="RdYlGn",
        version="1.0.0",
    ),
    SpectralIndexName.MNDWI: SpectralIndexDefinition(
        name=SpectralIndexName.MNDWI,
        display_name="Modified Normalized Difference Water Index (MNDWI - Xu 2006)",
        formula="(GREEN - SWIR1) / (GREEN + SWIR1)",
        required_bands=["green", "swir1"],
        expected_range=(-1.0, 1.0),
        description=(
            "Enhances open water features while significantly suppressing built-up land noise by "
            "substituting shortwave-infrared (SWIR1) for near-infrared (Xu 2006 formulation)."
        ),
        limitations=(
            "May still exhibit confusion over dark shadow areas in steep terrain "
            "or high-relief urban canyons."
        ),
        default_color_ramp="YlGnBu",
        version="1.0.0",
    ),
}


class SpectralRegistry:
    """Registry providing metadata, validation, and band mapping for spectral indices."""

    @classmethod
    def get_index_definition(cls, name: SpectralIndexName | str) -> SpectralIndexDefinition:
        """Retrieve definition for a specific spectral index."""
        try:
            enum_name = SpectralIndexName(name.lower()) if isinstance(name, str) else name
        except ValueError as err:
            supported = [idx.value for idx in SpectralIndexName]
            raise SpectralRegistryError(
                "UNSUPPORTED_INDEX",
                f"Spectral index '{name}' is not supported. Supported: {supported}",
                {"requested_index": str(name)},
            ) from err
        return SUPPORTED_SPECTRAL_INDICES[enum_name]

    @classmethod
    def get_all_index_definitions(cls) -> list[SpectralIndexDefinition]:
        """Return list of all registered spectral index definitions."""
        return list(SUPPORTED_SPECTRAL_INDICES.values())

    @classmethod
    def resolve_band_indices(
        cls,
        available_band_names: list[str],
        required_roles: list[str],
        collection: str | None = None,
    ) -> dict[str, int]:
        """Map canonical roles (e.g. 'nir', 'red') to 0-indexed raster band positions.

        Args:
            available_band_names: List of band descriptions/names from the dataset.
            required_roles: Canonical band roles needed by the formula.
            collection: Optional STAC collection identifier for domain matching.

        Returns:
            Dict mapping role string to integer 0-indexed band slice position.

        Raises:
            SpectralRegistryError: If any required band role cannot be resolved.
        """
        normalized_available = [b.lower().strip() for b in available_band_names]
        resolved: dict[str, int] = {}
        missing_roles: list[str] = []

        for role in required_roles:
            role_key = role.lower().strip()
            aliases = BAND_ROLE_ALIASES.get(role_key, [role_key])
            found_idx: int | None = None

            for alias in aliases:
                for idx, band_name in enumerate(normalized_available):
                    if band_name == alias or alias in band_name:
                        found_idx = idx
                        break
                if found_idx is not None:
                    break

            if found_idx is not None:
                resolved[role_key] = found_idx
            else:
                missing_roles.append(role)

        if missing_roles:
            raise SpectralRegistryError(
                "REQUIRED_BAND_MISSING",
                (
                    f"Required band role(s) {missing_roles} missing from dataset bands: "
                    f"{available_band_names}. Check collection compatibility."
                ),
                {
                    "missing_roles": missing_roles,
                    "available_bands": available_band_names,
                    "collection": collection,
                },
            )

        return resolved
