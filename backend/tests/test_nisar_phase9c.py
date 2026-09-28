from __future__ import annotations

from pathlib import Path
from typing import Any

import h5py
import httpx2
import numpy as np
import pytest
from conftest import UnavailableDatabase, make_settings
from fastapi.testclient import TestClient

from satquery.api.schemas.nisar import NisarDiscoveryRequest, NisarIngestionRequest
from satquery.main import create_app
from satquery.processing.nisar import NisarGcovIngestionService
from satquery.providers.catalog.nisar_cmr import NisarCmrProvider, NisarResolvedProduct

GRANULE = (
    "NISAR_L2_PR_GCOV_023_040_D_124_4005_SHSH_A_20260617T000743_20260617T000802_P05023_F_P_J_001"
)
CONCEPT = "G4250117587-ASF"


def _umm(*, instrument: str = "L-SAR") -> dict[str, Any]:
    attributes = {
        "FREQUENCIES": ["A", "B"],
        "FREQUENCY_A_POLARIZATION": ["HH"],
        "FREQUENCY_B_POLARIZATION": ["HH"],
        "FREQUENCY_A_RANGE_BANDWIDTH": ["40"],
        "FREQUENCY_B_RANGE_BANDWIDTH": ["5"],
        "FULL_FRAME": ["FALSE"],
        "JOINT_OBSERVATION": ["FALSE"],
        "PRODUCT_VERSION": ["1.0.11"],
    }
    return {
        "GranuleUR": GRANULE,
        "CollectionReference": {"ShortName": "NISAR_L2_GCOV_PROVISIONAL_V1"},
        "Platforms": [{"ShortName": "NISAR", "Instruments": [{"ShortName": instrument}]}],
        "TemporalExtent": {
            "RangeDateTime": {
                "BeginningDateTime": "2026-06-17T00:07:43Z",
                "EndingDateTime": "2026-06-17T00:08:02.999342Z",
            }
        },
        "SpatialExtent": {
            "HorizontalSpatialDomain": {
                "Geometry": {
                    "GPolygons": [
                        {
                            "Boundary": {
                                "Points": [
                                    {"Longitude": -60.0, "Latitude": -80.0},
                                    {"Longitude": -59.0, "Latitude": -80.0},
                                    {"Longitude": -59.0, "Latitude": -79.0},
                                    {"Longitude": -60.0, "Latitude": -79.0},
                                    {"Longitude": -60.0, "Latitude": -80.0},
                                ]
                            }
                        }
                    ]
                }
            }
        },
        "AdditionalAttributes": [
            {"Name": name, "Values": values} for name, values in attributes.items()
        ],
        "DataGranule": {"Identifiers": [{"IdentifierType": "CRID", "Identifier": "P05023"}]},
        "PGEVersionClass": {"PGEVersion": "R05.02.3"},
        "RelatedUrls": [
            {
                "Type": "GET DATA",
                "Format": "HDF5",
                "URL": (
                    "https://nisar.asf.earthdatacloud.nasa.gov/NISAR/"
                    "NISAR_L2_GCOV_PROVISIONAL_V1/2026/06/17/" + GRANULE + ".h5"
                ),
            },
            {
                "Subtype": "PRODUCT QUALITY ASSESSMENT",
                "URL": "https://example.invalid/product_QA.pdf",
            },
            {"URL": "https://example.invalid/product_QA_SUMMARY.csv"},
        ],
    }


def _item(*, instrument: str = "L-SAR") -> dict[str, Any]:
    return {
        "meta": {"concept-id": CONCEPT, "provider-id": "ASF"},
        "umm": _umm(instrument=instrument),
    }


def _aoi() -> dict[str, Any]:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [14.9999, -0.0001],
                [15.0004, -0.0001],
                [15.0004, 0.0004],
                [14.9999, 0.0004],
                [14.9999, -0.0001],
            ]
        ],
    }


