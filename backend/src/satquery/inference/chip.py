from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID, uuid4

import numpy as np
from rio_tiler.utils import render

from satquery.api.schemas.catalog import CatalogueScene
from satquery.api.schemas.processing import (
    ArtifactReference,
    PreparationRequest,
    QualityCheck,
    QualityThreshold,
    TaskReadiness,
)
from satquery.api.schemas.vqa import (
    MAX_MODEL_CHIP_BYTES,
    MAX_MODEL_CHIP_EDGE_PIXELS,
    MAX_MODEL_CHIP_PIXELS,
    FixedLinearRendering,
    ModelImageChip,
    Phase6QualityContext,
    PixelToMapTransform,
)
from satquery.processing.quality import OpticalQualityMasks
from satquery.processing.raster import CalibratedRasterInput

VQA_QUALITY_THRESHOLD_VERSION = "vqa-provisional-engineering-v1"
VQA_MIN_USABLE_FRACTION = 0.5
VQA_MIN_VALID_FRACTION = 0.8
VQA_RENDER_RANGE = (0.0, 0.3)


class ImageChipError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class EncodedModelChip:
    contract: ModelImageChip
    content: bytes


def build_model_chip(
    *,
    raster: CalibratedRasterInput,
    quality: OpticalQualityMasks,
    request: PreparationRequest,
    catalogue_scene: CatalogueScene,
    preparation_job_id: UUID | None = None,
    source_raster: ArtifactReference | None = None,
    provenance_manifest: ArtifactReference | None = None,
) -> EncodedModelChip:
    """Create one fixed-render PNG from calibrated scientific RGB and explicit masks."""

    _validate_inputs(raster, quality, request, catalogue_scene)
    quality_context = _quality_context(
        raster,
        quality,
        request,
        job_id=preparation_job_id or uuid4(),
        provenance_manifest=provenance_manifest,
    )
    valid_rgb = np.all(raster.band_validity, axis=0) & raster.inside_aoi_mask
    usable = valid_rgb & quality.usable
    rgb = _fixed_linear_uint8(raster.data)
    rgb[:, ~usable] = 0
    mask = usable.astype(np.uint8) * np.uint8(255)
    content = render(rgb, mask=mask, img_format="PNG")
    if not content or len(content) > MAX_MODEL_CHIP_BYTES:
        raise ImageChipError(
            "MODEL_CHIP_BYTE_LIMIT",
            f"The encoded model chip must contain 1 to {MAX_MODEL_CHIP_BYTES} bytes.",
        )
    source_mode = (
        "authorized_prepared_artifact"
        if source_raster is not None
        else "trusted_ephemeral_extraction"
    )
    contract = ModelImageChip(
        chip_id=uuid4(),
        scene=raster.scene,
        acquired_at=catalogue_scene.acquisition.start,
        source_mode=source_mode,
        source_raster=source_raster,
        source_assets=tuple(band.source for band in raster.bands),
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        media_type="image/png",
        byte_size=len(content),
        width=raster.width,
        height=raster.height,
        rendering=FixedLinearRendering(
            source_units="surface-reflectance",
            input_range=VQA_RENDER_RANGE,
        ),
        pixel_to_map=PixelToMapTransform(crs=raster.crs, affine=raster.transform),
        footprint_wgs84=request.aoi,
        phase6_quality=quality_context,
    )
    return EncodedModelChip(contract=contract, content=content)


def _validate_inputs(
    raster: CalibratedRasterInput,
    quality: OpticalQualityMasks,
    request: PreparationRequest,
    catalogue_scene: CatalogueScene,
) -> None:
    if request.scenes != [raster.scene]:
        raise ImageChipError(
            "CHIP_SCENE_MISMATCH", "The extraction does not match the request scene."
        )
    expected_scene = (
        catalogue_scene.provider.id,
        catalogue_scene.collection.id,
        catalogue_scene.provider_asset_id,
    )
    actual_scene = (raster.scene.provider, raster.scene.collection, raster.scene.item)
    if expected_scene != actual_scene:
        raise ImageChipError(
            "CHIP_CATALOGUE_MISMATCH", "Catalogue metadata belongs to a different scene."
        )
    if raster.band_order != ("red", "green", "blue"):
        raise ImageChipError(
            "UNSUPPORTED_CHIP_BANDS", "Model inference requires ordered red, green, and blue bands."
        )
    if raster.data.shape != (3, raster.height, raster.width):
        raise ImageChipError(
            "INVALID_CHIP_SHAPE", "The calibrated RGB array shape is inconsistent."
        )
    if quality.usable.shape != (raster.height, raster.width):
        raise ImageChipError("INVALID_QUALITY_SHAPE", "The quality mask does not match the chip.")
    if (
        raster.width > MAX_MODEL_CHIP_EDGE_PIXELS
        or raster.height > MAX_MODEL_CHIP_EDGE_PIXELS
        or raster.width * raster.height > MAX_MODEL_CHIP_PIXELS
    ):
        raise ImageChipError(
            "MODEL_CHIP_PIXEL_LIMIT", "The selected scientific extraction exceeds model limits."
        )


