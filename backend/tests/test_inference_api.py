from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from test_processing_jobs import MemoryRepository
from test_vqa_inference import SCENE, FakeTransport, _aoi, _catalogue_scene, _quality, _raster

from satquery.api.schemas.vqa import InferenceSubmissionRequest
from satquery.db.processing import ProcessingPrincipal
from satquery.inference import SingleImageInferenceService
from satquery.inference.grounding import GroundingError
from satquery.inference.jobs import InferenceJobError, InferenceJobService
from satquery.main import create_app
from satquery.providers.catalog import CatalogueProvider, CatalogueProviderError
from satquery.storage import AtomicArtifactStore


class TrustedProvider:
    async def item(self, collection_id: str, item_id: str) -> Any:
        assert collection_id == SCENE.collection
        assert item_id == SCENE.item
        return _catalogue_scene()


class StaleProvider(TrustedProvider):
    async def item(self, collection_id: str, item_id: str) -> Any:
        raise CatalogueProviderError(
            "ITEM_NOT_FOUND", "Provider item is unavailable.", retryable=False
        )


class InvalidGroundingService:
    async def locate(self, request: Any, chip: Any) -> Any:
        raise GroundingError(
            "GROUNDING_OUTPUT_INVALID", "The model returned invalid grounding geometry."
        )


def _provider(value: TrustedProvider) -> CatalogueProvider:
    """Narrow a deliberately minimal test double at the service boundary."""

    return cast(CatalogueProvider, value)


def _request(operation: str = "visual_question_answering") -> InferenceSubmissionRequest:
    return InferenceSubmissionRequest.model_validate(
        {
            "request_id": str(uuid4()),
            "operation": operation,
            "scene": SCENE.model_dump(mode="json"),
            "aoi": _aoi(),
            "text": "What surface types are visible?"
            if operation == "visual_question_answering"
            else ("the vegetation" if operation == "referring_grounding" else None),
        }
    )


def _root() -> Path:
    return Path(".test-inference-artifacts") / str(uuid4())


async def _wait(service: InferenceJobService, principal: ProcessingPrincipal, job_id: UUID) -> Any:
    for _ in range(100):
        status = await service.status(principal, job_id)
        if status.state in {"succeeded", "failed", "cancelled"}:
            return status
        await asyncio.sleep(0.01)
    raise AssertionError("inference job did not finish")


async def _install_scientific_fakes(monkeypatch: pytest.MonkeyPatch, *, qa: Any) -> None:
    async def extract(self: Any, request: Any) -> Any:
        return _raster()

    async def decode(self: Any, raster: Any) -> Any:
        return qa

    monkeypatch.setattr("satquery.inference.jobs.RasterInputService.extract", extract)
    monkeypatch.setattr("satquery.inference.jobs.QualityMaskService.decode", decode)