@pytest.mark.anyio
async def test_cmr_discovery_preserves_actual_l_band_layers_and_release() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.params["short_name"] == "NISAR_L2_GCOV_PROVISIONAL_V1"
        assert request.url.params["bounding_box"] == "15.0,0.0,16.0,1.0"
        return httpx2.Response(200, json={"items": [_item()]})

    provider = NisarCmrProvider(httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))
    response = await provider.search(
        NisarDiscoveryRequest.model_validate(
            {
                "aoi": {
                    "type": "Polygon",
                    "coordinates": [[[15, 0], [16, 0], [16, 1], [15, 1], [15, 0]]],
                },
                "acquisition": {
                    "start": "2026-06-17T00:00:00Z",
                    "end": "2026-06-18T00:00:00Z",
                },
            }
        )
    )
    scene = response.scenes[0]
    assert scene.granule_ur == GRANULE
    assert scene.composite_release_id == "P05023"
    assert scene.product_version == "1.0.11"
    assert scene.pge_version == "R05.02.3"
    assert [(item.frequency, item.polarizations) for item in scene.frequencies] == [
        ("A", ["HH"]),
        ("B", ["HH"]),
    ]
    assert [item.nominal_pixel_spacing_metres for item in scene.frequencies] == [10, 80]
    assert scene.quality.orbit_fidelity == "forecast"
    assert scene.quality.full_frame is False
    assert scene.quality.joint_observation is False
    assert scene.metadata.outcome.state == "unavailable"
    assert scene.metadata.outcome.missing_fields == ["crs"]
    await provider.aclose()


def test_s_band_record_is_not_silently_treated_as_l_band() -> None:
    with pytest.raises(Exception, match="Only NISAR L-band"):
        NisarCmrProvider._scene(_item(instrument="S-SAR"))


class _Provider:
    def __init__(self, resolved: NisarResolvedProduct) -> None:
        self.resolved = resolved

    async def resolve(self, source: Any) -> NisarResolvedProduct:
        assert source == self.resolved.scene.source
        return self.resolved


def _request(scene: Any) -> NisarIngestionRequest:
    return NisarIngestionRequest.model_validate(
        {"scene": scene.source, "aoi": _aoi(), "frequency": "A", "covariance_term": "HHHH"}
    )


@pytest.mark.anyio
async def test_missing_staged_product_reports_exact_authentication_step(tmp_path: Path) -> None:
    scene = NisarCmrProvider._scene(_item())
    resolved = NisarResolvedProduct(
        scene=scene,
        download_url="https://nisar.asf.earthdatacloud.nasa.gov/NISAR/file.h5",
        filename=f"{GRANULE}.h5",
    )
    service = NisarGcovIngestionService(_Provider(resolved), tmp_path)  # type: ignore[arg-type]
    response = await service.ingest(_request(scene))
    assert response.outcome.state == "unavailable"
    assert response.outcome.reason_code == "earthdata_authentication_required"
    assert "earthaccess.login()" in response.outcome.corrective_action

    unavailable_layer = _request(scene).model_copy(update={"covariance_term": "VVVV"})
    layer_response = await service.ingest(unavailable_layer)
    assert layer_response.outcome.state == "unavailable"
    assert layer_response.outcome.reason_code == "requested_layer_unavailable"


