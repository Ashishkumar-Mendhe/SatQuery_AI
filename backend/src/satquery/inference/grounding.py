from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from io import BytesIO
from math import isfinite
from typing import Any, Literal, Protocol

from satquery.api.schemas.vqa import (
    GroundingCandidate,
    GroundingPreprocessing,
    ModelIdentity,
    ModelImageChip,
    PixelBoundingBox,
    ProjectedMapPolygon,
    ReferringGroundingRequest,
    ReferringGroundingResult,
    UserSelectedPixelRegion,
    VisualPromptPixelBoundingBox,
)
from satquery.inference.chip import EncodedModelChip

GROUNDING_MODEL_ID = "IDEA-Research/grounding-dino-tiny"
GROUNDING_MODEL_REVISION = "a2bb814dd30d776dcf7e30523b00659f4f141c71"
GROUNDING_ADAPTER_VERSION = "satquery-grounding-dino-v1"
GROUNDING_METHOD = "grounding-dino-text-conditioned-box-v1"
MAX_GROUNDING_SECONDS = 300.0


class GroundingError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class RawGroundingCandidate:
    label: str
    score: float
    box: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class RuntimeGroundingResult:
    candidates: tuple[RawGroundingCandidate, ...]
    model_input_width: int
    model_input_height: int
    pad_right: int
    pad_bottom: int
    latency_ms: float


class GroundingRuntime(Protocol):
    def infer(
        self,
        *,
        image_png: bytes,
        referring_text: str,
        selected_region: UserSelectedPixelRegion | None,
        box_threshold: float,
        text_threshold: float,
        max_candidates: int,
    ) -> RuntimeGroundingResult: ...


class TransformersGroundingDinoRuntime:
    """Pinned CPU Grounding DINO runtime; model loading remains lazy and server-side."""

    def __init__(self, *, local_files_only: bool = False) -> None:
        self._local_files_only = local_files_only
        self._processor: Any | None = None
        self._model: Any | None = None

    def _load(self) -> tuple[Any, Any]:
        if self._processor is not None and self._model is not None:
            return self._processor, self._model
        try:
            from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
        except ImportError as exc:
            raise GroundingError(
                "GROUNDING_RUNTIME_UNAVAILABLE",
                "Install the pinned grounding optional dependencies before enabling grounding.",
            ) from exc
        try:
            processor = AutoProcessor.from_pretrained(  # type: ignore[no-untyped-call]
                GROUNDING_MODEL_ID,
                revision=GROUNDING_MODEL_REVISION,
                local_files_only=self._local_files_only,
            )
            model = AutoModelForZeroShotObjectDetection.from_pretrained(
                GROUNDING_MODEL_ID,
                revision=GROUNDING_MODEL_REVISION,
                local_files_only=self._local_files_only,
                use_safetensors=True,
            )
        except Exception as exc:
            raise GroundingError(
                "GROUNDING_MODEL_UNAVAILABLE",
                "The pinned Grounding DINO checkpoint could not be loaded.",
            ) from exc
        model.eval()
        self._processor = processor
        self._model = model
        return processor, model

    def infer(
        self,
        *,
        image_png: bytes,
        referring_text: str,
        selected_region: UserSelectedPixelRegion | None,
        box_threshold: float,
        text_threshold: float,
        max_candidates: int,
    ) -> RuntimeGroundingResult:
        try:
            import torch
            from PIL import Image
        except ImportError as exc:
            raise GroundingError(
                "GROUNDING_RUNTIME_UNAVAILABLE",
                "The local grounding image/runtime dependencies are unavailable.",
            ) from exc
        processor, model = self._load()
        try:
            with Image.open(BytesIO(image_png)) as source:
                rgba = source.convert("RGBA")
                background = Image.new("RGBA", rgba.size, (127, 127, 127, 255))
                image = Image.alpha_composite(background, rgba).convert("RGB")
        except Exception as exc:
            raise GroundingError(
                "GROUNDING_IMAGE_INVALID", "The model chip is not a valid image."
            ) from exc
        if selected_region is not None:
            image = image.crop(
                (
                    selected_region.x_min,
                    selected_region.y_min,
                    selected_region.x_max,
                    selected_region.y_max,
                )
            )
        query = referring_text.strip().lower()
        if not query.endswith("."):
            query = f"{query}."
        started = time.monotonic()
        try:
            inputs = processor(images=image, text=query, return_tensors="pt")
            with torch.no_grad():
                outputs = model(**inputs)
            results = processor.post_process_grounded_object_detection(
                outputs,
                inputs.input_ids,
                threshold=box_threshold,
                text_threshold=text_threshold,
                target_sizes=[(image.height, image.width)],
            )[0]
        except Exception as exc:
            raise GroundingError(
                "GROUNDING_INFERENCE_FAILED", "Grounding DINO inference failed."
            ) from exc
        latency_ms = (time.monotonic() - started) * 1000.0
        pixel_values = inputs["pixel_values"]
        input_height = int(pixel_values.shape[-2])
        input_width = int(pixel_values.shape[-1])
        pixel_mask = inputs.get("pixel_mask")
        pad_right = 0
        pad_bottom = 0
        if pixel_mask is not None:
            valid_rows = int(pixel_mask[0].any(dim=1).sum().item())
            valid_columns = int(pixel_mask[0].any(dim=0).sum().item())
            pad_bottom = input_height - valid_rows
            pad_right = input_width - valid_columns
        raw: list[RawGroundingCandidate] = []
        for label, score, box in zip(
            results["text_labels"], results["scores"], results["boxes"], strict=True
        ):
            values = tuple(float(value) for value in box.tolist())
            if len(values) != 4 or not all(isfinite(value) for value in values):
                continue
            raw.append(
                RawGroundingCandidate(
                    label=str(label).strip() or query.removesuffix("."),
                    score=float(score.item()),
                    box=(values[0], values[1], values[2], values[3]),
                )
            )
        raw.sort(key=lambda candidate: candidate.score, reverse=True)
        return RuntimeGroundingResult(
            candidates=tuple(raw[:max_candidates]),
            model_input_width=input_width,
            model_input_height=input_height,
            pad_right=pad_right,
            pad_bottom=pad_bottom,
            latency_ms=latency_ms,
        )


