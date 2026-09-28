from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from satquery.api.schemas.catalog import CatalogGeometry
from satquery.api.schemas.processing import (
    ArtifactReference,
    JobProgress,
    ProcessingIdentifier,
    QualityCheck,
    Sha256Digest,
    TaskReadiness,
)
from satquery.api.schemas.viewer import (
    ResolvedImageryAssetIdentity,
    StrictViewerModel,
    ViewerSceneIdentity,
)

VQA_SCHEMA_VERSION: Literal["1.0"] = "1.0"
MAX_MODEL_CHIP_EDGE_PIXELS = 2048
MAX_MODEL_CHIP_PIXELS = 4_194_304
MAX_MODEL_CHIP_BYTES = 20 * 1024 * 1024

type AffineTransform = tuple[float, float, float, float, float, float]
type ProjectedPoint = tuple[float, float]


def _finite(value: float, label: str) -> float:
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


class PixelToMapTransform(StrictViewerModel):
    """Transform chip pixel-edge coordinates into a projected map coordinate space."""

    crs: str = Field(pattern=r"^EPSG:(326|327)(0[1-9]|[1-5][0-9]|60)$")
    affine: AffineTransform
    pixel_interpretation: Literal["area"] = "area"
    pixel_origin: Literal["upper_left"] = "upper_left"
    x_axis: Literal["column_increases_right"] = "column_increases_right"
    y_axis: Literal["row_increases_down"] = "row_increases_down"
    coordinate_reference: Literal["pixel_edges"] = "pixel_edges"

    @field_validator("affine")
    @classmethod
    def validate_affine(cls, value: AffineTransform) -> AffineTransform:
        if not all(isfinite(number) for number in value):
            raise ValueError("pixel-to-map affine values must be finite")
        x_scale, x_skew, _, y_skew, y_scale, _ = value
        if x_scale <= 0 or y_scale >= 0:
            raise ValueError("pixel-to-map transform must be north-up")
        if x_skew != 0 or y_skew != 0:
            raise ValueError("rotated or sheared model chips are not supported")
        return value


class FixedLinearRendering(StrictViewerModel):
    """Explicit derived visual representation; never a replacement for calibrated values."""

    method: Literal["fixed_linear"] = "fixed_linear"
    source_units: str = Field(min_length=1, max_length=80)
    input_range: tuple[float, float]
    output_data_type: Literal["uint8"] = "uint8"
    output_range: tuple[Literal[0], Literal[255]] = (0, 255)
    out_of_range_behavior: Literal["clip_visual_representation_only"] = (
        "clip_visual_representation_only"
    )
    per_image_normalization: Literal[False] = False
    invalid_pixels: Literal["transparent"] = "transparent"

    @field_validator("input_range")
    @classmethod
    def validate_input_range(cls, value: tuple[float, float]) -> tuple[float, float]:
        low, high = value
        if not all(isfinite(number) for number in value) or low >= high:
            raise ValueError("rendering input_range must be ordered finite values")
        return value


class Phase6QualityContext(StrictViewerModel):
    preparation_job_id: UUID
    provenance_state: Literal["committed_manifest", "runtime_measured"]
    provenance_manifest: ArtifactReference | None = None
    readiness: TaskReadiness
    quality_checks: list[QualityCheck] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_quality_context(self) -> Self:
        if self.provenance_state == "committed_manifest":
            if (
                self.provenance_manifest is None
                or self.provenance_manifest.kind != "provenance_manifest"
            ):
                raise ValueError("committed Phase 6 context requires a provenance manifest")
        elif self.provenance_manifest is not None:
            raise ValueError("runtime-measured Phase 6 context has no committed manifest")
        if self.readiness.intended_task != "optical_single_scene":
            raise ValueError("the initial VQA contract accepts one prepared optical scene")
        checks = {check.check_id: check for check in self.quality_checks}
        if len(checks) != len(self.quality_checks):
            raise ValueError("Phase 6 quality-check identifiers must be unique")
        missing = sorted(set(self.readiness.quality_check_ids) - checks.keys())
        if missing:
            raise ValueError(f"Phase 6 readiness references missing checks: {', '.join(missing)}")
        unresolved = {
            check_id
            for check_id in self.readiness.quality_check_ids
            if checks[check_id].outcome == "unresolved"
        }
        if unresolved != set(self.readiness.unresolved_check_ids):
            raise ValueError("Phase 6 unresolved checks must match readiness")
        if self.readiness.state == "ready" and any(
            checks[check_id].outcome not in {"passed", "not_applicable"}
            for check_id in self.readiness.quality_check_ids
        ):
            raise ValueError("ready tasks require every referenced Phase 6 check to pass")
        return self