def _fixed_linear_uint8(data: np.ndarray) -> np.ndarray:
    low, high = VQA_RENDER_RANGE
    scaled = (data.astype(np.float32, copy=False) - low) * (255.0 / (high - low))
    # Invalid scientific samples remain excluded by the separate alpha mask. Give those
    # transparent RGB cells a deterministic zero payload before the uint8 conversion so NaN/Inf
    # never trigger an implementation-defined cast or warning.
    finite_scaled = np.where(np.isfinite(scaled), scaled, 0.0)
    rendered: np.ndarray = np.clip(finite_scaled, 0.0, 255.0).astype(np.uint8)
    return rendered


def _quality_context(
    raster: CalibratedRasterInput,
    quality: OpticalQualityMasks,
    request: PreparationRequest,
    *,
    job_id: UUID,
    provenance_manifest: ArtifactReference | None,
) -> Phase6QualityContext:
    inside_count = int(raster.inside_aoi_mask.sum())
    valid_rgb = np.all(raster.band_validity, axis=0) & raster.inside_aoi_mask
    valid_fraction = float(valid_rgb.sum() / inside_count) if inside_count else 0.0
    usable_fraction = float(quality.usable.sum() / inside_count) if inside_count else 0.0
    valid_check = _fraction_check(
        check_id="vqa-valid-rgb-fraction",
        metric="valid-rgb-pixel-fraction",
        measured=valid_fraction,
        minimum=VQA_MIN_VALID_FRACTION,
        explanation=(
            "Fraction of AOI pixel centres valid in all calibrated RGB bands; "
            f"{VQA_QUALITY_THRESHOLD_VERSION}."
        ),
    )
    if quality.quality_information == "available":
        usable_check = _fraction_check(
            check_id="vqa-usable-fraction",
            metric="qa-usable-pixel-fraction",
            measured=usable_fraction,
            minimum=VQA_MIN_USABLE_FRACTION,
            explanation=(
                "Fraction of AOI pixel centres valid in RGB and usable under decoded SCL; "
                f"{VQA_QUALITY_THRESHOLD_VERSION}."
            ),
        )
    else:
        usable_check = QualityCheck(
            check_id="vqa-usable-fraction",
            scope="prepared_scene",
            metric="qa-usable-pixel-fraction",
            outcome="unresolved",
            explanation=quality.unavailable_reason or "Quality information is unavailable.",
        )
    checks = [valid_check, usable_check]
    unresolved_ids = [check.check_id for check in checks if check.outcome == "unresolved"]
    if any(check.outcome == "failed" for check in checks):
        state = "not_ready"
        explanation = "Required calibrated or QA-usable coverage failed the VQA input gate."
    elif unresolved_ids:
        state = "unresolved"
        explanation = "Required QA evidence is unavailable; positive VQA readiness is prohibited."
    else:
        state = "ready"
        explanation = "The chip passed provisional RGB-validity and QA-usable coverage gates."
    readiness = TaskReadiness(
        intended_task="optical_single_scene",
        processing_profile=request.processing_profile,
        scenes=[raster.scene],
        state=state,
        quality_check_ids=[check.check_id for check in checks],
        unresolved_check_ids=unresolved_ids,
        explanation=explanation,
    )
    return Phase6QualityContext(
        preparation_job_id=job_id,
        provenance_state=(
            "committed_manifest" if provenance_manifest is not None else "runtime_measured"
        ),
        provenance_manifest=provenance_manifest,
        readiness=readiness,
        quality_checks=checks,
    )


def _fraction_check(
    *,
    check_id: str,
    metric: str,
    measured: float,
    minimum: float,
    explanation: str,
) -> QualityCheck:
    threshold = QualityThreshold(operator="gte", value=minimum, units="fraction")
    return QualityCheck(
        check_id=check_id,
        scope="prepared_scene",
        metric=metric,
        measured_value=measured,
        units="fraction",
        threshold=threshold,
        outcome="passed" if measured >= minimum else "failed",
        explanation=explanation,
    )
