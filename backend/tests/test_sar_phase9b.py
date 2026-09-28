from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import httpx2
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from satquery.api.schemas.sar import SarDiscoveryRequest, SarPreparationRequest
from satquery.processing.sar import SarRasterService
from satquery.providers.catalog.base import CatalogueProviderError
from satquery.providers.catalog.inpe_sar import (
    InpeSarAsset,
    InpeSarProvider,
    InpeSarResolvedScene,
)


def _item(*, assets: tuple[str, ...] = ("VV",)) -> dict[str, Any]:
    base = "https://data.inpe.br/bdc/data/sentinel-1/rtc/v1/2025/01/20/IW/DV/item/"
    values: dict[str, Any] = {
        f"Gamma0_{polarization}": {"href": f"{base}gamma0-{polarization}.tif"}
        for polarization in assets
    }
    values["layover_shadow_mask"] = {"href": f"{base}mask.tif"}
    return {
        "id": "S1A_IW_RTCH_FIXTURE",
        "collection": "sentinel-1-rtc-1",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [0.0, 4.0], [4.0, 4.0], [4.0, 0.0], [0.0, 0.0]]],
        },
        "assets": values,
        "properties": {
            "datetime": "2025-01-20T08:31:11Z",
            "operational_mode": "IW",
            "rtc_dem": "Copernicus 30m Global DEM",
        },
    }


def _aoi() -> dict[str, Any]:
    return {
        "type": "Polygon",
        "coordinates": [
            [[0.0, 0.0], [0.0, 4.0], [4.0, 4.0], [4.0, 0.0], [0.0, 0.0]],
            [[1.0, 1.0], [3.0, 1.0], [3.0, 3.0], [1.0, 3.0], [1.0, 1.0]],
        ],
    }


def test_discovery_preserves_actual_single_polarization() -> None:
    transport = httpx2.MockTransport(
        lambda _request: httpx2.Response(200, json={"features": [_item()]})
    )
    provider = InpeSarProvider(httpx2.AsyncClient(transport=transport))
    response = asyncio.run(
        provider.search(
            SarDiscoveryRequest.model_validate(
                {
                    "aoi": _aoi(),
                    "acquisition": {
                        "start": datetime(2025, 1, 1, tzinfo=UTC),
                        "end": datetime(2025, 2, 1, tzinfo=UTC),
                    },
                }
            )
        )
    )
    assert response.scenes[0].polarizations == ["VV"]
    metadata = response.scenes[0].metadata.outcome
    assert metadata.state == "available"
    assert metadata.metadata.calibration.source_values == "calibrated"


def test_resolver_rejects_unavailable_polarization() -> None:
    transport = httpx2.MockTransport(lambda _request: httpx2.Response(200, json=_item()))
    provider = InpeSarProvider(httpx2.AsyncClient(transport=transport))
    scene = InpeSarProvider._scene(_item())
    with pytest.raises(CatalogueProviderError, match="Available: VV") as failure:
        asyncio.run(provider.resolve(scene.source, "VH"))
    assert failure.value.code == "SAR_POLARIZATION_UNAVAILABLE"


def _write_tiff(path: Path, data: np.ndarray) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=data.shape[1],
        height=data.shape[0],
        count=1,
        dtype=data.dtype,
        crs="EPSG:4326",
        transform=from_origin(0, 4, 1, 1),
        nodata=-32768 if np.issubdtype(data.dtype, np.floating) else None,
    ) as dataset:
        dataset.write(data, 1)


class _FixtureProvider:
    def __init__(self, resolved: InpeSarResolvedScene) -> None:
        self.resolved = resolved

    async def resolve(
        self, _source: object, _polarization: Literal["HH", "HV", "VH", "VV"]
    ) -> InpeSarResolvedScene:
        return self.resolved


def test_aoi_clip_preserves_gamma0_holes_nodata_and_terrain_mask(tmp_path: Path) -> None:
    data_path = tmp_path / "gamma.tif"
    mask_path = tmp_path / "mask.tif"
    values = np.arange(1, 17, dtype=np.float32).reshape(4, 4) / 100.0
    values[0, 0] = -32768
    terrain = np.zeros((4, 4), dtype=np.uint8)
    terrain[0, 1] = 1
    _write_tiff(data_path, values)
    _write_tiff(mask_path, terrain)
    scene = InpeSarProvider._scene(_item())
    resolved = InpeSarResolvedScene(
        scene=scene,
        backscatter=InpeSarAsset(
            polarization="VV", location="data", nodata=-32768.0, checksum="fixture"
        ),
        layover_shadow_mask="mask",
        terrain_model="Copernicus 30m Global DEM",
    )
    paths = {"data": data_path, "mask": mask_path}

    @contextmanager
    def opener(location: str) -> Iterator[Any]:
        with rasterio.open(paths[location]) as dataset:
            yield dataset

    service = SarRasterService(cast(Any, _FixtureProvider(resolved)), opener=opener)
    response = asyncio.run(
        service.prepare(
            SarPreparationRequest.model_validate(
                {"scene": scene.source, "aoi": _aoi(), "polarization": "VV"}
            )
        )
    )
    raster = service.analytical_raster(response.preparation_id)
    assert response.mask.aoi_pixels == 12  # four centre pixels are removed by the hole
    assert response.mask.nodata_pixels == 1
    assert response.mask.layover_or_shadow_pixels == 1
    assert response.mask.valid_pixels == 10
    assert np.isclose(raster.values[3, 3], 0.16)
    assert np.isnan(raster.values[1:3, 1:3]).all()
    assert response.analysis_units == "gamma0_power"
    assert "fixed -25 to 0 dB" in response.display_scaling
    assert service.preview(response.preparation_id).startswith(b"\x89PNG")


def test_all_excluded_aoi_is_rejected(tmp_path: Path) -> None:
    data_path = tmp_path / "gamma.tif"
    mask_path = tmp_path / "mask.tif"
    _write_tiff(data_path, np.ones((4, 4), dtype=np.float32))
    _write_tiff(mask_path, np.ones((4, 4), dtype=np.uint8))
    scene = InpeSarProvider._scene(_item())
    resolved = InpeSarResolvedScene(
        scene=scene,
        backscatter=InpeSarAsset(
            polarization="VV", location="data", nodata=-32768.0, checksum=None
        ),
        layover_shadow_mask="mask",
        terrain_model="Copernicus 30m Global DEM",
    )
    paths = {"data": data_path, "mask": mask_path}

    @contextmanager
    def opener(location: str) -> Iterator[Any]:
        with rasterio.open(paths[location]) as dataset:
            yield dataset

    service = SarRasterService(cast(Any, _FixtureProvider(resolved)), opener=opener)
    with pytest.raises(Exception, match="no usable gamma0 pixels"):
        asyncio.run(
            service.prepare(
                SarPreparationRequest.model_validate(
                    {"scene": scene.source, "aoi": _aoi(), "polarization": "VV"}
                )
            )
        )