class ModelImageChip(StrictViewerModel):
    """A bounded, server-created model input referring only to authorized artifacts."""

    schema_version: Literal["1.0"] = VQA_SCHEMA_VERSION
    chip_id: UUID
    scene: ViewerSceneIdentity
    acquired_at: datetime
    source_mode: Literal["authorized_prepared_artifact", "trusted_ephemeral_extraction"]
    source_raster: ArtifactReference | None = None
    source_assets: tuple[
        ResolvedImageryAssetIdentity,
        ResolvedImageryAssetIdentity,
        ResolvedImageryAssetIdentity,
    ]
    checksum_sha256: Sha256Digest
    media_type: Literal["image/png", "image/jpeg"]
    byte_size: int = Field(ge=1, le=MAX_MODEL_CHIP_BYTES, strict=True)
    width: int = Field(ge=1, le=MAX_MODEL_CHIP_EDGE_PIXELS, strict=True)
    height: int = Field(ge=1, le=MAX_MODEL_CHIP_EDGE_PIXELS, strict=True)
    band_order: tuple[Literal["red"], Literal["green"], Literal["blue"]] = (
        "red",
        "green",
        "blue",
    )
    rendering: FixedLinearRendering
    pixel_to_map: PixelToMapTransform
    footprint_wgs84: CatalogGeometry
    phase6_quality: Phase6QualityContext

    @field_validator("acquired_at")
    @classmethod
    def normalize_acquisition_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("acquired_at must include a UTC offset")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_chip(self) -> Self:
        if self.width * self.height > MAX_MODEL_CHIP_PIXELS:
            raise ValueError(f"model chip may contain at most {MAX_MODEL_CHIP_PIXELS} pixels")
        if self.source_mode == "authorized_prepared_artifact":
            if self.source_raster is None or self.source_raster.kind != "prepared_raster":
                raise ValueError("prepared model chip source requires a prepared raster artifact")
            if self.source_raster.access.state != "available":
                raise ValueError("model chip source artifact must remain authorized and available")
        elif self.source_raster is not None:
            raise ValueError("ephemeral extraction must not claim a committed raster artifact")
        if any(source.scene != self.scene for source in self.source_assets):
            raise ValueError("every model chip source asset must belong to its scene")
        roles = [source.asset for source in self.source_assets]
        if len(roles) != len(set(roles)):
            raise ValueError("model chip source assets must be distinct")
        readiness = self.phase6_quality.readiness
        if readiness.scenes != [self.scene]:
            raise ValueError("model chip scene must match its Phase 6 quality context")
        return self


class VqaCaptionRequest(StrictViewerModel):
    schema_version: Literal["1.0"] = VQA_SCHEMA_VERSION
    request_id: UUID
    task: Literal["visual_question_answering", "image_captioning"]
    image_chip: ModelImageChip
    question: str | None = Field(default=None, min_length=1, max_length=1000)
    grounding: Literal["not_requested", "separate_optional"] = "not_requested"
    max_answer_characters: int = Field(default=2000, ge=1, le=4000, strict=True)

    @model_validator(mode="after")
    def validate_task_input(self) -> Self:
        if self.task == "visual_question_answering" and self.question is None:
            raise ValueError("visual question answering requires a question")
        if self.task == "image_captioning" and self.question is not None:
            raise ValueError("image captioning does not accept a question")
        return self


