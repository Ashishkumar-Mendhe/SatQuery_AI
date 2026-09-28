from __future__ import annotations

from datetime import UTC, datetime
from math import isclose, isfinite
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, StrictBool, StrictFloat, StrictInt, field_validator, model_validator

from satquery.api.schemas.catalog import CatalogGeometry
from satquery.api.schemas.processing import (
    ArtifactReference,
    OutputGrid,
    ProcessingIdentifier,
    Sha256Digest,
    SoftwareVersion,
)
from satquery.api.schemas.viewer import StrictViewerModel, ViewerSceneIdentity

CHANGE_RESULT_SCHEMA_VERSION: Literal["1.1"] = "1.1"
ChangeParameterValue = StrictBool | StrictInt | StrictFloat | str


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return value.astimezone(UTC)


class ChangeSourceScene(StrictViewerModel):
    temporal_role: Literal["before", "after"]
    scene: ViewerSceneIdentity
    acquired_at: datetime

    @field_validator("acquired_at")
    @classmethod
    def normalize_acquisition(cls, value: datetime) -> datetime:
        return _as_utc(value, "acquired_at")


class ChangeParameter(StrictViewerModel):
    name: ProcessingIdentifier
    value: ChangeParameterValue
    units: str | None = Field(default=None, min_length=1, max_length=80)
    explanation: str = Field(min_length=1, max_length=500)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: ChangeParameterValue) -> ChangeParameterValue:
        if isinstance(value, float) and not isfinite(value):
            raise ValueError("numeric change parameters must be finite")
        if isinstance(value, str) and (not value or len(value) > 500):
            raise ValueError("text change parameters must contain 1 to 500 characters")
        return value


