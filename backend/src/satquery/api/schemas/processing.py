from __future__ import annotations

from datetime import UTC, datetime
from math import isclose, isfinite
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from satquery.api.schemas.catalog import CatalogGeometry
from satquery.api.schemas.viewer import (
    ResolvedImageryAssetIdentity,
    StrictViewerModel,
    ViewerSceneIdentity,
)

PROCESSING_SCHEMA_VERSION: Literal["1.0"] = "1.0"
SUPPORTED_PROCESSING_PROVIDER = "earth-search"
SUPPORTED_PROCESSING_COLLECTION = "sentinel-2-c1-l2a"
MAX_OUTPUT_PIXELS = 100_000_000

ProcessingIdentifier = Annotated[
    str,
    Field(min_length=1, max_length=160, pattern=r"^[a-z0-9][a-z0-9._-]*$"),
]
Sha256Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
type OutputBounds = tuple[float, float, float, float]
type AffineTransform = tuple[float, float, float, float, float, float]


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return value.astimezone(UTC)


def _finite(value: float, field_name: str) -> float:
    if not isfinite(value):
        raise ValueError(f"{field_name} must be finite")
    return value


class RequiredBand(StrictViewerModel):
    role: ProcessingIdentifier
    common_name: Literal["red", "green", "blue", "nir"]


class ProcessingOptions(StrictViewerModel):
    grid_policy: Literal["source_aligned", "common_utm"]
    target_resolution_metres: float = Field(gt=0, le=1000, strict=True)
    continuous_resampling: Literal["nearest", "bilinear", "cubic"]
    mask_resampling: Literal["nearest"] = "nearest"
    calibration: Literal["source_metadata"] = "source_metadata"
    clip_to_aoi: Literal[True] = True
    preserve_originals: Literal[True] = True
    max_output_pixels: int = Field(
        default=MAX_OUTPUT_PIXELS,
        ge=1,
        le=MAX_OUTPUT_PIXELS,
        strict=True,
    )

    @field_validator("target_resolution_metres")
    @classmethod
    def require_finite_resolution(cls, value: float) -> float:
        return _finite(value, "target_resolution_metres")


class PreparationRequest(StrictViewerModel):
    schema_version: Literal["1.0"] = PROCESSING_SCHEMA_VERSION
    scenes: list[ViewerSceneIdentity] = Field(min_length=1, max_length=2)
    aoi: CatalogGeometry
    required_bands: list[RequiredBand] = Field(min_length=1, max_length=16)
    intended_task: Literal["optical_single_scene", "optical_pair"]
    processing_profile: Literal["sentinel-2-l2a-surface-reflectance-v1"]
    options: ProcessingOptions

    @model_validator(mode="after")
    def validate_supported_request(self) -> Self:
        scene_keys = [scene.model_dump_json() for scene in self.scenes]
        if len(scene_keys) != len(set(scene_keys)):
            raise ValueError("preparation scenes must be distinct")
        expected_count = 1 if self.intended_task == "optical_single_scene" else 2
        if len(self.scenes) != expected_count:
            raise ValueError(f"{self.intended_task} requires exactly {expected_count} scene(s)")
        if any(
            scene.provider != SUPPORTED_PROCESSING_PROVIDER
            or scene.collection != SUPPORTED_PROCESSING_COLLECTION
            for scene in self.scenes
        ):
            raise ValueError(
                "the initial processing profile supports only earth-search / "
                "sentinel-2-c1-l2a scenes"
            )
        roles = [band.role for band in self.required_bands]
        common_names = [band.common_name for band in self.required_bands]
        if len(roles) != len(set(roles)):
            raise ValueError("required band roles must be unique")
        if len(common_names) != len(set(common_names)):
            raise ValueError("required band common names must be unique")
        return self