class ModelIdentity(StrictViewerModel):
    provider: ProcessingIdentifier
    model: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=160)
    adapter_version: str = Field(min_length=1, max_length=160)
    runtime: Literal["hosted_api", "local"]
    weights: Literal["hosted_not_disclosed", "public_checkpoint"]
    licence_basis: str = Field(min_length=1, max_length=500)
    execution_hardware: str = Field(min_length=1, max_length=160)


class InferenceParameters(StrictViewerModel):
    prompt_version: ProcessingIdentifier
    image_detail: Literal["high"] = "high"
    max_output_tokens: int = Field(ge=1, le=512, strict=True)
    temperature: float = Field(ge=0, le=2, strict=True)
    timeout_seconds: float = Field(gt=0, le=120, strict=True)
    store_provider_response: Literal[False] = False


class AnswerEvidenceReference(StrictViewerModel):
    evidence_id: UUID
    source_chip_id: UUID
    source_scene: ViewerSceneIdentity
    basis: Literal["whole_image_visual", "phase6_quality_check"]
    description: str = Field(min_length=1, max_length=1000)
    phase6_check_ids: list[ProcessingIdentifier] = Field(default_factory=list, max_length=20)

    @field_validator("phase6_check_ids")
    @classmethod
    def require_unique_checks(cls, value: list[ProcessingIdentifier]) -> list[ProcessingIdentifier]:
        if len(value) != len(set(value)):
            raise ValueError("evidence quality-check references must be unique")
        return value


class PixelBoundingBox(StrictViewerModel):
    coordinate_space: Literal["image_pixel"] = "image_pixel"
    source_chip_id: UUID
    pixel_origin: Literal["upper_left"] = "upper_left"
    x_axis: Literal["column_increases_right"] = "column_increases_right"
    y_axis: Literal["row_increases_down"] = "row_increases_down"
    coordinate_reference: Literal["pixel_edges"] = "pixel_edges"
    image_width: int = Field(ge=1, le=MAX_MODEL_CHIP_EDGE_PIXELS, strict=True)
    image_height: int = Field(ge=1, le=MAX_MODEL_CHIP_EDGE_PIXELS, strict=True)
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        values = (self.x_min, self.y_min, self.x_max, self.y_max)
        if not all(isfinite(value) for value in values):
            raise ValueError("pixel grounding coordinates must be finite")
        if not (0 <= self.x_min < self.x_max <= self.image_width):
            raise ValueError("pixel grounding x coordinates exceed the chip")
        if not (0 <= self.y_min < self.y_max <= self.image_height):
            raise ValueError("pixel grounding y coordinates exceed the chip")
        return self


class UserSelectedPixelRegion(StrictViewerModel):
    """A user prompt region; it is never model-produced grounding."""

    coordinate_space: Literal["image_pixel"] = "image_pixel"
    source_chip_id: UUID
    pixel_origin: Literal["upper_left"] = "upper_left"
    coordinate_reference: Literal["pixel_edges"] = "pixel_edges"
    image_width: int = Field(ge=1, le=MAX_MODEL_CHIP_EDGE_PIXELS, strict=True)
    image_height: int = Field(ge=1, le=MAX_MODEL_CHIP_EDGE_PIXELS, strict=True)
    x_min: int = Field(ge=0, strict=True)
    y_min: int = Field(ge=0, strict=True)
    x_max: int = Field(gt=0, strict=True)
    y_max: int = Field(gt=0, strict=True)
    purpose: Literal["visual_prompt_crop"] = "visual_prompt_crop"

    @model_validator(mode="after")
    def validate_region(self) -> Self:
        if not (self.x_min < self.x_max <= self.image_width):
            raise ValueError("selected-region x coordinates exceed the chip")
        if not (self.y_min < self.y_max <= self.image_height):
            raise ValueError("selected-region y coordinates exceed the chip")
        return self


