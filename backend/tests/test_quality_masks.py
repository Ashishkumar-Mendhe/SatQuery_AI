from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from satquery.api.schemas.viewer import ResolvedImageryAssetIdentity, ViewerSceneIdentity
from satquery.processing import CalibratedRasterInput, QualityMaskError, QualityMaskService
from satquery.providers.catalog import (
    QualityRasterMetadata,
    ResolvedQualityRasterSource,
    ResolvedQualitySourceSet,
)

SCENE = ViewerSceneIdentity(
    provider="earth-search",
    collection="sentinel-2-c1-l2a",
    item="synthetic-quality-scene",
)
SAFE_LOCATION = (
    "https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/"
    "sentinel-2-c1-l2a/synthetic/SCL.tif"
)


class StaticQualityProvider:
    def __init__(self, resolved: ResolvedQualitySourceSet) -> None:
        self.resolved = resolved

    async def resolve_quality_source(self, _request: object) -> ResolvedQualitySourceSet:
        return self.resolved


class OppositeConventionDataset:
    def __init__(self, dataset: Any) -> None:
        self._dataset = dataset

    def __getattr__(self, name: str) -> Any:
        return getattr(self._dataset, name)

    def read_masks(self, *args: object, **kwargs: object) -> np.ndarray:
        return np.zeros_like(self._dataset.read_masks(*args, **kwargs))


def _raster(
    height: int,
    width: int,
    *,
    inside: np.ndarray | None = None,
    validity: np.ndarray | None = None,
) -> CalibratedRasterInput:
    transform = from_origin(0, height * 10, 10, 10)
    inside_mask = np.ones((height, width), dtype=bool) if inside is None else inside
    band_validity = np.ones((3, height, width), dtype=bool) if validity is None else validity
    return CalibratedRasterInput(
        scene=SCENE,
        data=np.zeros((3, height, width), dtype=np.float32),
        inside_aoi_mask=inside_mask,
        band_validity=band_validity,
        crs="EPSG:3857",
        transform=tuple(transform)[:6],
        bounds=(0.0, 0.0, width * 10.0, height * 10.0),
        width=width,
        height=height,
        band_order=("red", "green", "blue"),
        bands=(),
    )


def _available_source(
    classes: np.ndarray,
    *,
    resolution: float = 10.0,
) -> tuple[ResolvedQualitySourceSet, MemoryFile]:
    height, width = classes.shape
    transform = from_origin(0, height * resolution, resolution, resolution)
    memory = MemoryFile(filename="synthetic-scl.tif")
    with memory.open(
        driver="GTiff",
        width=width,
        height=height,
        count=1,
        dtype="uint8",
        crs="EPSG:3857",
        transform=transform,
        nodata=0,
    ) as dataset:
        dataset.write(classes.astype(np.uint8), 1)
    source = ResolvedQualityRasterSource(
        metadata=QualityRasterMetadata(
            identity=ResolvedImageryAssetIdentity(scene=SCENE, asset="scl", asset_version="v1"),
            quality_kind="sentinel-2-scl",
            band_index=1,
            media_type="image/tiff",
            nodata=0.0,
            crs="EPSG:3857",
            resolution_metres=resolution,
            shape=(height, width),
            transform=tuple(transform),
            content_length_bytes=4096,
        ),
        location=SAFE_LOCATION,
        expires_at=None,
    )
    return (
        ResolvedQualitySourceSet(
            scene=SCENE,
            state="available",
            source=source,
            processing_baseline="05.11",
            catalogue_scene_cloud_percent=28.287384,
            reason=None,
        ),
        memory,
    )


def _decode(
    raster: CalibratedRasterInput,
    resolved: ResolvedQualitySourceSet,
    memory: MemoryFile | None,
) -> Any:
    @contextmanager
    def opener(_source: ResolvedQualityRasterSource) -> Iterator[Any]:
        assert memory is not None
        with memory.open() as dataset:
            yield dataset

    service = QualityMaskService(
        StaticQualityProvider(resolved),  # type: ignore[arg-type]
        dataset_opener=opener,
    )
    return asyncio.run(service.decode(raster))


def _coverage(result: Any, name: str) -> Any:
    return next(item for item in result.coverage if item.name == name)