class OutputGrid(StrictViewerModel):
    crs: str = Field(pattern=r"^EPSG:(326|327)(0[1-9]|[1-5][0-9]|60)$")
    transform: AffineTransform
    width: int = Field(ge=1, le=100_000, strict=True)
    height: int = Field(ge=1, le=100_000, strict=True)
    resolution_metres: tuple[float, float]
    bounds: OutputBounds
    pixel_interpretation: Literal["area"] = "area"

    @field_validator("transform")
    @classmethod
    def validate_transform(cls, value: AffineTransform) -> AffineTransform:
        if not all(isfinite(number) for number in value):
            raise ValueError("output transform must contain finite numbers")
        x_scale, x_skew, _, y_skew, y_scale, _ = value
        if x_scale <= 0 or y_scale >= 0:
            raise ValueError("output transform must be north-up with positive x pixel size")
        if x_skew != 0 or y_skew != 0:
            raise ValueError("rotated or sheared output grids are not supported")
        return value

    @field_validator("resolution_metres")
    @classmethod
    def validate_resolution(cls, value: tuple[float, float]) -> tuple[float, float]:
        if not all(isfinite(number) and number > 0 for number in value):
            raise ValueError("output resolution must contain positive finite values")
        return value

    @field_validator("bounds")
    @classmethod
    def validate_bounds(cls, value: OutputBounds) -> OutputBounds:
        west, south, east, north = value
        if not all(isfinite(coordinate) for coordinate in value):
            raise ValueError("output bounds must contain finite coordinates")
        if not west < east or not south < north:
            raise ValueError("output bounds must be ordered west, south, east, north")
        return value

    @model_validator(mode="after")
    def validate_grid_consistency(self) -> Self:
        if self.width * self.height > MAX_OUTPUT_PIXELS:
            raise ValueError(f"output grid may contain at most {MAX_OUTPUT_PIXELS} pixels")
        x_scale, _, x_origin, _, y_scale, y_origin = self.transform
        x_resolution, y_resolution = self.resolution_metres
        west, south, east, north = self.bounds
        expected = (
            x_origin,
            y_origin + self.height * y_scale,
            x_origin + self.width * x_scale,
            y_origin,
        )
        if not isclose(x_scale, x_resolution) or not isclose(-y_scale, y_resolution):
            raise ValueError("output resolution must match the affine transform")
        if any(
            not isclose(actual, derived, rel_tol=1e-9, abs_tol=1e-6)
            for actual, derived in zip((west, south, east, north), expected, strict=True)
        ):
            raise ValueError("output bounds must match the affine transform and dimensions")
        return self


class ArtifactAccess(StrictViewerModel):
    state: Literal["available", "expired", "denied", "unavailable"]
    reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def require_failure_reason(self) -> Self:
        if self.state == "available" and self.reason is not None:
            raise ValueError("available artifact access must not include a failure reason")
        if self.state != "available" and self.reason is None:
            raise ValueError(f"artifact access state '{self.state}' requires a reason")
        return self


class ArtifactReference(StrictViewerModel):
    artifact_id: UUID
    kind: Literal[
        "prepared_raster",
        "validity_mask",
        "quality_mask",
        "provenance_manifest",
        "inference_evidence",
        "inference_chip",
        "change_classification",
        "optical_sar_evidence",
    ]
    media_type: Literal["image/tiff", "application/json", "image/png"]
    checksum_sha256: Sha256Digest
    byte_size: int = Field(ge=0, strict=True)
    access: ArtifactAccess

    @model_validator(mode="after")
    def validate_artifact_media_type(self) -> Self:
        expected = (
            "application/json"
            if self.kind in {"provenance_manifest", "inference_evidence", "optical_sar_evidence"}
            else "image/tiff"
        )
        if self.kind == "inference_chip":
            expected = "image/png"
        if self.media_type != expected:
            raise ValueError(f"artifact kind '{self.kind}' requires media type '{expected}'")
        return self


class MaskClass(StrictViewerModel):
    value: int = Field(ge=0, le=255, strict=True)
    label: ProcessingIdentifier
    explanation: str = Field(min_length=1, max_length=500)