class VisualPromptPixelBoundingBox(StrictViewerModel):
    """A detector box in the exact image (whole chip or crop) passed to its processor."""

    coordinate_space: Literal["visual_prompt_pixel"] = "visual_prompt_pixel"
    pixel_origin: Literal["upper_left"] = "upper_left"
    coordinate_reference: Literal["pixel_edges"] = "pixel_edges"
    image_width: int = Field(ge=1, le=MAX_MODEL_CHIP_EDGE_PIXELS, strict=True)
    image_height: int = Field(ge=1, le=MAX_MODEL_CHIP_EDGE_PIXELS, strict=True)
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        values = (self.x_min, self.y_min, self.x_max, self.y_max)
        if not all(isfinite(value) for value in values):
            raise ValueError("visual-prompt coordinates must be finite")
        if not (0 <= self.x_min < self.x_max <= self.image_width):
            raise ValueError("visual-prompt x coordinates exceed the supplied image")
        if not (0 <= self.y_min < self.y_max <= self.image_height):
            raise ValueError("visual-prompt y coordinates exceed the supplied image")
        return self


class ProjectedMapPolygon(StrictViewerModel):
    coordinate_space: Literal["projected_map"] = "projected_map"
    source_chip_id: UUID
    crs: str = Field(pattern=r"^EPSG:(326|327)(0[1-9]|[1-5][0-9]|60)$")
    rings: list[list[ProjectedPoint]] = Field(min_length=1, max_length=16)

    @field_validator("rings")
    @classmethod
    def validate_rings(cls, value: list[list[ProjectedPoint]]) -> list[list[ProjectedPoint]]:
        for ring in value:
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError(
                    "projected grounding rings must be closed with at least four points"
                )
            if any(not all(isfinite(coordinate) for coordinate in point) for point in ring):
                raise ValueError("projected grounding coordinates must be finite")
        return value


GroundingGeometry = Annotated[
    PixelBoundingBox | ProjectedMapPolygon, Field(discriminator="coordinate_space")
]


class GroundingResult(StrictViewerModel):
    availability: Literal["available", "unavailable", "unknown"]
    method: str = Field(min_length=1, max_length=160)
    model: ModelIdentity | None = None
    geometries: list[GroundingGeometry] = Field(default_factory=list, max_length=100)
    reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_grounding_availability(self) -> Self:
        if self.availability == "available":
            if self.model is None or not self.geometries or self.reason is not None:
                raise ValueError("available grounding requires a model and geometry only")
        elif self.geometries or self.reason is None:
            raise ValueError("unavailable or unknown grounding requires a reason and no geometry")
        return self