def test_decodes_all_official_scl_classes_with_distinct_masks() -> None:
    classes = np.arange(12, dtype=np.uint8).reshape(3, 4)
    resolved, memory = _available_source(classes)
    try:
        result = _decode(_raster(3, 4), resolved, memory)
    finally:
        memory.close()

    assert result.class_labels[0] == "no_data"
    assert result.class_labels[10] == "thin_cirrus"
    assert result.missing_or_invalid[0].tolist() == [True, True, False, False]
    assert result.cast_shadows[0, 2]
    assert result.cloud_shadows[0, 3]
    assert result.usable[1].tolist() == [True, True, True, False]
    assert result.unknown_quality[1, 3]
    assert result.clouds_or_cirrus[2].tolist() == [True, True, True, False]
    assert result.snow_or_ice[2, 3]
    assert result.catalogue_scene_cloud_percent == 28.287384
    assert _coverage(result, "clouds_or_cirrus").denominator_name == "quality_assessed"


def test_missing_qa_is_unknown_and_never_assumed_clear() -> None:
    resolved = ResolvedQualitySourceSet(
        scene=SCENE,
        state="unavailable",
        source=None,
        processing_baseline="05.11",
        catalogue_scene_cloud_percent=12.5,
        reason="Synthetic SCL asset is absent.",
    )
    result = _decode(_raster(2, 2), resolved, None)

    assert result.quality_information == "unavailable"
    assert result.unknown_quality.all()
    assert not result.usable.any()
    assert not result.clouds_or_cirrus.any()
    assert _coverage(result, "clouds_or_cirrus").denominator_pixels == 0
    assert _coverage(result, "clouds_or_cirrus").percent is None
    assert result.catalogue_scene_cloud_percent == 12.5


def test_overlapping_exclusions_are_counted_once_in_excluded_union() -> None:
    classes = np.array([[8, 4], [4, 4]], dtype=np.uint8)
    validity = np.ones((3, 2, 2), dtype=bool)
    validity[:, 0, 0] = False
    resolved, memory = _available_source(classes)
    try:
        result = _decode(_raster(2, 2, validity=validity), resolved, memory)
    finally:
        memory.close()

    assert result.missing_or_invalid.sum() == 1
    assert result.clouds_or_cirrus.sum() == 1
    assert result.excluded_any.sum() == 1
    assert _coverage(result, "excluded_any").pixel_count == 1
    assert _coverage(result, "excluded_any").denominator_pixels == 4


def test_all_invalid_aoi_has_no_usable_pixels() -> None:
    classes = np.array([[4, 5], [6, 8]], dtype=np.uint8)
    validity = np.zeros((3, 2, 2), dtype=bool)
    resolved, memory = _available_source(classes)
    try:
        result = _decode(_raster(2, 2, validity=validity), resolved, memory)
    finally:
        memory.close()

    assert result.missing_or_invalid.all()
    assert result.excluded_any.all()
    assert not result.usable.any()
    assert _coverage(result, "excluded_any").percent == 100.0


def test_valid_dark_water_pixels_remain_usable() -> None:
    classes = np.full((2, 2), 6, dtype=np.uint8)
    resolved, memory = _available_source(classes)
    raster = _raster(2, 2)
    assert np.all(raster.data == 0)
    try:
        result = _decode(raster, resolved, memory)
    finally:
        memory.close()

    assert result.usable.all()
    assert not result.missing_or_invalid.any()
    assert not result.unknown_quality.any()


def test_nearest_resampling_preserves_categorical_labels() -> None:
    classes = np.array([[4, 8], [3, 11]], dtype=np.uint8)
    resolved, memory = _available_source(classes, resolution=20.0)
    try:
        result = _decode(_raster(4, 4), resolved, memory)
    finally:
        memory.close()

    assert set(np.unique(result.scl_classes)) == {3, 4, 8, 11}
    assert np.all(result.scl_classes[:2, :2] == 4)
    assert np.all(result.scl_classes[:2, 2:] == 8)
    assert np.all(result.scl_classes[2:, :2] == 3)
    assert np.all(result.scl_classes[2:, 2:] == 11)


def test_rejects_noninverse_gdal_and_numpy_mask_conventions() -> None:
    resolved, memory = _available_source(np.full((2, 2), 4, dtype=np.uint8))

    @contextmanager
    def opener(_source: ResolvedQualityRasterSource) -> Iterator[Any]:
        with memory.open() as dataset:
            yield OppositeConventionDataset(dataset)

    service = QualityMaskService(
        StaticQualityProvider(resolved),  # type: ignore[arg-type]
        dataset_opener=opener,
    )
    try:
        with pytest.raises(QualityMaskError) as captured:
            asyncio.run(service.decode(_raster(2, 2)))
    finally:
        memory.close()
    assert captured.value.code == "QA_MASK_CONVENTION_MISMATCH"