@pytest.mark.anyio
async def test_ingestion_keeps_gamma0_and_decodes_gcoven_mask(tmp_path: Path) -> None:
    scene = NisarCmrProvider._scene(_item())
    resolved = NisarResolvedProduct(
        scene=scene,
        download_url="https://nisar.asf.earthdatacloud.nasa.gov/NISAR/file.h5",
        filename=f"{GRANULE}.h5",
    )
    staged = tmp_path / CONCEPT
    staged.mkdir()
    values = np.arange(1, 17, dtype=np.float32).reshape(4, 4) / 10
    values[1, 1] = -9999
    mask = np.ones((4, 4), dtype=np.uint8)
    mask[0, 0] = 0
    mask[0, 1] = 255
    with h5py.File(staged / resolved.filename, "w") as product:
        frequency = product.create_group("/science/LSAR/GCOV/grids/frequencyA")
        data = frequency.create_dataset("HHHH", data=values)
        data.attrs["units"] = "1"
        data.attrs["grid_mapping"] = "projection"
        data.attrs["_FillValue"] = np.float32(-9999)
        product_mask = frequency.create_dataset("mask", data=mask)
        product_mask.attrs["grid_mapping"] = "projection"
        projection = frequency.create_dataset("projection", data=np.uint32(32633))
        projection.attrs["epsg_code"] = 32633
        frequency.create_dataset("xCoordinates", data=[500005, 500015, 500025, 500035])
        frequency.create_dataset("yCoordinates", data=[35, 25, 15, 5])
        frequency.create_dataset("xCoordinateSpacing", data=10)
        frequency.create_dataset("yCoordinateSpacing", data=-10)

    service = NisarGcovIngestionService(_Provider(resolved), tmp_path)  # type: ignore[arg-type]
    response = await service.ingest(_request(scene))
    assert response.outcome.state == "ingested"
    assert response.outcome.units == "gamma0_power"
    assert response.outcome.calibration == "source_calibrated_rtc_gamma0_no_additional_scale"
    assert response.outcome.crs == "EPSG:32633"
    assert response.outcome.pixel_spacing_metres == 10
    assert response.outcome.mask.invalid_ensemble_pixels == 1
    assert response.outcome.mask.outside_acquisition_pixels == 1
    assert response.outcome.mask.nodata_or_nonfinite_backscatter_pixels == 1
    raster = service.analytical_raster(_request(scene))
    assert raster is not None
    assert np.isnan(raster.values[0, 0])
    assert np.isnan(raster.values[0, 1])
    assert np.isnan(raster.values[1, 1])
    assert raster.values[2, 2] == pytest.approx(values[2, 2])
    assert service.analytical_raster(_request(scene).model_copy(update={"frequency": "B"})) is None

    with h5py.File(staged / resolved.filename, "r+") as product:
        product["/science/LSAR/GCOV/grids/frequencyA/HHHH"].attrs["scale_factor"] = 2
    rejected = await service.ingest(_request(scene))
    assert rejected.outcome.state == "unavailable"
    assert rejected.outcome.reason_code == "invalid_product"


def test_nisar_api_uses_stable_scene_and_reports_missing_authenticated_pixels(
    tmp_path: Path,
) -> None:
    provider = NisarCmrProvider(
        httpx2.AsyncClient(
            transport=httpx2.MockTransport(
                lambda _request: httpx2.Response(200, json={"items": [_item()]})
            )
        )
    )
    app = create_app(
        settings=make_settings(),
        database=UnavailableDatabase(),
        nisar_provider=provider,
        nisar_ingestion_service=NisarGcovIngestionService(provider, tmp_path),
    )
    scene = NisarCmrProvider._scene(_item())
    with TestClient(app, raise_server_exceptions=False) as client:
        discovered = client.post(
            "/api/v1/nisar/search",
            json={
                "aoi": _aoi(),
                "acquisition": {
                    "start": "2026-06-17T00:00:00Z",
                    "end": "2026-06-18T00:00:00Z",
                },
                "limit": 1,
            },
        )
        assert discovered.status_code == 200
        assert discovered.json()["scenes"][0]["source"]["item"] == CONCEPT
        body = _request(scene).model_dump(mode="json")
        unavailable = client.post("/api/v1/nisar/ingestions", json=body)
        assert unavailable.status_code == 200
        assert unavailable.json()["outcome"]["reason_code"] == "earthdata_authentication_required"
        assert (
            client.post(
                "/api/v1/nisar/ingestions", json={**body, "asset_url": "https://example.com/a.h5"}
            ).status_code
            == 422
        )
