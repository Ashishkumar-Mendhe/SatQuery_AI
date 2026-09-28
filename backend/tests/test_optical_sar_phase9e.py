"""Known synthetic 9E measurements; not a live cross-sensor verification."""

from __future__ import annotations

import time
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from test_optical_sar_pair_phase9d import AOI, OPTICAL, SAR, T0, _fixture
from test_processing_jobs import MemoryRepository

from satquery.api.schemas.optical_sar import OpticalSarAnalysisRequest
from satquery.db.processing import ProcessingPrincipal
from satquery.main import create_app
from satquery.processing.optical_sar_jobs import SUPPORTED_QUESTION, _result
from satquery.processing.optical_sar_pair import OpticalSarPairService
from satquery.processing.raster import RasterInputError
from satquery.processing.sar import SarRasterService
from satquery.providers.catalog.base import CatalogueProvider
from satquery.providers.catalog.inpe_sar import InpeSarProvider
from satquery.storage import AtomicArtifactStore


def _request(question: str = SUPPORTED_QUESTION) -> OpticalSarAnalysisRequest:
    return OpticalSarAnalysisRequest.model_validate(
        {
            "request_id": str(uuid4()),
            "optical_scene": OPTICAL.model_dump(mode="json"),
            "sar_scene": SAR.model_dump(mode="json"),
            "aoi": AOI,
            "polarization": "VV",
            "question": question,
        }
    )


def test_separate_measurements_use_source_pixels_and_joint_denominator() -> None:
    optical_request, sar_request, grid, response, raster = _fixture()
    pair = OpticalSarPairService().prepare(optical_request, sar_request, grid, T0, response, raster)
    result = _result(pair, _request(), uuid4(), uuid4())
    assert result.state == "limited"
    assert result.optical.measured_value == pytest.approx(0.2)
    assert result.sar.measured_value == pytest.approx(0.15)
    assert result.optical.valid_pixels == 33
    assert result.optical.denominator_pixels == 36
    assert result.joint_usable_pixels == int(np.count_nonzero(pair.joint_usable))
    assert result.joint_usable_percent_of_aoi == pytest.approx(
        100 * result.joint_usable_pixels / 36
    )
    assert result.optical.evidence_crs == "EPSG:32631"
    assert result.sar.evidence_crs == "EPSG:32631"
    assert result.alignment_state == "unavailable"
    assert result.agreement_state == "not_assessed"
    assert result.source_evidence[0].source == OPTICAL
    assert result.source_evidence[1].source == SAR
    assert result.source_evidence[1].preparation_version == response.processing_version
    assert "building change are not determined" in result.answer


def test_unsupported_question_and_no_joint_coverage_are_insufficient() -> None:
    optical_request, sar_request, grid, response, raster = _fixture()
    pair = OpticalSarPairService().prepare(optical_request, sar_request, grid, T0, response, raster)
    unsupported = _result(pair, _request("How many new buildings?"), uuid4(), uuid4())
    assert unsupported.state == "insufficient_evidence"
    assert "unsupported" in unsupported.answer
    assert not any("new buildings" in limitation for limitation in unsupported.limitations)
    empty = replace(
        pair,
        coverage=replace(
            pair.coverage,
            joint_usable_pixels=0,
            joint_usable_percent=0.0,
            joint_usable_area_square_metres=0.0,
        ),
    )
    result = _result(empty, _request(), uuid4(), uuid4())
    assert result.state == "insufficient_evidence"


def test_request_rejects_untrusted_sources_and_excess_grid() -> None:
    payload = _request().model_dump(mode="json")
    payload["sar_scene"]["provider"] = "client-url"
    with pytest.raises(ValueError):
        OpticalSarAnalysisRequest.model_validate(payload)
    payload = _request().model_dump(mode="json")
    payload["target_resolution_metres"] = 1.0
    with pytest.raises(ValueError):
        OpticalSarAnalysisRequest.model_validate(payload)