class PreparedMask(StrictViewerModel):
    purpose: Literal["validity", "quality"]
    artifact: ArtifactReference
    classes: list[MaskClass] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_mask(self) -> Self:
        expected_kind = "validity_mask" if self.purpose == "validity" else "quality_mask"
        if self.artifact.kind != expected_kind:
            raise ValueError(f"{self.purpose} mask requires artifact kind '{expected_kind}'")
        if self.artifact.media_type != "image/tiff":
            raise ValueError("prepared masks require image/tiff artifacts")
        values = [item.value for item in self.classes]
        if len(values) != len(set(values)):
            raise ValueError("mask class values must be unique")
        if self.purpose == "validity" and set(values) != {0, 1}:
            raise ValueError("validity mask must define exactly classes 0 and 1")
        return self


class SourceCalibration(StrictViewerModel):
    calibration_id: ProcessingIdentifier
    source: ResolvedImageryAssetIdentity
    band_role: ProcessingIdentifier
    status: Literal["applied", "not_required", "unavailable"]
    method: Literal["metadata_scale_offset", "identity", "unavailable"]
    scale: float | None = None
    offset: float | None = None
    input_units: str | None = Field(default=None, min_length=1, max_length=80)
    output_units: str | None = Field(default=None, min_length=1, max_length=80)
    explanation: str = Field(min_length=1, max_length=1000)

    @field_validator("scale", "offset")
    @classmethod
    def require_finite_coefficients(cls, value: float | None) -> float | None:
        return None if value is None else _finite(value, "calibration coefficient")

    @model_validator(mode="after")
    def validate_calibration(self) -> Self:
        if self.status == "applied":
            if self.method != "metadata_scale_offset" or self.scale is None or self.offset is None:
                raise ValueError("applied calibration requires metadata scale and offset")
            if self.output_units is None:
                raise ValueError("applied calibration requires output_units")
        elif self.status == "not_required":
            if self.method != "identity" or self.scale is not None or self.offset is not None:
                raise ValueError("not-required calibration must use identity without coefficients")
        elif self.method != "unavailable" or self.scale is not None or self.offset is not None:
            raise ValueError("unavailable calibration must retain unknown coefficients")
        return self


class SourceInputProvenance(StrictViewerModel):
    asset: ResolvedImageryAssetIdentity
    checksum_sha256: Sha256Digest | None = None
    checksum_unavailable_reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def describe_checksum_availability(self) -> Self:
        if (self.checksum_sha256 is None) == (self.checksum_unavailable_reason is None):
            raise ValueError("source checksum requires either a digest or an unavailable reason")
        return self


class SoftwareVersion(StrictViewerModel):
    name: ProcessingIdentifier
    version: str = Field(min_length=1, max_length=160)


class ProcessingStep(StrictViewerModel):
    sequence: int = Field(ge=1, le=100, strict=True)
    operation: Literal["read", "calibrate", "reproject", "resample", "clip", "mask", "write"]
    method: str = Field(min_length=1, max_length=160)
    parameters_digest_sha256: Sha256Digest


