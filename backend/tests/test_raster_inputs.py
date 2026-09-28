from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.warp import transform
from rasterio.windows import Window

from satquery.api.schemas.asset_resolution import (
    AssetResolutionResponse,
    AssetResolutionStatus,
    ResolvedRasterComponent,
)
from satquery.api.schemas.processing import PreparationRequest
from satquery.api.schemas.viewer import (
    AnalysisReadiness,
    AssetAccessibility,
    CatalogueAvailability,
    RenderStatus,
    ResolvedImageryAsset,
    ResolvedImageryAssetIdentity,
    SupportedRenderPreset,
    ViewerSceneIdentity,
)
from satquery.processing import RasterInputError, RasterInputService
from satquery.providers.catalog import ResolvedImagerySourceSet, ResolvedRasterSource

SCENE = ViewerSceneIdentity(
    provider="earth-search",
    collection="sentinel-2-c1-l2a",
    item="synthetic-calibrated-scene",
)
SOURCE_TRANSFORM = from_origin(0, 1000, 100, 100)
SOURCE_CRS = "EPSG:3857"
SOURCE_SHAPE = (10, 10)
SAFE_PREFIX = (
    "https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/sentinel-2-c1-l2a/synthetic/"
)


class StaticProvider:
    def __init__(self, source_set: ResolvedImagerySourceSet) -> None:
        self.source_set = source_set

    async def resolve_imagery_sources(self, _request: object) -> ResolvedImagerySourceSet:
        return self.source_set


class RecordingDataset:
    def __init__(self, dataset: Any, windows: list[Window | None]) -> None:
        self._dataset = dataset
        self._windows = windows

    def __getattr__(self, name: str) -> Any:
        return getattr(self._dataset, name)

    def read(self, *args: object, **kwargs: object) -> Any:
        window = kwargs.get("window")
        self._windows.append(window if isinstance(window, Window) else None)
        return self._dataset.read(*args, **kwargs)


