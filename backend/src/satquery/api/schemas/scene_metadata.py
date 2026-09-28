from __future__ import annotations

from math import isfinite
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from satquery.api.schemas.catalog import (
    AcquisitionInterval,
    CatalogGeometry,
    ProviderIdentity,
)
from satquery.api.schemas.viewer import StrictViewerModel, ViewerSceneIdentity

SCENE_METADATA_SCHEMA_VERSION: Literal["1.0"] = "1.0"

ProductMaturity = Literal[
    "operational",
    "provisional",
    "near_real_time",
    "reprocessed",
    "research",
    "unknown",
]
SceneModality = Literal["optical", "sar"]
CombinationKind = Literal["optical_pair", "sar_pair", "optical_sar_pair"]
UnavailableField = Literal[
    "mission",
    "acquisition",
    "footprint",
    "native_resolution",
    "crs",
    "processing_level",
    "product_maturity",
    "calibration",
    "valid_data_mask",
    "optical_bands",
    "polarizations",
]


def _finite(value: float, name: str) -> float:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


class NativeResolution(StrictViewerModel):
    x_metres: float = Field(gt=0, strict=True)
    y_metres: float = Field(gt=0, strict=True)
    source_field: str = Field(min_length=1, max_length=256)

    @field_validator("x_metres", "y_metres")
    @classmethod
    def require_finite_resolution(cls, value: float) -> float:
        return _finite(value, "native resolution")


class SceneCrs(StrictViewerModel):
    identifier: str = Field(
        min_length=3,
        max_length=80,
        pattern=r"^[A-Z][A-Z0-9._-]*:[A-Za-z0-9._-]+$",
    )
    axis_units: Literal["metre", "degree", "unknown"]
    source_field: str = Field(min_length=1, max_length=256)


class ScaleOffsetCalibration(StrictViewerModel):
    source_values: Literal["uncalibrated"]
    method: Literal["scale_offset"]
    scale: float
    offset: float
    input_units: str = Field(min_length=1, max_length=80)
    output_units: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=1, max_length=1000)

    @field_validator("scale", "offset")
    @classmethod
    def require_finite_coefficient(cls, value: float) -> float:
        return _finite(value, "calibration coefficient")


class ProviderAlgorithmCalibration(StrictViewerModel):
    source_values: Literal["uncalibrated"]
    method: Literal["provider_algorithm"]
    algorithm: str = Field(min_length=1, max_length=160)
    algorithm_version: str | None = Field(default=None, min_length=1, max_length=160)
    input_units: str = Field(min_length=1, max_length=80)
    output_units: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=1, max_length=1000)


class AlreadyCalibrated(StrictViewerModel):
    source_values: Literal["calibrated"]
    method: Literal["identity"]
    units: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=1, max_length=1000)


class UnavailableCalibration(StrictViewerModel):
    source_values: Literal["unknown"]
    method: Literal["unavailable"]
    reason: str = Field(min_length=1, max_length=1000)


CalibrationMetadata = Annotated[
    ScaleOffsetCalibration
    | ProviderAlgorithmCalibration
    | AlreadyCalibrated
    | UnavailableCalibration,
    Field(discriminator="method"),
]