class ChangeProcessingParameters(StrictViewerModel):
    preparation_job_id: UUID
    preparation_profile: Literal["sentinel-2-l2a-surface-reflectance-v1"]
    algorithm: ProcessingIdentifier
    algorithm_version: str = Field(min_length=1, max_length=160)
    required_band_roles: list[ProcessingIdentifier] = Field(min_length=1, max_length=16)
    output_grid: OutputGrid
    radiometric_harmonization: Literal["none"] = "none"
    registration_input: Literal["phase6_effective_pair"] = "phase6_effective_pair"
    unknown_pixel_policy: Literal["outside_joint_usable_or_unresolved_quality"] = (
        "outside_joint_usable_or_unresolved_quality"
    )
    parameters: list[ChangeParameter] = Field(default_factory=list, max_length=64)
    parameters_digest_sha256: Sha256Digest

    @model_validator(mode="after")
    def require_unique_parameters(self) -> Self:
        if len(self.required_band_roles) != len(set(self.required_band_roles)):
            raise ValueError("required change band roles must be unique")
        names = [parameter.name for parameter in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("change parameter names must be unique")
        return self


class ChangeCoverage(StrictViewerModel):
    denominator: Literal["inside_aoi"] = "inside_aoi"
    aoi_pixel_count: int = Field(gt=0, strict=True)
    joint_valid_pixel_count: int = Field(ge=0, strict=True)
    valid_fraction_of_aoi: float = Field(ge=0, le=1, strict=True)
    joint_valid_area_square_metres: float = Field(ge=0, strict=True)
    joint_usable_pixel_count: int = Field(ge=0, strict=True)
    usable_fraction_of_aoi: float = Field(ge=0, le=1, strict=True)
    joint_usable_area_square_metres: float = Field(ge=0, strict=True)
    pixel_area_square_metres: float = Field(gt=0, strict=True)
    area_method: Literal["projected_grid_cell_count"] = "projected_grid_cell_count"
    area_method_explanation: str = Field(min_length=1, max_length=1000)

    @field_validator(
        "valid_fraction_of_aoi",
        "joint_valid_area_square_metres",
        "usable_fraction_of_aoi",
        "joint_usable_area_square_metres",
        "pixel_area_square_metres",
    )
    @classmethod
    def require_finite_measurement(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("coverage measurements must be finite")
        return value

    @model_validator(mode="after")
    def validate_coverage_math(self) -> Self:
        if self.joint_valid_pixel_count > self.aoi_pixel_count:
            raise ValueError("joint valid pixels must not exceed inside-AOI pixels")
        if self.joint_usable_pixel_count > self.joint_valid_pixel_count:
            raise ValueError("joint usable pixels must not exceed joint valid pixels")
        expected_fraction = self.joint_valid_pixel_count / self.aoi_pixel_count
        if not isclose(self.valid_fraction_of_aoi, expected_fraction, abs_tol=1e-12):
            raise ValueError("valid AOI fraction must match the declared pixel counts")
        expected_area = self.joint_valid_pixel_count * self.pixel_area_square_metres
        if not isclose(
            self.joint_valid_area_square_metres,
            expected_area,
            rel_tol=1e-12,
            abs_tol=1e-6,
        ):
            raise ValueError("joint valid area must match the projected grid-cell count")
        expected_usable_fraction = self.joint_usable_pixel_count / self.aoi_pixel_count
        if not isclose(self.usable_fraction_of_aoi, expected_usable_fraction, abs_tol=1e-12):
            raise ValueError("usable AOI fraction must match the declared pixel counts")
        expected_usable_area = self.joint_usable_pixel_count * self.pixel_area_square_metres
        if not isclose(
            self.joint_usable_area_square_metres,
            expected_usable_area,
            rel_tol=1e-12,
            abs_tol=1e-6,
        ):
            raise ValueError("joint usable area must match the projected grid-cell count")
        return self


class ChangeClassMeasurement(StrictViewerModel):
    classification: Literal["unchanged", "changed", "unknown"]
    raster_value: int = Field(ge=0, le=255, strict=True)
    pixel_count: int = Field(ge=0, strict=True)
    area_square_metres: float = Field(ge=0, strict=True)
    fraction_of_aoi: float = Field(ge=0, le=1, strict=True)
    fraction_of_joint_valid: float | None = Field(default=None, ge=0, le=1, strict=True)
    fraction_of_joint_usable: float | None = Field(default=None, ge=0, le=1, strict=True)
    explanation: str = Field(min_length=1, max_length=1000)

    @field_validator(
        "area_square_metres",
        "fraction_of_aoi",
        "fraction_of_joint_valid",
        "fraction_of_joint_usable",
    )
    @classmethod
    def require_finite_area(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(value):
            raise ValueError("change class measurements must be finite")
        return value

    @model_validator(mode="after")
    def validate_class_encoding(self) -> Self:
        expected_values = {"unchanged": 0, "changed": 1, "unknown": 255}
        if self.raster_value != expected_values[self.classification]:
            raise ValueError("change class raster value does not match its fixed meaning")
        if self.classification == "unknown" and (
            self.fraction_of_joint_valid is not None or self.fraction_of_joint_usable is not None
        ):
            raise ValueError("unknown pixels have no observed or usable class fraction")
        return self


class ChangeQualityWarning(StrictViewerModel):
    warning_id: ProcessingIdentifier
    state: Literal["warning", "unknown"]
    source_check_ids: list[ProcessingIdentifier] = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=1000)
    corrective_action: str = Field(min_length=1, max_length=1000)

    @field_validator("source_check_ids")
    @classmethod
    def require_unique_checks(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("quality warning source checks must be unique")
        return value


class PreparedSceneChangeEvidence(StrictViewerModel):
    scene: ViewerSceneIdentity
    prepared_raster_artifact_id: UUID
    prepared_raster_checksum_sha256: Sha256Digest
    validity_mask_checksum_sha256: Sha256Digest
    quality_mask_checksums_sha256: list[Sha256Digest] = Field(min_length=1, max_length=16)


class ChangeProvenance(StrictViewerModel):
    preparation_job_id: UUID
    preparation_manifest_artifact_id: UUID
    preparation_manifest_checksum_sha256: Sha256Digest
    prepared_scenes: list[PreparedSceneChangeEvidence] = Field(min_length=2, max_length=2)
    parameters_digest_sha256: Sha256Digest
    software: list[SoftwareVersion] = Field(min_length=1, max_length=32)
    started_at: datetime
    finished_at: datetime

    @field_validator("started_at", "finished_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime, info: object) -> datetime:
        return _as_utc(value, str(getattr(info, "field_name", "change timestamp")))

    @model_validator(mode="after")
    def validate_provenance(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("change processing finished_at must not precede started_at")
        scene_keys = [item.scene.model_dump_json() for item in self.prepared_scenes]
        if len(scene_keys) != len(set(scene_keys)):
            raise ValueError("change provenance requires two distinct prepared scenes")
        software_names = [item.name for item in self.software]
        if len(software_names) != len(set(software_names)):
            raise ValueError("change provenance software names must be unique")
        return self


class TwoDateChangeResult(StrictViewerModel):
    schema_version: Literal["1.1"] = CHANGE_RESULT_SCHEMA_VERSION
    result_id: UUID
    state: Literal["complete", "limited"]
    sources: list[ChangeSourceScene] = Field(min_length=2, max_length=2)
    aoi: CatalogGeometry
    processing: ChangeProcessingParameters
    coverage: ChangeCoverage
    classes: list[ChangeClassMeasurement] = Field(min_length=3, max_length=3)
    quality_warnings: list[ChangeQualityWarning] = Field(default_factory=list, max_length=100)
    classification_artifact: ArtifactReference
    provenance: ChangeProvenance

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        roles = {source.temporal_role: source for source in self.sources}
        if set(roles) != {"before", "after"} or len(roles) != len(self.sources):
            raise ValueError("change result requires exactly one before and one after scene")
        before = roles["before"]
        after = roles["after"]
        if before.scene == after.scene:
            raise ValueError("change result source scenes must be distinct")
        if before.acquired_at >= after.acquired_at:
            raise ValueError("before acquisition must precede after acquisition")
        if (before.scene.provider, before.scene.collection) != (
            after.scene.provider,
            after.scene.collection,
        ):
            raise ValueError("the initial change contract requires one provider and collection")

        classes = {item.classification: item for item in self.classes}
        expected_classes = {"unchanged", "changed", "unknown"}
        if set(classes) != expected_classes or len(classes) != len(self.classes):
            raise ValueError("change measurements require changed, unchanged, and unknown classes")
        usable_pixels = classes["changed"].pixel_count + classes["unchanged"].pixel_count
        if usable_pixels != self.coverage.joint_usable_pixel_count:
            raise ValueError("changed plus unchanged pixels must equal joint usable pixels")
        if classes["unknown"].pixel_count != (
            self.coverage.aoi_pixel_count - self.coverage.joint_usable_pixel_count
        ):
            raise ValueError("unknown pixels must equal the non-joint-usable AOI remainder")
        for measurement in self.classes:
            expected_area = measurement.pixel_count * self.coverage.pixel_area_square_metres
            if not isclose(
                measurement.area_square_metres,
                expected_area,
                rel_tol=1e-12,
                abs_tol=1e-6,
            ):
                raise ValueError("class area must match its projected grid-cell count")
            expected_aoi_fraction = measurement.pixel_count / self.coverage.aoi_pixel_count
            if not isclose(measurement.fraction_of_aoi, expected_aoi_fraction, abs_tol=1e-12):
                raise ValueError("class AOI fraction must match its pixel count")
            if measurement.classification != "unknown":
                expected_valid_fraction = (
                    measurement.pixel_count / self.coverage.joint_valid_pixel_count
                    if self.coverage.joint_valid_pixel_count
                    else None
                )
                if expected_valid_fraction is None:
                    if measurement.fraction_of_joint_valid is not None:
                        raise ValueError("zero observed coverage requires null observed fractions")
                elif measurement.fraction_of_joint_valid is None or not isclose(
                    measurement.fraction_of_joint_valid,
                    expected_valid_fraction,
                    abs_tol=1e-12,
                ):
                    raise ValueError("class observed fraction must use joint-valid pixels")
                expected_usable_fraction = (
                    measurement.pixel_count / self.coverage.joint_usable_pixel_count
                    if self.coverage.joint_usable_pixel_count
                    else None
                )
                if expected_usable_fraction is None:
                    if measurement.fraction_of_joint_usable is not None:
                        raise ValueError(
                            "zero usable coverage requires null usable-class fractions"
                        )
                elif measurement.fraction_of_joint_usable is None or not isclose(
                    measurement.fraction_of_joint_usable,
                    expected_usable_fraction,
                    abs_tol=1e-12,
                ):
                    raise ValueError("class usable fraction must match its pixel count")

        warning_ids = [warning.warning_id for warning in self.quality_warnings]
        if len(warning_ids) != len(set(warning_ids)):
            raise ValueError("change quality warning identifiers must be unique")
        if any(warning.state == "unknown" for warning in self.quality_warnings):
            if self.state != "limited":
                raise ValueError("unknown quality evidence requires a limited change result")
        if self.classification_artifact.kind != "change_classification":
            raise ValueError("change result requires a change_classification artifact")
        if self.classification_artifact.access.state != "available":
            raise ValueError("change result requires an available committed classification")
        if self.provenance.preparation_job_id != self.processing.preparation_job_id:
            raise ValueError("change provenance must reference the processing preparation job")
        if self.provenance.parameters_digest_sha256 != self.processing.parameters_digest_sha256:
            raise ValueError("change provenance must bind the processing parameters digest")
        source_scenes = {source.scene.model_dump_json() for source in self.sources}
        provenance_scenes = {
            source.scene.model_dump_json() for source in self.provenance.prepared_scenes
        }
        if source_scenes != provenance_scenes:
            raise ValueError("change provenance prepared scenes must match the result sources")
        return self


class ChangeAreaApiSummary(StrictViewerModel):
    pixel_area_square_metres: float = Field(gt=0, strict=True)
    aoi_pixel_count: int = Field(gt=0, strict=True)
    aoi_area_square_metres: float = Field(gt=0, strict=True)
    joint_valid_pixel_count: int = Field(gt=0, strict=True)
    joint_valid_observed_area_square_metres: float = Field(gt=0, strict=True)
    observed_coverage_percent_of_aoi: float = Field(ge=0, le=100, strict=True)
    joint_usable_pixel_count: int = Field(ge=0, strict=True)
    joint_usable_area_square_metres: float = Field(ge=0, strict=True)
    usable_coverage_percent_of_aoi: float = Field(ge=0, le=100, strict=True)
    changed_pixel_count: int = Field(ge=0, strict=True)
    changed_area_square_metres: float = Field(ge=0, strict=True)
    changed_percent_of_joint_valid_observed_area: float = Field(ge=0, le=100, strict=True)
    unchanged_pixel_count: int = Field(ge=0, strict=True)
    unchanged_area_square_metres: float = Field(ge=0, strict=True)
    unknown_pixel_count: int = Field(ge=0, strict=True)
    unknown_area_square_metres: float = Field(ge=0, strict=True)
    unknown_percent_of_aoi: float = Field(ge=0, le=100, strict=True)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.changed_pixel_count + self.unchanged_pixel_count != self.joint_usable_pixel_count:
            raise ValueError("changed plus unchanged must equal joint-usable pixels")
        if self.unknown_pixel_count != self.aoi_pixel_count - self.joint_usable_pixel_count:
            raise ValueError("unknown must equal the non-joint-usable AOI remainder")
        return self


class ChangeApiWarning(StrictViewerModel):
    code: ProcessingIdentifier
    statement: str = Field(min_length=1, max_length=1000)


class ChangeAnalysisApiResult(StrictViewerModel):
    """Persisted 8E view of the computed 8C/8D result; never model-generated."""

    schema_version: Literal["1.0"] = "1.0"
    job_id: UUID
    sources: list[ChangeSourceScene] = Field(min_length=2, max_length=2)
    aoi: CatalogGeometry
    grid: OutputGrid
    method: ProcessingIdentifier
    method_version: str = Field(min_length=1, max_length=160)
    threshold: float = Field(gt=0, strict=True)
    threshold_units: str = Field(min_length=1, max_length=160)
    area: ChangeAreaApiSummary
    alignment_statement: str = Field(min_length=1, max_length=1000)
    warnings: list[ChangeApiWarning] = Field(default_factory=list, max_length=100)
    statements: list[str] = Field(min_length=1, max_length=20)
    cause_or_land_cover_category: Literal["not_determined"]
    classification_artifact_id: UUID
    processing_version: str = Field(min_length=1, max_length=160)