def _wgs84_ring(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    xs, ys = transform(
        SOURCE_CRS,
        "EPSG:4326",
        [point[0] for point in points],
        [point[1] for point in points],
    )
    return list(zip(xs, ys, strict=True))


def _aoi_with_hole() -> dict[str, object]:
    exterior = _wgs84_ring([(210, 790), (790, 790), (790, 210), (210, 210), (210, 790)])
    hole = _wgs84_ring([(410, 590), (590, 590), (590, 410), (410, 410), (410, 590)])
    return {"type": "Polygon", "coordinates": [exterior, hole]}


def _outside_aoi() -> dict[str, object]:
    ring = _wgs84_ring(
        [(20_000, 20_000), (21_000, 20_000), (21_000, 19_000), (20_000, 19_000), (20_000, 20_000)]
    )
    return {"type": "Polygon", "coordinates": [ring]}


def _request(
    *,
    aoi: dict[str, object] | None = None,
    max_output_pixels: int = 1000,
) -> PreparationRequest:
    return PreparationRequest.model_validate(
        {
            "scenes": [SCENE.model_dump()],
            "aoi": aoi or _aoi_with_hole(),
            "required_bands": [
                {"role": "model-blue", "common_name": "blue"},
                {"role": "model-red", "common_name": "red"},
                {"role": "model-green", "common_name": "green"},
            ],
            "intended_task": "optical_single_scene",
            "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
            "options": {
                "grid_policy": "source_aligned",
                "target_resolution_metres": 100.0,
                "continuous_resampling": "nearest",
                "max_output_pixels": max_output_pixels,
            },
        }
    )


def _component(
    role: str,
    band_name: str,
    *,
    scale: float | None,
    offset: float | None,
    nodata: float,
) -> ResolvedRasterComponent:
    return ResolvedRasterComponent(
        identity=ResolvedImageryAssetIdentity(scene=SCENE, asset=role, asset_version="v1"),
        render_role=role,
        band_name=band_name,
        common_name=role,
        band_index=1,
        media_type="image/tiff",
        scale=scale,
        offset=offset,
        nodata=nodata,
        crs=SOURCE_CRS,
        resolution_metres=100.0,
        shape=SOURCE_SHAPE,
        transform=tuple(SOURCE_TRANSFORM),
        access_check="head_succeeded",
        content_length_bytes=4096,
    )


def _source_set(components: list[ResolvedRasterComponent]) -> ResolvedImagerySourceSet:
    now = datetime(2026, 9, 22, tzinfo=UTC)
    resolved = ResolvedImageryAsset(
        identity=ResolvedImageryAssetIdentity(
            scene=SCENE, asset="rgb-synthetic", asset_version="v1"
        ),
        acquisition={"start": now, "end": now},
        media_type="image/tiff",
        bounds=(0.0, 0.0, 0.01, 0.01),
        render_presets=[
            SupportedRenderPreset(
                id="natural-color",
                title="Natural colour",
                description="Synthetic RGB raster used only by the Task 6B test.",
                mode="rgb",
                bands=[component.identity.asset for component in components],
            )
        ],
        default_render_preset="natural-color",
        catalogue_availability=CatalogueAvailability(state="available"),
        asset_accessibility=AssetAccessibility(state="accessible", method="backend_mediated"),
        analysis_readiness=AnalysisReadiness(state="not_assessed", reason="Not assessed."),
        attributions=["Synthetic test fixture."],
        resolved_at=now,
    )
    resolution = AssetResolutionResponse(
        scene=SCENE,
        status=AssetResolutionStatus(state="supported"),
        catalogue_availability=resolved.catalogue_availability,
        asset_accessibility=resolved.asset_accessibility,
        render_status=RenderStatus(state="not_requested"),
        analysis_readiness=resolved.analysis_readiness,
        resolved_asset=resolved,
        components=components,
        attributions=["Synthetic test fixture."],
        checked_at=now,
    )
    return ResolvedImagerySourceSet(
        resolution=resolution,
        sources=tuple(
            ResolvedRasterSource(
                component=component,
                location=f"{SAFE_PREFIX}{component.band_name}.tif",
                expires_at=None,
            )
            for component in components
        ),
    )


def _fixture(
    *, include_crs: bool = True
) -> tuple[
    ResolvedImagerySourceSet,
    dict[str, MemoryFile],
    list[Window | None],
]:
    definitions = [
        ("red", "B04", 0.01, -1.0, 22.0, 0.0),
        ("green", "B03", 0.1, 2.0, 123.0, 100.0),
        ("blue", "B02", 1.0, 0.0, 234.0, 200.0),
    ]
    components = [
        _component(role, name, scale=scale, offset=offset, nodata=nodata)
        for role, name, scale, offset, nodata, _base in definitions
    ]
    memories: dict[str, MemoryFile] = {}
    for component, definition in zip(components, definitions, strict=True):
        base = definition[-1]
        memory = MemoryFile(filename=f"{component.band_name}.tif")
        values = np.arange(100, dtype=np.float32).reshape(10, 10) + base
        with memory.open(
            driver="GTiff",
            width=10,
            height=10,
            count=1,
            dtype="float32",
            crs=SOURCE_CRS if include_crs else None,
            transform=SOURCE_TRANSFORM,
            nodata=component.nodata,
            tiled=False,
        ) as dataset:
            dataset.write(values, 1)
        memories[component.band_name] = memory
    return _source_set(components), memories, []


def _service(
    source_set: ResolvedImagerySourceSet,
    memories: dict[str, MemoryFile],
    windows: list[Window | None],
    *,
    max_pixels: int = 1000,
) -> RasterInputService:
    @contextmanager
    def opener(source: ResolvedRasterSource) -> Iterator[RecordingDataset]:
        with memories[source.component.band_name].open() as dataset:
            yield RecordingDataset(dataset, windows)

    return RasterInputService(
        StaticProvider(source_set),  # type: ignore[arg-type]
        dataset_opener=opener,
        max_pixels=max_pixels,
    )


def _close(memories: dict[str, MemoryFile]) -> None:
    for memory in memories.values():
        memory.close()


def test_windowed_clip_preserves_hole_transform_calibration_and_nodata() -> None:
    source_set, memories, windows = _fixture()
    try:
        result = asyncio.run(_service(source_set, memories, windows).extract(_request()))
    finally:
        _close(memories)

    assert (result.width, result.height) == (6, 6)
    assert result.crs == SOURCE_CRS
    assert result.transform == (100.0, 0.0, 200.0, 0.0, -100.0, 800.0)
    assert result.bounds == (200.0, 200.0, 800.0, 800.0)
    assert result.band_order == ("model-blue", "model-red", "model-green")
    assert result.data.shape == (3, 6, 6)
    assert result.inside_aoi_mask.sum() == 32
    assert not result.inside_aoi_mask[2:4, 2:4].any()
    assert result.band_validity.shape == (3, 6, 6)
    assert result.band_validity.sum(axis=(1, 2)).tolist() == [31, 31, 31]
    assert np.isnan(result.data[1, 0, 0])
    assert result.data[0, 0, 0] == pytest.approx(222.0)
    assert result.data[1, 0, 1] == pytest.approx(-0.77)
    assert result.data[2, 0, 0] == pytest.approx(14.2)
    assert [band.source.asset for band in result.bands] == ["blue", "red", "green"]
    assert [band.units for band in result.bands] == ["1", "1", "1"]
    assert [band.native_resolution_metres for band in result.bands] == [100.0] * 3
    assert [band.method for band in result.bands] == [
        "identity",
        "metadata_scale_offset",
        "metadata_scale_offset",
    ]
    assert len(windows) == 3
    assert all(window is not None and window.width == 6 for window in windows)


@pytest.mark.parametrize(
    ("extraction_request", "max_pixels", "expected_code"),
    [
        (_request(aoi=_outside_aoi()), 1000, "EMPTY_AOI_INTERSECTION"),
        (_request(), 20, "RASTER_RESOURCE_LIMIT"),
    ],
)
def test_rejects_empty_intersections_and_resource_limit(
    extraction_request: PreparationRequest, max_pixels: int, expected_code: str
) -> None:
    source_set, memories, windows = _fixture()
    try:
        with pytest.raises(RasterInputError) as captured:
            asyncio.run(
                _service(source_set, memories, windows, max_pixels=max_pixels).extract(
                    extraction_request
                )
            )
    finally:
        _close(memories)
    assert captured.value.code == expected_code


def test_rejects_missing_source_georeferencing() -> None:
    source_set, memories, windows = _fixture(include_crs=False)
    try:
        with pytest.raises(RasterInputError) as captured:
            asyncio.run(_service(source_set, memories, windows).extract(_request()))
    finally:
        _close(memories)
    assert captured.value.code == "MISSING_GEOREFERENCING"


def test_rejects_expired_trusted_sources_before_opening() -> None:
    source_set, memories, windows = _fixture()
    expired = replace(
        source_set,
        sources=tuple(
            replace(source, expires_at=datetime.now(UTC) - timedelta(seconds=1))
            for source in source_set.sources
        ),
    )
    try:
        with pytest.raises(RasterInputError) as captured:
            asyncio.run(_service(expired, memories, windows).extract(_request()))
    finally:
        _close(memories)
    assert captured.value.code == "RASTER_SOURCE_EXPIRED"
    assert windows == []


def test_request_schema_rejects_client_supplied_raster_locations() -> None:
    payload = _request().model_dump(mode="json")
    payload["url"] = "file:///private/source.tif"
    with pytest.raises(ValueError):
        PreparationRequest.model_validate(payload)
