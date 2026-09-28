"""Bounded spatial co-location of Sentinel-2 L2A and INPE Sentinel-1 RTC.

This does not compare optical reflectance with C-band gamma-0 or infer change.
Independent, distributed tie points are required before the pair is called
analysis-ready; a shared output grid is not feature registration evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

import numpy as np
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import reproject

from satquery.api.schemas.asset_resolution import AssetResolutionRequest
from satquery.api.schemas.processing import OutputGrid, PreparationRequest
from satquery.api.schemas.sar import SarPreparationRequest, SarPreparationResponse
from satquery.api.schemas.viewer import ViewerSceneIdentity
from satquery.processing.area import projected_pixel_area_square_metres
from satquery.processing.grid import CommonGridResult, CommonGridService, ScenePreparationInput
from satquery.processing.quality import QualityMaskService
from satquery.processing.raster import CalibratedRasterInput, RasterInputService
from satquery.processing.sar import SarAnalyticalRaster, SarRasterService
from satquery.providers.catalog.base import CatalogueProvider

OPTICAL_SAR_PAIR_VERSION = "9d-optical-sar-colocation-v1"


@dataclass(frozen=True, slots=True)
class OpticalSarPairParameters:
    version: str = OPTICAL_SAR_PAIR_VERSION
    continuous_resampling: Literal["bilinear"] = "bilinear"
    categorical_resampling: Literal["nearest"] = "nearest"
    min_joint_usable_aoi_percent: float = 10.0
    max_tie_point_residual_pixels: float = 0.5
    min_distributed_tie_points: int = 4
    temporal_warning_days: float = 30.0


@dataclass(frozen=True, slots=True)
class CrossModalTiePoint:
    """Independently identified corresponding features, in output-grid pixel coordinates."""

    optical_row: float
    optical_column: float
    sar_row: float
    sar_column: float


@dataclass(frozen=True, slots=True)
class CrossModalAlignment:
    state: Literal["verified", "inconclusive", "unavailable"]
    method: Literal["independent_tie_point_residual"]
    coordinate_space: Literal["output_grid_pixel_centres"]
    tie_point_count: int
    distributed_quadrants: int
    median_residual_pixels: float | None
    maximum_residual_pixels: float | None
    threshold_pixels: float
    explanation: str


@dataclass(frozen=True, slots=True)
class OpticalSarPairCoverage:
    denominator_name: Literal["inside_aoi"]
    aoi_pixels: int
    optical_usable_pixels: int
    sar_valid_pixels: int
    joint_valid_pixels: int
    joint_usable_pixels: int
    joint_usable_percent: float
    joint_usable_area_square_metres: float
    pixel_area_square_metres: float


@dataclass(frozen=True, slots=True)
class OpticalSarPairOutcome:
    state: Literal["analysis_ready", "insufficient_evidence"]
    processing_version: str
    parameters: OpticalSarPairParameters
    optical_source: ViewerSceneIdentity
    sar_source: ViewerSceneIdentity
    optical_acquired_at: datetime
    sar_acquired_at: datetime
    time_gap_hours: float
    grid: CommonGridResult
    optical_native_raster: CalibratedRasterInput | None
    sar_preparation: SarPreparationResponse
    sar_native_raster: SarAnalyticalRaster
    optical_units: tuple[str, ...]
    sar_units: Literal["gamma0_power"]
    sar_native_resolution_metres: float
    sar_resampled_values: np.ndarray
    sar_valid: np.ndarray
    sar_layover_shadow: np.ndarray
    joint_valid: np.ndarray
    joint_usable: np.ndarray
    coverage: OpticalSarPairCoverage
    alignment: CrossModalAlignment
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


class OpticalSarPairService:
    """Joins trusted Phase 6/9B outputs; no client asset locations are accepted."""

    def __init__(self, parameters: OpticalSarPairParameters | None = None) -> None:
        self.parameters = parameters or OpticalSarPairParameters()
        if not 0 <= self.parameters.min_joint_usable_aoi_percent <= 100:
            raise ValueError("min joint coverage must be a percentage")
        if not 0 < self.parameters.max_tie_point_residual_pixels <= 2:
            raise ValueError("tie-point residual bound must be within two pixels")

    async def prepare_real(
        self,
        optical_request: PreparationRequest,
        sar_request: SarPreparationRequest,
        optical_provider: CatalogueProvider,
        sar_service: SarRasterService,
    ) -> OpticalSarPairOutcome:
        """Resolve actual scene IDs through the existing trusted provider services."""

        self._validate_request(optical_request, sar_request)
        catalogue_scene = await optical_provider.item(
            optical_request.scenes[0].collection, optical_request.scenes[0].item
        )
        if (
            catalogue_scene.provider.id != optical_request.scenes[0].provider
            or catalogue_scene.collection.id != optical_request.scenes[0].collection
            or catalogue_scene.provider_asset_id != optical_request.scenes[0].item
        ):
            raise ValueError("optical catalogue identity changed during resolution")
        resolved = await optical_provider.resolve_imagery_sources(
            AssetResolutionRequest(scene=optical_request.scenes[0])
        )
        if not resolved.sources:
            raise ValueError("selected optical scene has no resolved scientific bands")
        source_request = optical_request.model_copy(
            update={
                "options": optical_request.options.model_copy(
                    update={
                        "grid_policy": "source_aligned",
                        "target_resolution_metres": resolved.sources[0].component.resolution_metres,
                    }
                )
            }
        )
        raster = await RasterInputService(optical_provider).extract(source_request)
        quality = await QualityMaskService(optical_provider).decode(raster)
        optical_grid = CommonGridService(max_pixels=1_000_000).prepare(
            optical_request, (ScenePreparationInput(raster=raster, quality=quality),)
        )
        sar_response = await sar_service.prepare(sar_request)
        sar_raster = sar_service.analytical_raster(sar_response.preparation_id)
        return self.prepare(
            optical_request,
            sar_request,
            optical_grid,
            catalogue_scene.acquisition.start,
            sar_response,
            sar_raster,
            optical_native_raster=raster,
        )

    def prepare(
        self,
        optical_request: PreparationRequest,
        sar_request: SarPreparationRequest,
        optical_grid: CommonGridResult,
        optical_acquired_at: datetime,
        sar_response: SarPreparationResponse,
        sar_raster: SarAnalyticalRaster,
        *,
        optical_native_raster: CalibratedRasterInput | None = None,
        independent_tie_points: tuple[CrossModalTiePoint, ...] = (),
    ) -> OpticalSarPairOutcome:
        self._validate_request(optical_request, sar_request)
        if (
            len(optical_grid.scenes) != 1
            or optical_grid.scenes[0].scene != optical_request.scenes[0]
        ):
            raise ValueError("optical grid does not belong to the selected optical scene")
        if (
            optical_native_raster is not None
            and optical_native_raster.scene != optical_request.scenes[0]
        ):
            raise ValueError("native optical raster belongs to a different source")
        if (
            sar_response.source != sar_request.scene
            or sar_response.polarization != sar_request.polarization
        ):
            raise ValueError("SAR preparation does not belong to the selected source/layer")
        if optical_acquired_at.tzinfo is None or optical_acquired_at.utcoffset() is None:
            raise ValueError("optical acquisition requires an offset-aware timestamp")
        if (
            sar_response.acquisition_time.tzinfo is None
            or sar_response.acquisition_time.utcoffset() is None
        ):
            raise ValueError("SAR acquisition requires an offset-aware timestamp")
        if sar_raster.values.shape != (sar_response.height, sar_response.width):
            raise ValueError("SAR values and declared source grid differ")
        if any(
            mask.shape != sar_raster.values.shape
            for mask in (
                sar_raster.valid_mask,
                sar_raster.inside_aoi_mask,
                sar_raster.layover_shadow_mask,
            )
        ):
            raise ValueError("SAR masks and source grid differ")
        if sar_raster.crs != sar_response.crs or not np.allclose(
            sar_raster.transform, sar_response.transform, rtol=0, atol=1e-9
        ):
            raise ValueError("SAR raster georeferencing differs from its preparation record")
        if (
            int(np.count_nonzero(sar_raster.inside_aoi_mask)) != sar_response.mask.aoi_pixels
            or int(np.count_nonzero(sar_raster.valid_mask)) != sar_response.mask.valid_pixels
            or int(np.count_nonzero(sar_raster.layover_shadow_mask))
            != sar_response.mask.layover_or_shadow_pixels
        ):
            raise ValueError("SAR source mask counts differ from the preparation record")
        if (
            np.any(sar_raster.valid_mask & ~sar_raster.inside_aoi_mask)
            or np.any(sar_raster.valid_mask & sar_raster.layover_shadow_mask)
            or not np.isfinite(sar_raster.values[sar_raster.valid_mask]).all()
        ):
            raise ValueError("SAR source validity contradicts AOI, terrain mask, or values")
        grid = optical_grid.grid
        shape = (grid.height, grid.width)
        if optical_grid.aoi_mask.shape != shape or optical_grid.scenes[0].data.shape[1:] != shape:
            raise ValueError("optical data and AOI do not share the declared grid")
        optical = optical_grid.scenes[0]
        if (
            optical.band_order != ("red", "green", "blue")
            or len(optical.bands) != 3
            or any(
                band.units != "1" or band.source.scene != optical.scene for band in optical.bands
            )
        ):
            raise ValueError(
                "9D requires calibrated Sentinel-2 RGB reflectance on the optical grid"
            )
        if grid.width * grid.height > 1_000_000:
            raise ValueError("optical/SAR pair exceeds the one-million-pixel limit")
        source_transform = Affine(*sar_raster.transform)
        target_transform = Affine(*grid.transform)
        source_valid = sar_raster.valid_mask & sar_raster.inside_aoi_mask
        source_values = np.where(source_valid, sar_raster.values, np.nan).astype(np.float32)
        values = np.full(shape, np.nan, dtype=np.float32)
        reproject(
            source_values,
            values,
            src_transform=source_transform,
            src_crs=sar_raster.crs,
            src_nodata=np.nan,
            dst_transform=target_transform,
            dst_crs=grid.crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
        valid = _nearest_mask(source_valid, source_transform, sar_raster.crs, grid)
        valid &= optical_grid.aoi_mask & np.isfinite(values)
        values[~valid] = np.nan
        terrain_invalid = (
            _nearest_mask(sar_raster.layover_shadow_mask, source_transform, sar_raster.crs, grid)
            & optical_grid.aoi_mask
        )
        joint_valid = optical.valid_data & valid
        joint_usable = optical.quality.usable & valid
        aoi_pixels = int(np.count_nonzero(optical_grid.aoi_mask))
        if aoi_pixels == 0:
            raise ValueError("optical/SAR pair AOI has no grid-cell centres")
        pixel_area = projected_pixel_area_square_metres(grid)
        usable_pixels = int(np.count_nonzero(joint_usable))
        coverage = OpticalSarPairCoverage(
            denominator_name="inside_aoi",
            aoi_pixels=aoi_pixels,
            optical_usable_pixels=int(np.count_nonzero(optical.quality.usable)),
            sar_valid_pixels=int(np.count_nonzero(valid)),
            joint_valid_pixels=int(np.count_nonzero(joint_valid)),
            joint_usable_pixels=usable_pixels,
            joint_usable_percent=100 * usable_pixels / aoi_pixels,
            joint_usable_area_square_metres=usable_pixels * pixel_area,
            pixel_area_square_metres=pixel_area,
        )
        alignment = _alignment(independent_tie_points, joint_usable, self.parameters)
        gap_hours = (
            abs((sar_response.acquisition_time - optical_acquired_at).total_seconds()) / 3600
        )
        reasons: list[str] = []
        warnings: list[str] = []
        if optical.quality.quality_information != "available":
            reasons.append(
                "Optical scene classification is unavailable; cloud/shadow exclusion is unknown."
            )
        if coverage.joint_usable_pixels == 0:
            reasons.append("No joint valid, quality-usable pixels overlap inside the AOI.")
        elif coverage.joint_usable_percent < self.parameters.min_joint_usable_aoi_percent:
            reasons.append(
                "Joint usable AOI coverage is below the provisional engineering minimum."
            )
        if alignment.state != "verified":
            reasons.append(
                "Cross-modal feature alignment is unverified or inadequate; "
                "a common grid is insufficient."
            )
        if gap_hours > 24 * self.parameters.temporal_warning_days:
            warnings.append(
                "Acquisitions are more than 30 days apart; temporal differences may dominate."
            )
        if grid.resolution_metres[0] < sar_response.native_resolution_metres or optical.upsampled:
            warnings.append(
                "At least one layer was upsampled; output pixels add no native spatial detail."
            )
        warnings.append(
            "Optical reflectance and Sentinel-1 C-band gamma-0 retain different units; "
            "no numerical cross-sensor comparison is authorized."
        )
        return OpticalSarPairOutcome(
            state="analysis_ready" if not reasons else "insufficient_evidence",
            processing_version=self.parameters.version,
            parameters=self.parameters,
            optical_source=optical.scene,
            sar_source=sar_response.source,
            optical_acquired_at=optical_acquired_at.astimezone(UTC),
            sar_acquired_at=sar_response.acquisition_time.astimezone(UTC),
            time_gap_hours=gap_hours,
            grid=optical_grid,
            optical_native_raster=optical_native_raster,
            sar_preparation=sar_response,
            sar_native_raster=sar_raster,
            optical_units=tuple(band.units for band in optical.bands),
            sar_units=sar_response.analysis_units,
            sar_native_resolution_metres=sar_response.native_resolution_metres,
            sar_resampled_values=values,
            sar_valid=valid,
            sar_layover_shadow=terrain_invalid,
            joint_valid=joint_valid,
            joint_usable=joint_usable,
            coverage=coverage,
            alignment=alignment,
            reasons=tuple(reasons),
            warnings=tuple(warnings),
        )

    @staticmethod
    def _validate_request(
        optical_request: PreparationRequest, sar_request: SarPreparationRequest
    ) -> None:
        if (
            optical_request.intended_task != "optical_single_scene"
            or len(optical_request.scenes) != 1
        ):
            raise ValueError("9D requires one Sentinel-2 L2A optical scene")
        if tuple(band.role for band in optical_request.required_bands) != ("red", "green", "blue"):
            raise ValueError("9D requires calibrated red, green, and blue optical bands")
        if tuple(band.common_name for band in optical_request.required_bands) != (
            "red",
            "green",
            "blue",
        ):
            raise ValueError("9D requires actual red, green, and blue source bands")
        if (
            sar_request.scene.provider != "inpe-bdc"
            or sar_request.scene.collection != "sentinel-1-rtc-1"
        ):
            raise ValueError("9D supports only INPE Sentinel-1 C-band RTC, not NISAR L-band")
        if optical_request.aoi.model_dump(mode="json") != sar_request.aoi.model_dump(mode="json"):
            raise ValueError("optical and SAR requests must use the identical AOI")
        if optical_request.options.grid_policy != "common_utm":
            raise ValueError("9D requires the AOI-defined common UTM grid")


def _nearest_mask(
    source: np.ndarray, source_transform: Affine, source_crs: str, grid: OutputGrid
) -> np.ndarray:
    # A zero category is a real False value; it is not source or destination nodata.
    output = np.zeros((grid.height, grid.width), dtype=np.uint8)
    reproject(
        source.astype(np.uint8),
        output,
        src_transform=source_transform,
        src_crs=source_crs,
        src_nodata=None,
        dst_transform=Affine(*grid.transform),
        dst_crs=grid.crs,
        dst_nodata=None,
        resampling=Resampling.nearest,
        init_dest_nodata=False,
    )
    return cast(np.ndarray, output != 0)


def _alignment(
    points: tuple[CrossModalTiePoint, ...],
    usable: np.ndarray,
    parameters: OpticalSarPairParameters,
) -> CrossModalAlignment:
    if not points:
        return CrossModalAlignment(
            "unavailable",
            "independent_tie_point_residual",
            "output_grid_pixel_centres",
            0,
            0,
            None,
            None,
            parameters.max_tie_point_residual_pixels,
            "No independently identified cross-modal tie points are available.",
        )
    height, width = usable.shape
    residuals: list[float] = []
    quadrants: set[tuple[int, int]] = set()
    for point in points:
        coordinates = (point.optical_row, point.optical_column, point.sar_row, point.sar_column)
        if not all(np.isfinite(value) for value in coordinates):
            continue
        if not all(
            0 <= row < height and 0 <= col < width
            for row, col in (
                (point.optical_row, point.optical_column),
                (point.sar_row, point.sar_column),
            )
        ):
            continue
        optical_cell = (round(point.optical_row), round(point.optical_column))
        sar_cell = (round(point.sar_row), round(point.sar_column))
        if not usable[min(optical_cell[0], height - 1), min(optical_cell[1], width - 1)]:
            continue
        if not usable[min(sar_cell[0], height - 1), min(sar_cell[1], width - 1)]:
            continue
        residuals.append(
            float(
                np.hypot(point.optical_row - point.sar_row, point.optical_column - point.sar_column)
            )
        )
        quadrants.add(
            (int(point.optical_row >= height / 2), int(point.optical_column >= width / 2))
        )
    enough = len(residuals) >= parameters.min_distributed_tie_points and len(quadrants) == 4
    max_residual = max(residuals) if residuals else None
    verified = (
        enough
        and max_residual is not None
        and max_residual <= parameters.max_tie_point_residual_pixels
    )
    return CrossModalAlignment(
        "verified" if verified else "inconclusive",
        "independent_tie_point_residual",
        "output_grid_pixel_centres",
        len(residuals),
        len(quadrants),
        float(np.median(residuals)) if residuals else None,
        max_residual,
        parameters.max_tie_point_residual_pixels,
        "Independent corresponding features are distributed and within the residual bound."
        if verified
        else "Tie points are missing, insufficiently distributed, masked, or exceed the "
        "residual bound.",
    )
