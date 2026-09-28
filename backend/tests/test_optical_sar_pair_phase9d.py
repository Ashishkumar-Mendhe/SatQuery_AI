"""Known synthetic optical/SAR grids; these are not live product evidence."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from rasterio.warp import transform_bounds

from satquery.api.schemas.catalog import CatalogPolygon
from satquery.api.schemas.processing import OutputGrid, PreparationRequest
from satquery.api.schemas.sar import SarPreparationRequest, SarPreparationResponse
from satquery.api.schemas.viewer import ResolvedImageryAssetIdentity, ViewerSceneIdentity
from satquery.processing.grid import (
    CommonGridResult,
    HarmonizedQualityMasks,
    HarmonizedScene,
)
from satquery.processing.optical_sar_pair import (
    CrossModalTiePoint,
    OpticalSarPairService,
)
from satquery.processing.raster import BandCalibration
from satquery.processing.sar import SarAnalyticalRaster

AOI = {
    "type": "Polygon",
    "coordinates": [[[3.0, 0.0], [3.002, 0.0], [3.002, 0.002], [3.0, 0.002], [3.0, 0.0]]],
}
OPTICAL = ViewerSceneIdentity(
    provider="earth-search", collection="sentinel-2-c1-l2a", item="fixture-optical"
)
SAR = ViewerSceneIdentity(provider="inpe-bdc", collection="sentinel-1-rtc-1", item="fixture-sar")
T0 = datetime(2025, 1, 20, 8, tzinfo=UTC)


def _fixture() -> tuple[
    PreparationRequest,
    SarPreparationRequest,
    CommonGridResult,
    SarPreparationResponse,
    SarAnalyticalRaster,
]:
    optical_request = PreparationRequest.model_validate(
        {
            "scenes": [OPTICAL.model_dump(mode="json")],
            "aoi": AOI,
            "required_bands": [
                {"role": role, "common_name": role} for role in ("red", "green", "blue")
            ],
            "intended_task": "optical_single_scene",
            "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
            "options": {
                "grid_policy": "common_utm",
                "target_resolution_metres": 20.0,
                "continuous_resampling": "bilinear",
                "max_output_pixels": 100,
            },
        }
    )
    sar_request = SarPreparationRequest.model_validate(
        {"scene": SAR.model_dump(mode="json"), "aoi": AOI, "polarization": "VV"}
    )
    grid = OutputGrid(
        crs="EPSG:32631",
        transform=(20.0, 0.0, 500000.0, 0.0, -20.0, 120.0),
        width=6,
        height=6,
        resolution_metres=(20.0, 20.0),
        bounds=(500000.0, 0.0, 500120.0, 120.0),
    )
    aoi = np.ones((6, 6), dtype=bool)
    optical_valid = np.ones((6, 6), dtype=bool)
    optical_valid[0, 0] = False
    clouds = np.zeros((6, 6), dtype=bool)
    clouds[2, 2] = True
    shadows = np.zeros((6, 6), dtype=bool)
    shadows[3, 3] = True
    optical_usable = optical_valid & ~clouds & ~shadows
    zero = np.zeros((6, 6), dtype=bool)
    quality = HarmonizedQualityMasks(
        quality_information="available",
        unavailable_reason=None,
        source_asset="SCL",
        processing_baseline="05.00",
        catalogue_scene_cloud_percent=1.0,
        scl_classes=np.full((6, 6), 4, dtype=np.uint8),
        class_labels={4: "vegetation"},
        outside_aoi=zero.copy(),
        missing_or_invalid=~optical_valid,
        clouds_or_cirrus=clouds,
        cloud_shadows=shadows,
        cast_shadows=zero.copy(),
        snow_or_ice=zero.copy(),
        unknown_quality=zero.copy(),
        usable=optical_usable,
        excluded_any=~optical_usable,
    )
    source = ResolvedImageryAssetIdentity(scene=OPTICAL, asset="visual", asset_version="v1")
    bands = tuple(
        BandCalibration(
            source=source,
            role=role,
            band_name=role,
            band_index=1,
            units="1",
            native_resolution_metres=10.0,
            source_nodata=0.0,
            provider_scale=0.0001,
            provider_offset=0.0,
            applied_scale=0.0001,
            applied_offset=0.0,
            method="metadata_scale_offset",
        )
        for role in ("red", "green", "blue")
    )
    scene = HarmonizedScene(
        scene=OPTICAL,
        data=np.full((3, 6, 6), 0.2, dtype=np.float32),
        band_validity=np.broadcast_to(optical_valid, (3, 6, 6)).copy(),
        valid_data=optical_valid,
        quality=quality,
        band_order=("red", "green", "blue"),
        bands=bands,
        native_resolutions_metres=(10.0, 10.0, 10.0),
        output_resolution_metres=20.0,
        continuous_resampling="bilinear",
        upsampled=False,
        upsampling_explanation=None,
        coverage=(),
    )
    common = CommonGridResult(
        grid=grid,
        aoi_mask=aoi,
        scenes=(scene,),
        joint_valid_data=None,
        joint_usable=None,
        pair_coverage=(),
        area_method="projected_pixel_count",
        registration_status="not_assessed",
        registration_explanation="synthetic fixture",
        radiometric_harmonization="none",
    )
    west, south, east, north = transform_bounds("EPSG:32631", "EPSG:4326", *grid.bounds)
    # Extend one pixel on all sides so every target cell is covered after reprojection.
    dx = (east - west) / 6
    dy = (north - south) / 6
    sar_transform = (dx, 0.0, west - dx, 0.0, -dy, north + dy)
    sar_values = np.full((8, 8), 0.15, dtype=np.float32)
    sar_valid = np.ones((8, 8), dtype=bool)
    terrain = np.zeros((8, 8), dtype=bool)
    terrain[3, 4] = True
    sar_valid[3, 4] = False
    sar_response = SarPreparationResponse.model_validate(
        {
            "preparation_id": "00000000-0000-0000-0000-000000000001",
            "source": SAR.model_dump(mode="json"),
            "acquisition_time": T0 + timedelta(hours=6),
            "polarization": "VV",
            "crs": "EPSG:4326",
            "transform": sar_transform,
            "width": 8,
            "height": 8,
            "bounds": [west - dx, south - dy, east + dx, north + dy],
            "native_resolution_metres": 20.0,
            "analysis_units": "gamma0_power",
            "calibration": "provider calibrated",
            "geometric_processing": "RTC",
            "terrain_model": "fixture DEM",
            "mask": {
                "aoi_pixels": 64,
                "valid_pixels": 63,
                "nodata_pixels": 0,
                "layover_or_shadow_pixels": 1,
            },
            "display_scaling": "not analytical",
            "preview_url": "/api/v1/sar/fixture.png",
            "processing_version": "fixture",
            "warnings": [],
        }
    )
    sar_raster = SarAnalyticalRaster(
        values=sar_values,
        valid_mask=sar_valid,
        inside_aoi_mask=np.ones((8, 8), dtype=bool),
        layover_shadow_mask=terrain,
        crs="EPSG:4326",
        transform=sar_transform,
    )
    return optical_request, sar_request, common, sar_response, sar_raster


def test_reprojects_native_power_masks_and_reports_joint_coverage() -> None:
    optical_request, sar_request, grid, response, raster = _fixture()
    result = OpticalSarPairService().prepare(
        optical_request, sar_request, grid, T0, response, raster
    )
    assert result.state == "insufficient_evidence"  # no independent tie points
    assert result.time_gap_hours == 6
    assert result.coverage.aoi_pixels == 36
    assert result.coverage.optical_usable_pixels == 33
    assert result.coverage.joint_usable_pixels == int(result.joint_usable.sum())
    assert result.coverage.joint_usable_area_square_metres == (
        result.coverage.joint_usable_pixels * 400
    )
    assert not result.joint_usable[2, 2]  # actual SCL cloud
    assert not result.joint_usable[3, 3]  # actual SCL cloud shadow
    assert np.count_nonzero(result.sar_layover_shadow) >= 1
    assert not np.any(result.joint_usable & result.sar_layover_shadow)
    assert np.isnan(result.sar_resampled_values[~result.sar_valid]).all()
    assert np.allclose(result.sar_resampled_values[result.sar_valid], 0.15)
    assert result.optical_units == ("1", "1", "1")
    assert result.sar_units == "gamma0_power"
    assert result.sar_native_raster is raster
    assert result.sar_native_raster.values[4, 4] == pytest.approx(0.15)
    assert result.grid.grid.crs == "EPSG:32631"


def test_missing_coverage_and_quality_reject() -> None:
    optical_request, sar_request, grid, response, raster = _fixture()
    raster.valid_mask[:] = False
    response = response.model_copy(
        update={"mask": response.mask.model_copy(update={"valid_pixels": 0, "nodata_pixels": 63})}
    )
    result = OpticalSarPairService().prepare(
        optical_request, sar_request, grid, T0, response, raster
    )
    assert result.coverage.joint_usable_pixels == 0
    assert any("No joint valid" in reason for reason in result.reasons)
    assert result.state == "insufficient_evidence"


def test_cloud_covered_optical_and_large_time_gap_stay_explicit() -> None:
    optical_request, sar_request, grid, response, raster = _fixture()
    covered_quality = replace(
        grid.scenes[0].quality,
        clouds_or_cirrus=np.ones((6, 6), dtype=bool),
        usable=np.zeros((6, 6), dtype=bool),
        excluded_any=np.ones((6, 6), dtype=bool),
    )
    covered_grid = replace(grid, scenes=(replace(grid.scenes[0], quality=covered_quality),))
    covered = OpticalSarPairService().prepare(
        optical_request, sar_request, covered_grid, T0, response, raster
    )
    assert covered.state == "insufficient_evidence"
    assert covered.coverage.joint_usable_pixels == 0
    assert not np.any(covered.joint_usable)
    assert any("No joint valid" in reason for reason in covered.reasons)

    distant = response.model_copy(update={"acquisition_time": T0 + timedelta(days=45)})
    dated = OpticalSarPairService().prepare(optical_request, sar_request, grid, T0, distant, raster)
    assert dated.time_gap_hours == 45 * 24
    assert any("more than 30 days" in warning for warning in dated.warnings)
    assert dated.alignment.state == "unavailable"


def test_unknown_optical_quality_never_becomes_clear() -> None:
    optical_request, sar_request, grid, response, raster = _fixture()
    scene = replace(
        grid.scenes[0],
        quality=replace(grid.scenes[0].quality, quality_information="unavailable"),
    )
    grid = replace(grid, scenes=(scene,))
    result = OpticalSarPairService().prepare(
        optical_request, sar_request, grid, T0, response, raster
    )
    assert result.state == "insufficient_evidence"
    assert any("classification is unavailable" in reason for reason in result.reasons)


def test_alignment_requires_distributed_independent_correspondences() -> None:
    optical_request, sar_request, grid, response, raster = _fixture()
    points = tuple(
        CrossModalTiePoint(row, col, row + 0.1, col + 0.1)
        for row, col in ((1.0, 1.0), (1.0, 4.0), (4.0, 1.0), (4.0, 4.0))
    )
    result = OpticalSarPairService().prepare(
        optical_request,
        sar_request,
        grid,
        T0,
        response,
        raster,
        independent_tie_points=points,
    )
    assert result.alignment.state == "verified"
    assert result.alignment.distributed_quadrants == 4
    assert result.state == "analysis_ready"
    bad = (*points[:-1], CrossModalTiePoint(4.0, 4.0, 5.0, 4.0))
    rejected = OpticalSarPairService().prepare(
        optical_request,
        sar_request,
        grid,
        T0,
        response,
        raster,
        independent_tie_points=bad,
    )
    assert rejected.alignment.state == "inconclusive"
    assert rejected.state == "insufficient_evidence"


def test_rejects_different_aoi_and_unsupported_l_band() -> None:
    optical_request, sar_request, grid, response, raster = _fixture()
    wrong_aoi = sar_request.model_copy(
        update={
            "aoi": CatalogPolygon.model_validate(
                {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [4.0, 0.0],
                            [4.002, 0.0],
                            [4.002, 0.002],
                            [4.0, 0.002],
                            [4.0, 0.0],
                        ]
                    ],
                }
            )
        }
    )
    with pytest.raises(ValueError, match="identical AOI"):
        OpticalSarPairService().prepare(optical_request, wrong_aoi, grid, T0, response, raster)
    nisar_request = sar_request.model_copy(
        update={
            "scene": ViewerSceneIdentity(
                provider="nasa-cmr", collection="NISAR_L2_GCOV_PROVISIONAL_V1", item="fixture"
            )
        }
    )
    with pytest.raises(ValueError, match="not NISAR L-band"):
        OpticalSarPairService().prepare(optical_request, nisar_request, grid, T0, response, raster)
    inconsistent = response.model_copy(
        update={"mask": response.mask.model_copy(update={"valid_pixels": 64})}
    )
    with pytest.raises(ValueError, match="mask counts differ"):
        OpticalSarPairService().prepare(
            optical_request, sar_request, grid, T0, inconsistent, raster
        )