class ReferringGroundingService:
    def __init__(
        self,
        runtime: GroundingRuntime,
        *,
        timeout_seconds: float = MAX_GROUNDING_SECONDS,
        max_concurrency: int = 1,
    ) -> None:
        if not 1 <= max_concurrency <= 2:
            raise ValueError("grounding concurrency must be between 1 and 2")
        if not 0 < timeout_seconds <= MAX_GROUNDING_SECONDS:
            raise ValueError(f"grounding timeout must be at most {MAX_GROUNDING_SECONDS} seconds")
        self._runtime = runtime
        self._timeout_seconds = timeout_seconds
        self._slots = asyncio.Semaphore(max_concurrency)

    async def locate(
        self, request: ReferringGroundingRequest, chip: EncodedModelChip
    ) -> ReferringGroundingResult:
        failure = _preflight(request, chip)
        if failure is not None:
            return failure
        if request.requested_geometry != "bounding_box":
            return _unsuccessful(
                request,
                "unsupported_geometry",
                "The selected Grounding DINO checkpoint produces boxes, not polygons or masks.",
            )
        try:
            async with self._slots:
                async with asyncio.timeout(self._timeout_seconds):
                    runtime_result = await asyncio.to_thread(
                        self._runtime.infer,
                        image_png=chip.content,
                        referring_text=request.referring_text,
                        selected_region=request.selected_region,
                        box_threshold=request.box_threshold,
                        text_threshold=request.text_threshold,
                        max_candidates=request.max_candidates,
                    )
        except TimeoutError:
            return _unsuccessful(
                request, "failed_inference", "Grounding inference exceeded its time limit."
            )
        except GroundingError as exc:
            return _unsuccessful(request, "failed_inference", str(exc))
        candidates = _transform_candidates(request, runtime_result)
        visual_width, visual_height = _visual_prompt_size(request)
        preprocessing = GroundingPreprocessing(
            processor_revision=GROUNDING_MODEL_REVISION,
            visual_prompt_width=visual_width,
            visual_prompt_height=visual_height,
            model_input_width=runtime_result.model_input_width,
            model_input_height=runtime_result.model_input_height,
            pad_right=runtime_result.pad_right,
            pad_bottom=runtime_result.pad_bottom,
        )
        if not candidates:
            status = "no_detection"
        elif len(candidates) == 1:
            status = "detected"
        else:
            status = "ambiguous_detection"
        return ReferringGroundingResult(
            request_id=request.request_id,
            source_chip_id=request.image_chip.chip_id,
            status=status,
            model=_model_identity(),
            selected_region=request.selected_region,
            preprocessing=preprocessing,
            candidates=candidates,
            latency_ms=runtime_result.latency_ms,
        )


def _preflight(
    request: ReferringGroundingRequest, chip: EncodedModelChip
) -> ReferringGroundingResult | None:
    if request.image_chip != chip.contract:
        return _unsuccessful(request, "unavailable", "The request does not match the encoded chip.")
    if len(chip.content) != chip.contract.byte_size:
        return _unsuccessful(request, "unavailable", "The encoded chip byte size changed.")
    if hashlib.sha256(chip.content).hexdigest() != chip.contract.checksum_sha256:
        return _unsuccessful(request, "unavailable", "The encoded chip checksum changed.")
    if chip.contract.phase6_quality.readiness.state not in {"ready", "limited"}:
        return _unsuccessful(
            request,
            "unavailable",
            "The prepared image did not pass the required scientific quality gate.",
        )
    return None