def test_api_fails_closed_without_verified_identity(ready_client: TestClient) -> None:
    response = ready_client.post(
        "/api/v1/optical-sar/jobs",
        json=_request().model_dump(mode="json"),
        headers={"Idempotency-Key": "synthetic-phase9e"},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "CAPABILITY_UNAVAILABLE"


def test_synthetic_api_job_result_cache_and_owner_scoped_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from conftest import ReadyDatabase, make_settings

    from satquery.processing.optical_sar_jobs import OpticalSarJobService

    optical_request, sar_request, grid, response, raster = _fixture()
    pair = OpticalSarPairService().prepare(optical_request, sar_request, grid, T0, response, raster)

    class OpticalProvider:
        async def item(self, collection: str, item: str) -> Any:
            assert collection == OPTICAL.collection and item == OPTICAL.item
            return SimpleNamespace(
                provider=SimpleNamespace(id=OPTICAL.provider),
                provider_asset_id=OPTICAL.item,
                provider_asset_version="fixture-v1",
                acquisition=SimpleNamespace(start=T0),
            )

    class SarProvider:
        async def resolve(self, source: Any, polarization: str) -> Any:
            assert source == SAR and polarization == "VV"
            return SimpleNamespace(
                scene=SimpleNamespace(source=SAR, acquisition=SimpleNamespace(start=T0)),
                backscatter=SimpleNamespace(checksum="fixture-checksum"),
            )

    class MemoryArtifactStore:
        def __init__(self) -> None:
            self.items: dict[str, bytes] = {}

        def write_bytes(
            self,
            job_id: Any,
            artifact_id: Any,
            suffix: str,
            payload: bytes,
            *,
            bytes_already_written: int,
        ) -> Any:
            key = f"{job_id}/{artifact_id}{suffix}"
            self.items[key] = payload
            return SimpleNamespace(
                storage_key=key, checksum_sha256=sha256(payload).hexdigest(), byte_size=len(payload)
            )

        def exists(self, key: str) -> bool:
            return key in self.items

        def open(self, key: str) -> BytesIO:
            return BytesIO(self.items[key])

    async def prepared(self: Any, *args: Any) -> Any:
        return pair

    monkeypatch.setattr(OpticalSarPairService, "prepare_real", prepared)
    repository = MemoryRepository()
    owner = ProcessingPrincipal(uuid4(), "owner:phase9e")
    other = ProcessingPrincipal(uuid4(), "owner:other")
    optical_provider = OpticalProvider()
    sar_provider = SarProvider()
    optical_adapter = cast(CatalogueProvider, optical_provider)
    sar_adapter = cast(InpeSarProvider, sar_provider)
    sar_raster_service = cast(SarRasterService, object())
    service = OpticalSarJobService(
        repository,
        optical_adapter,
        sar_adapter,
        sar_raster_service,
        cast(AtomicArtifactStore, MemoryArtifactStore()),
    )

    async def principal(request: Request) -> ProcessingPrincipal:
        return other if request.headers.get("x-test-owner") == "other" else owner

    app = create_app(
        settings=make_settings(),
        database=ReadyDatabase(),
        catalogue_provider=optical_adapter,
        sar_provider=sar_adapter,
        sar_raster_service=sar_raster_service,
        optical_sar_job_service=service,
        processing_principal_resolver=principal,
    )
    payload = _request().model_dump(mode="json")
    with TestClient(app) as client:
        started = client.post(
            "/api/v1/optical-sar/jobs",
            json=payload,
            headers={"Idempotency-Key": "phase9e-api-1"},
        )
        assert started.status_code == 202, started.text
        job_id = started.json()["job_id"]
        for _ in range(100):
            status = client.get(f"/api/v1/optical-sar/jobs/{job_id}")
            if status.json()["state"] in {"succeeded", "failed"}:
                break
            time.sleep(0.01)
        assert status.json()["state"] == "succeeded", status.text
        result = client.get(f"/api/v1/optical-sar/jobs/{job_id}/result")
        assert result.status_code == 200
        assert result.json()["optical"]["source"]["item"] == OPTICAL.item
        assert result.json()["source_evidence"][0]["source_version"] == "fixture-v1"
        assert result.json()["source_evidence"][1]["checksum"] == "fixture-checksum"
        artifact_id = result.json()["evidence_artifact_id"]
        assert client.get(f"/api/v1/optical-sar/artifacts/{artifact_id}").status_code == 200
        denied = client.get(
            f"/api/v1/optical-sar/artifacts/{artifact_id}", headers={"x-test-owner": "other"}
        )
        assert denied.status_code == 404
        repeated = client.post(
            "/api/v1/optical-sar/jobs",
            json=payload,
            headers={"Idempotency-Key": "phase9e-api-2"},
        )
        assert repeated.json()["job_id"] == job_id

        async def unavailable_raster(self: Any, *args: Any) -> Any:
            raise RasterInputError(
                "RASTER_READ_FAILED", "A selected scientific raster band could not be read."
            )

        monkeypatch.setattr(OpticalSarPairService, "prepare_real", unavailable_raster)
        failed_payload = _request().model_dump(mode="json")
        failed = client.post(
            "/api/v1/optical-sar/jobs",
            json=failed_payload,
            headers={"Idempotency-Key": "phase9f-raster-failure"},
        )
        assert failed.status_code == 202
        failed_job_id = failed.json()["job_id"]
        for _ in range(100):
            failed_status = client.get(f"/api/v1/optical-sar/jobs/{failed_job_id}")
            if failed_status.json()["state"] == "failed":
                break
            time.sleep(0.01)
        assert failed_status.json()["state"] == "failed"
        assert failed_status.json()["error_code"] == "raster_read_failed"
        assert "scientific raster band" in failed_status.json()["safe_error_message"]
        assert failed_status.json()["artifacts"] == []