class ReferringGroundingRequest(StrictViewerModel):
    schema_version: Literal["1.0"] = VQA_SCHEMA_VERSION
    request_id: UUID
    image_chip: ModelImageChip
    referring_text: str = Field(min_length=1, max_length=160)
    selected_region: UserSelectedPixelRegion | None = None
    requested_geometry: Literal["bounding_box", "polygon", "mask"] = "bounding_box"
    max_candidates: int = Field(default=5, ge=1, le=10, strict=True)
    box_threshold: float = Field(default=0.35, ge=0, le=1)
    text_threshold: float = Field(default=0.25, ge=0, le=1)

    @field_validator("referring_text")
    @classmethod
    def normalize_referring_text(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("referring text must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_selected_region(self) -> Self:
        if self.selected_region is None:
            return self
        if self.selected_region.source_chip_id != self.image_chip.chip_id:
            raise ValueError("selected region must reference the request image chip")
        if (
            self.selected_region.image_width != self.image_chip.width
            or self.selected_region.image_height != self.image_chip.height
        ):
            raise ValueError("selected-region dimensions must match the image chip")
        return self


class GroundingPreprocessing(StrictViewerModel):
    processor: Literal["GroundingDinoProcessor"] = "GroundingDinoProcessor"
    processor_revision: str = Field(min_length=40, max_length=64)
    resize_shortest_edge: Literal[800] = 800
    resize_longest_edge: Literal[1333] = 1333
    resampling: Literal["bilinear"] = "bilinear"
    normalization: Literal["imagenet_mean_std"] = "imagenet_mean_std"
    transparent_pixel_fill: Literal["neutral_gray_127"] = "neutral_gray_127"
    visual_prompt_width: int = Field(ge=1, le=MAX_MODEL_CHIP_EDGE_PIXELS, strict=True)
    visual_prompt_height: int = Field(ge=1, le=MAX_MODEL_CHIP_EDGE_PIXELS, strict=True)
    model_input_width: int = Field(ge=1, le=1333, strict=True)
    model_input_height: int = Field(ge=1, le=1333, strict=True)
    pad_left: Literal[0] = 0
    pad_top: Literal[0] = 0
    pad_right: int = Field(ge=0, le=1333, strict=True)
    pad_bottom: int = Field(ge=0, le=1333, strict=True)
    postprocess_target: Literal["visual_prompt_original_size"] = "visual_prompt_original_size"


class GroundingCandidate(StrictViewerModel):
    candidate_index: int = Field(ge=0, le=9, strict=True)
    label: str = Field(min_length=1, max_length=160)
    model_score: float = Field(ge=0, le=1)
    score_meaning: Literal["uncalibrated_model_relevance"] = "uncalibrated_model_relevance"
    geometry_kind: Literal["bounding_box"] = "bounding_box"
    visual_prompt_box: VisualPromptPixelBoundingBox
    image_chip_box: PixelBoundingBox
    map_footprint: ProjectedMapPolygon


class ReferringGroundingResult(StrictViewerModel):
    schema_version: Literal["1.0"] = VQA_SCHEMA_VERSION
    request_id: UUID
    source_chip_id: UUID
    status: Literal[
        "detected",
        "no_detection",
        "ambiguous_detection",
        "unsupported_geometry",
        "unavailable",
        "failed_inference",
    ]
    method: Literal["grounding-dino-text-conditioned-box-v1"] = (
        "grounding-dino-text-conditioned-box-v1"
    )
    model: ModelIdentity
    selected_region: UserSelectedPixelRegion | None = None
    preprocessing: GroundingPreprocessing | None = None
    candidates: list[GroundingCandidate] = Field(default_factory=list, max_length=10)
    reason: str | None = Field(default=None, min_length=1, max_length=1000)
    latency_ms: float | None = Field(default=None, ge=0, le=600_000)
    geometry_capability: Literal["bounding_boxes_only_no_masks"] = "bounding_boxes_only_no_masks"

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        completed = self.status in {"detected", "no_detection", "ambiguous_detection"}
        if completed and (self.preprocessing is None or self.latency_ms is None):
            raise ValueError("completed grounding requires preprocessing and latency")
        if self.status == "detected" and len(self.candidates) != 1:
            raise ValueError("detected grounding requires exactly one candidate")
        if self.status == "ambiguous_detection" and len(self.candidates) < 2:
            raise ValueError("ambiguous grounding requires multiple candidates")
        if self.status == "no_detection" and self.candidates:
            raise ValueError("no-detection grounding cannot include candidates")
        if self.status in {"unsupported_geometry", "unavailable", "failed_inference"}:
            if self.candidates or self.reason is None:
                raise ValueError("unsuccessful grounding requires a reason and no candidates")
        elif self.reason is not None:
            raise ValueError("completed grounding cannot include a failure reason")
        for candidate in self.candidates:
            if candidate.image_chip_box.source_chip_id != self.source_chip_id:
                raise ValueError("grounding candidate must reference the result image chip")
            if candidate.map_footprint.source_chip_id != self.source_chip_id:
                raise ValueError("map footprint must reference the result image chip")
        if (
            self.selected_region is not None
            and self.selected_region.source_chip_id != self.source_chip_id
        ):
            raise ValueError("selected region must reference the result image chip")
        return self


class NormalizedVisualPromptRegion(StrictViewerModel):
    """Client-selected region in normalized chip coordinates, never a model prediction."""

    coordinate_space: Literal["normalized_image"] = "normalized_image"
    x_min: float = Field(ge=0, le=1)
    y_min: float = Field(ge=0, le=1)
    x_max: float = Field(ge=0, le=1)
    y_max: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_region(self) -> Self:
        if self.x_min >= self.x_max or self.y_min >= self.y_max:
            raise ValueError("normalized selected-region bounds must have positive area")
        return self


class InferenceSubmissionRequest(StrictViewerModel):
    """Public inference input: stable identities only; asset locations are server-resolved."""

    schema_version: Literal["1.0"] = VQA_SCHEMA_VERSION
    request_id: UUID
    operation: Literal["visual_question_answering", "image_captioning", "referring_grounding"]
    scene: ViewerSceneIdentity
    aoi: CatalogGeometry
    text: str | None = Field(default=None, min_length=1, max_length=500)
    selected_region: NormalizedVisualPromptRegion | None = None
    requested_geometry: Literal["bounding_box", "polygon", "mask"] = "bounding_box"

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("inference text must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_operation(self) -> Self:
        requires_text = self.operation in {
            "visual_question_answering",
            "referring_grounding",
        }
        if requires_text != (self.text is not None):
            raise ValueError("only VQA and grounding operations require text")
        if self.operation != "referring_grounding" and self.selected_region is not None:
            raise ValueError("a selected visual-prompt region is supported only for grounding")
        if self.operation != "referring_grounding" and self.requested_geometry != "bounding_box":
            raise ValueError("requested geometry applies only to grounding")
        return self


class InferenceQualityDecision(StrictViewerModel):
    state: Literal["proceed", "proceed_with_warning", "blocked", "unknown"]
    reason: str = Field(min_length=1, max_length=1000)
    required_check_ids: list[ProcessingIdentifier] = Field(min_length=1, max_length=20)


class InferenceEvidenceRecord(StrictViewerModel):
    schema_version: Literal["1.0"] = VQA_SCHEMA_VERSION
    request: InferenceSubmissionRequest
    source_chip: ModelImageChip
    input_chip_artifact: ArtifactReference
    quality_decision: InferenceQualityDecision
    execution_state: Literal["completed", "unavailable", "blocked", "unknown"]
    execution_reason: str | None = Field(default=None, min_length=1, max_length=1000)
    answer: ModelAnswer | None = None
    grounding: ReferringGroundingResult | None = None
    interpretation_disclaimer: Literal["evidence_not_validation"] = "evidence_not_validation"
    interpretation_notice: str = (
        "Evidence identifies the pixels and geometry used by inference; it does not prove "
        "the model interpretation."
    )

    @model_validator(mode="after")
    def validate_result_binding(self) -> Self:
        if self.request.scene != self.source_chip.scene:
            raise ValueError("evidence scene must match the source chip")
        if (
            self.input_chip_artifact.kind != "inference_chip"
            or self.input_chip_artifact.media_type != self.source_chip.media_type
            or self.input_chip_artifact.checksum_sha256 != self.source_chip.checksum_sha256
            or self.input_chip_artifact.byte_size != self.source_chip.byte_size
            or self.input_chip_artifact.access.state != "available"
        ):
            raise ValueError("input chip artifact must expose the exact authorized source chip")
        if self.answer is not None and self.answer.source_chip_id != self.source_chip.chip_id:
            raise ValueError("answer evidence must reference the exact source chip")
        if self.grounding is not None and self.grounding.source_chip_id != self.source_chip.chip_id:
            raise ValueError("grounding evidence must reference the exact source chip")
        if self.execution_state == "completed" and self.execution_reason is not None:
            raise ValueError("completed inference evidence cannot include an execution reason")
        if self.execution_state != "completed" and self.execution_reason is None:
            raise ValueError("non-available inference evidence requires an execution reason")
        requires_result = self.execution_state == "completed"
        if self.request.operation == "referring_grounding":
            if self.answer is not None or (requires_result and self.grounding is None):
                raise ValueError("proceeding grounding evidence requires a grounding result only")
        elif self.grounding is not None or (requires_result and self.answer is None):
            raise ValueError("proceeding VQA/caption evidence requires a model answer only")
        return self


class InferenceJobStatus(StrictViewerModel):
    schema_version: Literal["1.0"] = VQA_SCHEMA_VERSION
    job_id: UUID
    request_id: UUID
    operation: Literal["visual_question_answering", "image_captioning", "referring_grounding"]
    state: Literal["queued", "running", "cancelling", "succeeded", "failed", "cancelled"]
    submitted_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    attempt: int = Field(ge=0, strict=True)
    current_stage: ProcessingIdentifier | None = None
    progress: JobProgress | None = None
    artifacts: list[ArtifactReference] = Field(default_factory=list, max_length=4)
    result: InferenceEvidenceRecord | None = None
    error_code: ProcessingIdentifier | None = None
    safe_error_message: str | None = Field(default=None, min_length=1, max_length=1000)


class ModelQualityWarning(StrictViewerModel):
    code: ProcessingIdentifier
    severity: Literal["information", "warning", "blocking"]
    message: str = Field(min_length=1, max_length=1000)
    corrective_action: str | None = Field(default=None, min_length=1, max_length=1000)
    phase6_check_id: ProcessingIdentifier | None = None


class ModelAnswer(StrictViewerModel):
    schema_version: Literal["1.0"] = VQA_SCHEMA_VERSION
    request_id: UUID
    task: Literal["visual_question_answering", "image_captioning"]
    source_chip_id: UUID
    availability: Literal["available", "unavailable", "unknown"]
    answer: str | None = Field(default=None, min_length=1, max_length=4000)
    reason: str | None = Field(default=None, min_length=1, max_length=1000)
    model: ModelIdentity
    inference_parameters: InferenceParameters
    provider_response_id: str | None = Field(default=None, min_length=1, max_length=160)
    latency_ms: float | None = Field(default=None, ge=0, le=120_000)
    evidence: list[AnswerEvidenceReference] = Field(default_factory=list, max_length=100)
    grounding: GroundingResult | None = None
    quality_warnings: list[ModelQualityWarning] = Field(default_factory=list, max_length=100)
    phase6_quality: Phase6QualityContext
    calibrated_confidence: None = None

    @model_validator(mode="after")
    def validate_answer(self) -> Self:
        if self.availability == "available":
            if self.answer is None or self.reason is not None:
                raise ValueError(
                    "available model answers require answer text and no failure reason"
                )
            if not self.evidence:
                raise ValueError("available model answers require image-specific evidence")
        elif self.answer is not None or self.reason is None:
            raise ValueError("unavailable or unknown answers require a reason and no answer text")
        if self.availability in {"available", "unknown"}:
            if self.provider_response_id is None or self.latency_ms is None:
                raise ValueError("completed model inference requires response ID and latency")
        elif self.provider_response_id is not None or self.latency_ms is not None:
            raise ValueError("unavailable inference must not claim a provider response or latency")
        quality_ids = {check.check_id for check in self.phase6_quality.quality_checks}
        quality_scenes = self.phase6_quality.readiness.scenes
        for reference in self.evidence:
            if reference.source_chip_id != self.source_chip_id:
                raise ValueError("evidence must reference the answer source chip")
            if reference.source_scene not in quality_scenes:
                raise ValueError("evidence scene must belong to the Phase 6 quality context")
            if not set(reference.phase6_check_ids).issubset(quality_ids):
                raise ValueError("evidence references an unknown Phase 6 quality check")
        if any(
            warning.phase6_check_id is not None and warning.phase6_check_id not in quality_ids
            for warning in self.quality_warnings
        ):
            raise ValueError("quality warning references an unknown Phase 6 check")
        if self.grounding is not None:
            for geometry in self.grounding.geometries:
                if geometry.source_chip_id != self.source_chip_id:
                    raise ValueError("grounding must reference the answer source chip")
        return self