def _transform_candidates(
    request: ReferringGroundingRequest, result: RuntimeGroundingResult
) -> list[GroundingCandidate]:
    visual_width, visual_height = _visual_prompt_size(request)
    offset_x = request.selected_region.x_min if request.selected_region is not None else 0
    offset_y = request.selected_region.y_min if request.selected_region is not None else 0
    transformed: list[GroundingCandidate] = []
    for raw in result.candidates:
        clipped = _clip_box(raw.box, visual_width, visual_height)
        if clipped is None:
            continue
        chip_box_values = (
            clipped[0] + offset_x,
            clipped[1] + offset_y,
            clipped[2] + offset_x,
            clipped[3] + offset_y,
        )
        chip_box = PixelBoundingBox(
            source_chip_id=request.image_chip.chip_id,
            image_width=request.image_chip.width,
            image_height=request.image_chip.height,
            x_min=chip_box_values[0],
            y_min=chip_box_values[1],
            x_max=chip_box_values[2],
            y_max=chip_box_values[3],
        )
        transformed.append(
            GroundingCandidate(
                candidate_index=len(transformed),
                label=raw.label,
                model_score=max(0.0, min(1.0, raw.score)),
                visual_prompt_box=VisualPromptPixelBoundingBox(
                    image_width=visual_width,
                    image_height=visual_height,
                    x_min=clipped[0],
                    y_min=clipped[1],
                    x_max=clipped[2],
                    y_max=clipped[3],
                ),
                image_chip_box=chip_box,
                map_footprint=_box_to_map_polygon(request.image_chip, chip_box),
            )
        )
    return transformed


def _clip_box(
    box: tuple[float, float, float, float], width: int, height: int
) -> tuple[float, float, float, float] | None:
    if not all(isfinite(value) for value in box):
        return None
    x_min = max(0.0, min(float(width), box[0]))
    y_min = max(0.0, min(float(height), box[1]))
    x_max = max(0.0, min(float(width), box[2]))
    y_max = max(0.0, min(float(height), box[3]))
    if x_max <= x_min or y_max <= y_min:
        return None
    return (x_min, y_min, x_max, y_max)


def _box_to_map_polygon(chip: ModelImageChip, box: PixelBoundingBox) -> ProjectedMapPolygon:
    corners = [
        (box.x_min, box.y_min),
        (box.x_max, box.y_min),
        (box.x_max, box.y_max),
        (box.x_min, box.y_max),
        (box.x_min, box.y_min),
    ]
    return ProjectedMapPolygon(
        source_chip_id=chip.chip_id,
        crs=chip.pixel_to_map.crs,
        rings=[[_pixel_to_map(chip, x, y) for x, y in corners]],
    )


def _pixel_to_map(chip: ModelImageChip, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = chip.pixel_to_map.affine
    return (a * x + b * y + c, d * x + e * y + f)


def map_to_pixel(chip: ModelImageChip, x: float, y: float) -> tuple[float, float]:
    """Invert the supported north-up affine for coordinate round-trip verification."""

    a, b, c, d, e, f = chip.pixel_to_map.affine
    determinant = a * e - b * d
    if determinant == 0:
        raise GroundingError("GROUNDING_TRANSFORM_INVALID", "The chip affine is singular.")
    delta_x = x - c
    delta_y = y - f
    return (
        (e * delta_x - b * delta_y) / determinant,
        (-d * delta_x + a * delta_y) / determinant,
    )


def _visual_prompt_size(request: ReferringGroundingRequest) -> tuple[int, int]:
    if request.selected_region is None:
        return request.image_chip.width, request.image_chip.height
    return (
        request.selected_region.x_max - request.selected_region.x_min,
        request.selected_region.y_max - request.selected_region.y_min,
    )


def _unsuccessful(
    request: ReferringGroundingRequest,
    status: Literal["unsupported_geometry", "unavailable", "failed_inference"],
    reason: str,
) -> ReferringGroundingResult:
    return ReferringGroundingResult(
        request_id=request.request_id,
        source_chip_id=request.image_chip.chip_id,
        status=status,
        model=_model_identity(),
        selected_region=request.selected_region,
        reason=reason,
    )


def _model_identity() -> ModelIdentity:
    return ModelIdentity(
        provider="hugging-face",
        model=GROUNDING_MODEL_ID,
        version=GROUNDING_MODEL_REVISION,
        adapter_version=GROUNDING_ADAPTER_VERSION,
        runtime="local",
        weights="public_checkpoint",
        licence_basis="Apache-2.0 checkpoint model card and upstream repository.",
        execution_hardware="local_cpu",
    )