def test_valid_api_inference_records_exact_chip_evidence_and_reuses_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from conftest import ReadyDatabase
    from conftest import make_settings as settings_factory

    root = _root()
    try:
        asyncio.run(_install_scientific_fakes(monkeypatch, qa=_quality()))
        repository = MemoryRepository()
        principal = ProcessingPrincipal(uuid4(), "owner:api-inference")
        service = InferenceJobService(
            repository,
            _provider(TrustedProvider()),
            AtomicArtifactStore(root, max_job_bytes=2_000_000),
            answer_service=SingleImageInferenceService(FakeTransport()),
            grounding_service=None,
        )

        async def resolve_principal(request: Request) -> ProcessingPrincipal:
            return principal

        app = create_app(
            settings=settings_factory(),
            database=ReadyDatabase(),
            catalogue_provider=_provider(TrustedProvider()),
            inference_job_service=service,
            processing_principal_resolver=resolve_principal,
        )
        payload = _request().model_dump(mode="json")
        with TestClient(app) as client:
            started = client.post(
                "/api/v1/inference/jobs",
                json=payload,
                headers={"Idempotency-Key": "inference-api-1"},
            )
            assert started.status_code == 202
            job_id = started.json()["job_id"]
            for _ in range(100):
                status = client.get(f"/api/v1/inference/jobs/{job_id}")
                if status.json()["state"] == "succeeded":
                    break
            body = status.json()
            assert body["state"] == "succeeded"
            assert body["result"]["answer"]["availability"] == "available"
            assert body["result"]["source_chip"]["scene"] == payload["scene"]
            assert body["result"]["interpretation_disclaimer"] == "evidence_not_validation"
            repeated = client.post(
                "/api/v1/inference/jobs",
                json=payload,
                headers={"Idempotency-Key": "different-key-same-request"},
            )
            assert repeated.json()["job_id"] == job_id
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.mark.parametrize(
    ("qa", "answer_available", "expected_state"),
    [
        (_quality(), False, "unavailable"),
        (_quality(usable=False), True, "blocked"),
        (_quality(available=False), True, "unknown"),
    ],
)
def test_unavailable_model_and_blocked_or_unknown_quality_are_explicit(
    monkeypatch: pytest.MonkeyPatch, qa: Any, answer_available: bool, expected_state: str
) -> None:
    root = _root()
    try:
        asyncio.run(_install_scientific_fakes(monkeypatch, qa=qa))
        service = InferenceJobService(
            MemoryRepository(),
            _provider(TrustedProvider()),
            AtomicArtifactStore(root, max_job_bytes=2_000_000),
            answer_service=SingleImageInferenceService(FakeTransport())
            if answer_available
            else None,
            grounding_service=None,
        )
        principal = ProcessingPrincipal(uuid4(), "owner:quality-state")

        async def run() -> Any:
            record = await service.submit(principal, _request(), idempotency_key=str(uuid4()))
            return await _wait(service, principal, record.job_id)

        status = asyncio.run(run())
        assert status.state == "succeeded"
        assert status.result.execution_state == expected_state
        assert status.result.answer is None
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_stale_scene_invalid_grounding_and_cross_owner_artifact_access_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _root()
    try:
        asyncio.run(_install_scientific_fakes(monkeypatch, qa=_quality()))
        principal = ProcessingPrincipal(uuid4(), "owner:one")
        stale = InferenceJobService(
            MemoryRepository(),
            _provider(StaleProvider()),
            AtomicArtifactStore(root, max_job_bytes=2_000_000),
            answer_service=None,
            grounding_service=None,
        )
        with pytest.raises(InferenceJobError, match="no longer available"):
            asyncio.run(stale.submit(principal, _request(), idempotency_key="stale"))

        repository = MemoryRepository()
        invalid = InferenceJobService(
            repository,
            _provider(TrustedProvider()),
            AtomicArtifactStore(root, max_job_bytes=2_000_000),
            answer_service=None,
            grounding_service=InvalidGroundingService(),  # type: ignore[arg-type]
        )

        async def run_invalid() -> Any:
            record = await invalid.submit(
                principal, _request("referring_grounding"), idempotency_key="invalid-grounding"
            )
            return await _wait(invalid, principal, record.job_id)

        status = asyncio.run(run_invalid())
        assert status.state == "failed"
        assert status.error_code == "grounding_output_invalid"
        assert status.artifacts == []

        valid = InferenceJobService(
            repository,
            _provider(TrustedProvider()),
            AtomicArtifactStore(root, max_job_bytes=2_000_000),
            answer_service=SingleImageInferenceService(FakeTransport()),
            grounding_service=None,
        )

        async def run_access() -> None:
            record = await valid.submit(principal, _request(), idempotency_key="owner-artifact")
            completed = await _wait(valid, principal, record.job_id)
            artifact_id = completed.artifacts[0].artifact_id
            other = ProcessingPrincipal(uuid4(), "owner:other")
            assert await repository.get_artifact(other, artifact_id) is None

        asyncio.run(run_access())
    finally:
        shutil.rmtree(root, ignore_errors=True)