class AvailableValidDataMask(StrictViewerModel):
    state: Literal["available"]
    source_role: str = Field(min_length=1, max_length=160)
    convention: Literal["gdal_valid_nonzero", "categorical_quality", "finite_not_nodata"]
    valid_values: list[int] = Field(default_factory=list, max_length=256)
    explanation: str = Field(min_length=1, max_length=1000)

    @field_validator("valid_values")
    @classmethod
    def require_unique_byte_values(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("valid mask values must be unique")
        if any(item < 0 or item > 255 for item in value):
            raise ValueError("valid mask values must be bytes")
        return value

    @model_validator(mode="after")
    def validate_convention(self) -> Self:
        if self.convention == "categorical_quality" and not self.valid_values:
            raise ValueError("categorical quality masks require valid_values")
        if self.convention != "categorical_quality" and self.valid_values:
            raise ValueError("only categorical quality masks may declare valid_values")
        return self


class UnavailableValidDataMask(StrictViewerModel):
    state: Literal["unavailable"]
    reason: str = Field(min_length=1, max_length=1000)


ValidDataMaskMetadata = Annotated[
    AvailableValidDataMask | UnavailableValidDataMask,
    Field(discriminator="state"),
]


class OpticalBandMetadata(StrictViewerModel):
    band_id: str = Field(min_length=1, max_length=160)
    common_name: str | None = Field(default=None, min_length=1, max_length=80)
    native_resolution_metres: float = Field(gt=0, strict=True)
    units: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("native_resolution_metres")
    @classmethod
    def require_finite_resolution(cls, value: float) -> float:
        return _finite(value, "band native resolution")


class SarPolarizationMetadata(StrictViewerModel):
    polarization: Literal["HH", "HV", "VH", "VV", "RR", "RL", "LR", "LL"]
    native_resolution_metres: float = Field(gt=0, strict=True)
    units: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("native_resolution_metres")
    @classmethod
    def require_finite_resolution(cls, value: float) -> float:
        return _finite(value, "polarization native resolution")


class BaseSceneMetadata(StrictViewerModel):
    source: ViewerSceneIdentity
    source_version: str | None = Field(default=None, min_length=1, max_length=256)
    provider: ProviderIdentity
    mission: str = Field(min_length=1, max_length=160)
    acquisition: AcquisitionInterval
    footprint: CatalogGeometry
    native_resolution: NativeResolution
    crs: SceneCrs
    processing_level: str = Field(min_length=1, max_length=160)
    product_maturity: ProductMaturity
    calibration: CalibrationMetadata
    valid_data_mask: ValidDataMaskMetadata

    @model_validator(mode="after")
    def bind_provider_to_source(self) -> Self:
        if self.provider.id != self.source.provider:
            raise ValueError("metadata provider must match the stable source provider")
        return self


class OpticalSceneMetadata(BaseSceneMetadata):
    modality: Literal["optical"]
    optical_bands: list[OpticalBandMetadata] = Field(min_length=1, max_length=256)

    @field_validator("optical_bands")
    @classmethod
    def require_unique_bands(cls, value: list[OpticalBandMetadata]) -> list[OpticalBandMetadata]:
        band_ids = [item.band_id for item in value]
        if len(band_ids) != len(set(band_ids)):
            raise ValueError("optical band identifiers must be unique")
        common_names = [item.common_name for item in value if item.common_name is not None]
        if len(common_names) != len(set(common_names)):
            raise ValueError("known optical common names must be unique")
        return value


class SarSceneMetadata(BaseSceneMetadata):
    modality: Literal["sar"]
    polarizations: list[SarPolarizationMetadata] = Field(min_length=1, max_length=8)

    @field_validator("polarizations")
    @classmethod
    def require_unique_polarizations(
        cls, value: list[SarPolarizationMetadata]
    ) -> list[SarPolarizationMetadata]:
        labels = [item.polarization for item in value]
        if len(labels) != len(set(labels)):
            raise ValueError("SAR polarizations must be unique")
        return value


SceneMetadata = Annotated[
    OpticalSceneMetadata | SarSceneMetadata,
    Field(discriminator="modality"),
]


class AvailableSceneMetadata(StrictViewerModel):
    state: Literal["available"]
    metadata: SceneMetadata


class UnavailableSceneMetadata(StrictViewerModel):
    state: Literal["unavailable"]
    source: ViewerSceneIdentity
    provider: ProviderIdentity
    expected_modality: Literal["optical", "sar", "unknown"]
    reason_code: Literal[
        "provider_not_supported",
        "collection_not_supported",
        "source_not_found",
        "metadata_incomplete",
        "access_denied",
        "transient_provider_failure",
    ]
    missing_fields: list[UnavailableField] = Field(default_factory=list, max_length=32)
    retryable: bool
    reason: str = Field(min_length=1, max_length=1000)
    corrective_action: str = Field(min_length=1, max_length=1000)

    @field_validator("missing_fields")
    @classmethod
    def require_unique_missing_fields(cls, value: list[UnavailableField]) -> list[UnavailableField]:
        if len(value) != len(set(value)):
            raise ValueError("missing metadata fields must be unique")
        return value

    @model_validator(mode="after")
    def validate_unavailable_outcome(self) -> Self:
        if self.provider.id != self.source.provider:
            raise ValueError("unavailable metadata provider must match the stable source provider")
        if self.retryable != (self.reason_code == "transient_provider_failure"):
            raise ValueError("only transient provider failures are retryable")
        if self.reason_code == "metadata_incomplete" and not self.missing_fields:
            raise ValueError("incomplete metadata must identify missing fields")
        return self


SceneMetadataOutcome = Annotated[
    AvailableSceneMetadata | UnavailableSceneMetadata,
    Field(discriminator="state"),
]


class SceneMetadataResponse(StrictViewerModel):
    schema_version: Literal["1.0"] = SCENE_METADATA_SCHEMA_VERSION
    outcome: SceneMetadataOutcome


class SceneCombinationMember(StrictViewerModel):
    source: ViewerSceneIdentity
    modality: SceneModality


class SupportedSceneCombination(StrictViewerModel):
    state: Literal["supported"]
    combination: CombinationKind
    members: list[SceneCombinationMember] = Field(min_length=2, max_length=2)
    policy_version: str = Field(min_length=1, max_length=160)
    explanation: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_supported_combination(self) -> Self:
        _validate_combination_members(self.members, self.combination)
        return self


class UnsupportedSceneCombination(StrictViewerModel):
    state: Literal["unsupported"]
    combination: CombinationKind
    members: list[SceneCombinationMember] = Field(min_length=2, max_length=2)
    reason_code: Literal[
        "modality_not_supported",
        "mission_not_supported",
        "processing_level_incompatible",
        "calibration_unavailable",
        "valid_mask_unavailable",
        "polarization_incompatible",
        "optical_bands_incompatible",
        "product_maturity_incompatible",
        "temporal_order_invalid",
        "spatial_overlap_unavailable",
    ]
    reason: str = Field(min_length=1, max_length=1000)
    corrective_action: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_unsupported_combination(self) -> Self:
        _validate_combination_members(self.members, self.combination)
        return self


def _validate_combination_members(
    members: list[SceneCombinationMember], combination: CombinationKind
) -> None:
    source_keys = [member.source.model_dump_json() for member in members]
    if len(source_keys) != len(set(source_keys)):
        raise ValueError("scene combinations require two distinct source identifiers")
    expected_modalities = {
        "optical_pair": ["optical", "optical"],
        "sar_pair": ["sar", "sar"],
        "optical_sar_pair": ["optical", "sar"],
    }
    if [member.modality for member in members] != expected_modalities[combination]:
        raise ValueError("scene member modalities must match the declared combination order")


SceneCombinationOutcome = Annotated[
    SupportedSceneCombination | UnsupportedSceneCombination,
    Field(discriminator="state"),
]


class SceneCombinationResponse(StrictViewerModel):
    schema_version: Literal["1.0"] = SCENE_METADATA_SCHEMA_VERSION
    outcome: SceneCombinationOutcome