class ProcessingProvenance(StrictViewerModel):
    processing_profile: Literal["sentinel-2-l2a-surface-reflectance-v1"]
    request_digest_sha256: Sha256Digest
    source_inputs: list[SourceInputProvenance] = Field(min_length=1, max_length=32)
    calibrations: list[SourceCalibration] = Field(min_length=1, max_length=32)
    steps: list[ProcessingStep] = Field(min_length=1, max_length=100)
    software: list[SoftwareVersion] = Field(min_length=1, max_length=32)
    started_at: datetime
    finished_at: datetime

    @field_validator("started_at", "finished_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime, info: object) -> datetime:
        field_name = getattr(info, "field_name", "processing timestamp")
        return _as_utc(value, field_name)

    @model_validator(mode="after")
    def validate_provenance(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("processing finished_at must not precede started_at")
        source_keys = [item.asset.model_dump_json() for item in self.source_inputs]
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("processing source inputs must be unique")
        calibration_ids = [item.calibration_id for item in self.calibrations]
        if len(calibration_ids) != len(set(calibration_ids)):
            raise ValueError("processing calibration identifiers must be unique")
        sequences = [step.sequence for step in self.steps]
        if sequences != list(range(1, len(sequences) + 1)):
            raise ValueError("processing step sequence must be contiguous from 1")
        software_names = [item.name for item in self.software]
        if len(software_names) != len(set(software_names)):
            raise ValueError("processing software names must be unique")
        return self


class PreparedBand(StrictViewerModel):
    role: ProcessingIdentifier
    source: ResolvedImageryAssetIdentity
    data_type: Literal["uint16", "int16", "float32", "float64"]
    units: str | None = Field(default=None, min_length=1, max_length=80)
    calibration_id: ProcessingIdentifier


class PreparedRaster(StrictViewerModel):
    scene: ViewerSceneIdentity
    artifact: ArtifactReference
    grid: OutputGrid
    bands: list[PreparedBand] = Field(min_length=1, max_length=32)
    validity_mask: PreparedMask
    quality_masks: list[PreparedMask] = Field(min_length=1, max_length=16)
    provenance: ProcessingProvenance

    @model_validator(mode="after")
    def validate_prepared_raster(self) -> Self:
        if self.artifact.kind != "prepared_raster" or self.artifact.media_type != "image/tiff":
            raise ValueError("prepared raster requires an image/tiff prepared_raster artifact")
        if self.validity_mask.purpose != "validity":
            raise ValueError("prepared raster requires a separate validity mask")
        if any(mask.purpose != "quality" for mask in self.quality_masks):
            raise ValueError("prepared raster quality_masks must contain only quality masks")
        roles = [band.role for band in self.bands]
        if len(roles) != len(set(roles)):
            raise ValueError("prepared raster band roles must be unique")
        if any(band.source.scene != self.scene for band in self.bands):
            raise ValueError("prepared raster bands must belong to its scene")
        calibration_ids = {item.calibration_id for item in self.provenance.calibrations}
        missing = sorted({band.calibration_id for band in self.bands} - calibration_ids)
        if missing:
            raise ValueError(f"prepared bands reference missing calibrations: {', '.join(missing)}")
        return self


class QualityThreshold(StrictViewerModel):
    operator: Literal["lt", "lte", "gt", "gte", "eq"]
    value: float
    units: str = Field(min_length=1, max_length=80)

    @field_validator("value")
    @classmethod
    def require_finite_value(cls, value: float) -> float:
        return _finite(value, "quality threshold")


class QualityCheck(StrictViewerModel):
    check_id: ProcessingIdentifier
    scope: Literal["source", "prepared_scene", "prepared_pair"]
    metric: ProcessingIdentifier
    measured_value: float | None = None
    units: str | None = Field(default=None, min_length=1, max_length=80)
    threshold: QualityThreshold | None = None
    outcome: Literal["passed", "failed", "unresolved", "not_applicable"]
    explanation: str = Field(min_length=1, max_length=1000)

    @field_validator("measured_value")
    @classmethod
    def require_finite_measurement(cls, value: float | None) -> float | None:
        return None if value is None else _finite(value, "quality measurement")

    @model_validator(mode="after")
    def validate_quality_evidence(self) -> Self:
        if self.outcome in {"passed", "failed"}:
            if self.measured_value is None or self.units is None or self.threshold is None:
                raise ValueError(
                    "passed or failed quality checks require a measured value and threshold"
                )
            if self.units != self.threshold.units:
                raise ValueError("quality measurement and threshold units must match")
            comparisons = {
                "lt": self.measured_value < self.threshold.value,
                "lte": self.measured_value <= self.threshold.value,
                "gt": self.measured_value > self.threshold.value,
                "gte": self.measured_value >= self.threshold.value,
                "eq": isclose(self.measured_value, self.threshold.value),
            }
            expected_outcome = "passed" if comparisons[self.threshold.operator] else "failed"
            if self.outcome != expected_outcome:
                raise ValueError("quality outcome must match the measured value and threshold")
        elif self.outcome == "unresolved":
            if self.measured_value is not None:
                raise ValueError("unresolved quality checks must keep the measured value unknown")
        elif (
            self.measured_value is not None or self.units is not None or self.threshold is not None
        ):
            raise ValueError("not-applicable quality checks must not include measurement fields")
        return self


class TaskReadiness(StrictViewerModel):
    intended_task: Literal["optical_single_scene", "optical_pair"]
    processing_profile: Literal["sentinel-2-l2a-surface-reflectance-v1"]
    scenes: list[ViewerSceneIdentity] = Field(min_length=1, max_length=2)
    state: Literal["ready", "limited", "not_ready", "unresolved", "unsupported"]
    quality_check_ids: list[ProcessingIdentifier] = Field(min_length=1, max_length=100)
    unresolved_check_ids: list[ProcessingIdentifier] = Field(default_factory=list, max_length=100)
    explanation: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_readiness_shape(self) -> Self:
        expected_count = 1 if self.intended_task == "optical_single_scene" else 2
        if len(self.scenes) != expected_count:
            raise ValueError(f"{self.intended_task} readiness requires {expected_count} scene(s)")
        if len(self.quality_check_ids) != len(set(self.quality_check_ids)):
            raise ValueError("readiness quality-check identifiers must be unique")
        if len(self.unresolved_check_ids) != len(set(self.unresolved_check_ids)):
            raise ValueError("unresolved check identifiers must be unique")
        if not set(self.unresolved_check_ids).issubset(self.quality_check_ids):
            raise ValueError("unresolved checks must be included in quality_check_ids")
        if self.state == "ready" and self.unresolved_check_ids:
            raise ValueError("ready tasks cannot retain unresolved checks")
        if self.state == "unresolved" and not self.unresolved_check_ids:
            raise ValueError("unresolved readiness requires unresolved checks")
        return self


class ProcessingOutcome(StrictViewerModel):
    state: Literal["succeeded", "failed"]
    explanation: str = Field(min_length=1, max_length=1000)


class PreparationResult(StrictViewerModel):
    schema_version: Literal["1.0"] = PROCESSING_SCHEMA_VERSION
    job_id: UUID
    request: PreparationRequest
    processing: ProcessingOutcome
    output_grid: OutputGrid | None = None
    prepared_rasters: list[PreparedRaster] = Field(default_factory=list, max_length=2)
    quality_checks: list[QualityCheck] = Field(default_factory=list, max_length=100)
    readiness: TaskReadiness
    artifacts: list[ArtifactReference] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.processing.state == "succeeded":
            if self.output_grid is None or len(self.prepared_rasters) != len(self.request.scenes):
                raise ValueError("successful processing requires a grid and one raster per scene")
            if any(raster.grid != self.output_grid for raster in self.prepared_rasters):
                raise ValueError("successful processing outputs must use the declared output grid")
        elif self.output_grid is not None or self.prepared_rasters:
            raise ValueError("failed processing must not expose prepared raster outputs")
        if self.readiness.intended_task != self.request.intended_task:
            raise ValueError("readiness intended task must match the preparation request")
        if self.readiness.processing_profile != self.request.processing_profile:
            raise ValueError("readiness profile must match the preparation request")
        if self.readiness.scenes != self.request.scenes:
            raise ValueError("readiness scenes must match the preparation request")
        checks = {check.check_id: check for check in self.quality_checks}
        if len(checks) != len(self.quality_checks):
            raise ValueError("quality-check identifiers must be unique")
        missing = sorted(set(self.readiness.quality_check_ids) - checks.keys())
        if missing:
            raise ValueError(f"readiness references missing quality checks: {', '.join(missing)}")
        unresolved = {
            check_id
            for check_id in self.readiness.quality_check_ids
            if checks[check_id].outcome == "unresolved"
        }
        if unresolved != set(self.readiness.unresolved_check_ids):
            raise ValueError("readiness unresolved checks must match unresolved quality outcomes")
        if self.readiness.state == "ready" and any(
            checks[check_id].outcome not in {"passed", "not_applicable"}
            for check_id in self.readiness.quality_check_ids
        ):
            raise ValueError("ready tasks require every referenced quality check to pass")
        if self.processing.state == "failed" and self.readiness.state == "ready":
            raise ValueError("failed processing cannot be task-ready")
        artifact_ids = [artifact.artifact_id for artifact in self.artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("result artifact references must be unique")
        if self.processing.state == "succeeded":
            nested_artifacts = {
                artifact.artifact_id
                for raster in self.prepared_rasters
                for artifact in [
                    raster.artifact,
                    raster.validity_mask.artifact,
                    *(mask.artifact for mask in raster.quality_masks),
                ]
            }
            if not nested_artifacts.issubset(artifact_ids):
                raise ValueError("successful processing must commit every raster and mask artifact")
            if any(artifact.access.state != "available" for artifact in self.artifacts):
                raise ValueError("successful processing artifacts must be available")
        return self


class JobProgress(StrictViewerModel):
    completed_units: int = Field(ge=0, strict=True)
    total_units: int = Field(gt=0, strict=True)
    units: ProcessingIdentifier

    @model_validator(mode="after")
    def validate_progress(self) -> Self:
        if self.completed_units > self.total_units:
            raise ValueError("completed progress units must not exceed total units")
        return self


class ProcessingJobStatus(StrictViewerModel):
    schema_version: Literal["1.0"] = PROCESSING_SCHEMA_VERSION
    job_id: UUID
    state: Literal["queued", "running", "cancelling", "succeeded", "failed", "cancelled"]
    submitted_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    attempt: int = Field(ge=0, strict=True)
    current_stage: ProcessingIdentifier | None = None
    progress: JobProgress | None = None
    artifacts: list[ArtifactReference] = Field(default_factory=list, max_length=64)
    error_code: ProcessingIdentifier | None = None
    safe_error_message: str | None = Field(default=None, min_length=1, max_length=1000)

    @field_validator("submitted_at", "started_at", "finished_at")
    @classmethod
    def normalize_job_timestamps(cls, value: datetime | None, info: object) -> datetime | None:
        if value is None:
            return None
        field_name = getattr(info, "field_name", "job timestamp")
        return _as_utc(value, field_name)

    @model_validator(mode="after")
    def validate_job_state(self) -> Self:
        if self.started_at is not None and self.started_at < self.submitted_at:
            raise ValueError("job started_at must not precede submitted_at")
        if self.finished_at is not None:
            if self.finished_at < self.submitted_at:
                raise ValueError("job finished_at must not precede submitted_at")
            if self.started_at is not None and self.finished_at < self.started_at:
                raise ValueError("job finished_at must not precede started_at")
        if self.state == "queued":
            if self.started_at is not None or self.finished_at is not None or self.attempt != 0:
                raise ValueError("queued jobs cannot include execution timestamps or attempts")
        elif self.state in {"running", "cancelling"}:
            if self.started_at is None or self.finished_at is not None or self.attempt < 1:
                raise ValueError(f"{self.state} jobs require an active attempt")
        elif self.finished_at is None:
            raise ValueError(f"terminal job state '{self.state}' requires finished_at")
        has_error = self.error_code is not None or self.safe_error_message is not None
        if self.state == "failed":
            if self.error_code is None or self.safe_error_message is None:
                raise ValueError("failed jobs require a safe structured error")
        elif has_error:
            raise ValueError("only failed jobs may include an error")
        if self.state == "succeeded":
            if self.started_at is None or self.attempt < 1:
                raise ValueError("succeeded jobs require an executed attempt")
            if not self.artifacts:
                raise ValueError("succeeded jobs require committed artifact references")
            if any(artifact.access.state != "available" for artifact in self.artifacts):
                raise ValueError("succeeded job artifacts must be available")
            if self.progress is not None and (
                self.progress.completed_units != self.progress.total_units
            ):
                raise ValueError("succeeded job progress must be complete when provided")
        elif self.artifacts:
            raise ValueError("non-succeeded jobs must not expose committed artifacts")
        return self
