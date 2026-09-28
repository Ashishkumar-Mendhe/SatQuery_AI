"""Synthetic service doubles verify actual bounded method dispatch, not scientific outputs."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from satquery.agent.execution import TOOL_REGISTRY, GeoAgentServices, ToolSpec, execute_message
from satquery.api.schemas.geoagent import GeoAgentMessageRequest
from satquery.api.schemas.optical_sar import OpticalSarAnalysisRequest, OpticalSarJobStatus
from satquery.api.schemas.processing import PreparationRequest, ProcessingJobStatus
from satquery.api.schemas.viewer import TileMetadata, TileMetadataRequest
from satquery.api.schemas.vqa import InferenceJobStatus, InferenceSubmissionRequest
from satquery.db.processing import ProcessingPersistenceError, ProcessingPrincipal
from satquery.inference.jobs import InferenceJobService
from satquery.processing.jobs import PreparationJobService
from satquery.processing.optical_sar_jobs import OpticalSarJobService
from satquery.providers.catalog import CatalogueProvider
from satquery.tiles import ImageryTileService

AOI = {
    "type": "Polygon",
    "coordinates": [[[77.5, 12.9], [77.51, 12.9], [77.51, 12.91], [77.5, 12.91], [77.5, 12.9]]],
}
PRINCIPAL = ProcessingPrincipal(uuid4(), "owner:geoagent-fixture")


def _scene(item: str, day: int) -> dict[str, Any]:
    return {
        "source": {"provider": "earth-search", "collection": "sentinel-2-c1-l2a", "item": item},
        "modality": "optical",
        "acquired_at": f"2025-01-{day:02d}T10:00:00Z",
    }


def _sar() -> dict[str, Any]:
    return {
        "source": {"provider": "inpe-bdc", "collection": "sentinel-1-rtc-1", "item": "S1_A"},
        "modality": "sar",
        "acquired_at": "2025-01-03T08:00:00Z",
        "polarization": "VV",
    }


def _request(
    message: str, scenes: list[dict[str, Any]], *, aoi: bool = True, request_id: UUID | None = None
) -> GeoAgentMessageRequest:
    return GeoAgentMessageRequest.model_validate(
        {
            "request_id": str(request_id or uuid4()),
            "message": message,
            "selected_aoi": AOI if aoi else None,
            "selected_scenes": scenes,
        }
    )


class InferenceDouble:
    def __init__(self) -> None:
        self.job_id = uuid4()
        self.calls: list[tuple[InferenceSubmissionRequest, str]] = []

    async def submit(
        self,
        principal: ProcessingPrincipal,
        request: InferenceSubmissionRequest,
        *,
        idempotency_key: str,
    ) -> Any:
        assert principal == PRINCIPAL
        self.calls.append((request, idempotency_key))
        return SimpleNamespace(job_id=self.job_id)

    async def status(self, principal: ProcessingPrincipal, job_id: UUID) -> InferenceJobStatus:
        assert principal == PRINCIPAL and job_id == self.job_id
        return InferenceJobStatus.model_validate(
            {
                "job_id": str(job_id),
                "request_id": str(self.calls[-1][0].request_id),
                "operation": self.calls[-1][0].operation,
                "state": "queued",
                "submitted_at": datetime.now(UTC).isoformat(),
                "attempt": 0,
            }
        )


class ChangeDouble:
    def __init__(self) -> None:
        self.job_id = uuid4()
        self.calls: list[tuple[PreparationRequest, str]] = []

    async def submit_change(
        self, principal: ProcessingPrincipal, request: PreparationRequest, *, idempotency_key: str
    ) -> Any:
        assert principal == PRINCIPAL
        self.calls.append((request, idempotency_key))
        return SimpleNamespace(job_id=self.job_id)

    async def change_status(
        self, principal: ProcessingPrincipal, job_id: UUID
    ) -> ProcessingJobStatus:
        assert principal == PRINCIPAL and job_id == self.job_id
        return ProcessingJobStatus.model_validate(
            {
                "job_id": str(job_id),
                "state": "queued",
                "submitted_at": datetime.now(UTC).isoformat(),
                "attempt": 0,
            }
        )


class OpticalSarDouble:
    def __init__(self) -> None:
        self.job_id = uuid4()
        self.calls: list[tuple[OpticalSarAnalysisRequest, str]] = []

    async def submit(
        self,
        principal: ProcessingPrincipal,
        request: OpticalSarAnalysisRequest,
        *,
        idempotency_key: str,
    ) -> Any:
        assert principal == PRINCIPAL
        self.calls.append((request, idempotency_key))
        return SimpleNamespace(job_id=self.job_id)

    async def status(self, principal: ProcessingPrincipal, job_id: UUID) -> OpticalSarJobStatus:
        assert principal == PRINCIPAL and job_id == self.job_id
        return OpticalSarJobStatus.model_validate(
            {
                "job_id": str(job_id),
                "request_id": str(self.calls[-1][0].request_id),
                "state": "queued",
                "submitted_at": datetime.now(UTC).isoformat(),
                "attempt": 0,
            }
        )


class CatalogueDouble:
    def __init__(self, reverse: bool = False) -> None:
        self.reverse = reverse
        self.calls: list[str] = []

    async def item(self, collection: str, item: str) -> Any:
        assert collection == "sentinel-2-c1-l2a"
        self.calls.append(item)
        day = 10 if item == "AFTER" else 1
        if self.reverse:
            day = 1 if item == "AFTER" else 10
        return SimpleNamespace(
            provider=SimpleNamespace(id="earth-search"),
            provider_asset_id=item,
            acquisition=SimpleNamespace(start=datetime(2025, 1, day, tzinfo=UTC)),
        )


class ImageryDouble:
    def __init__(self) -> None:
        self.calls: list[tuple[TileMetadataRequest, str]] = []
        self.tile_set_id = uuid4()

    async def metadata(self, request: TileMetadataRequest, *, access_scope: str) -> TileMetadata:
        self.calls.append((request, access_scope))
        return TileMetadata.model_validate(
            {
                "tile_set_id": str(self.tile_set_id),
                "asset": {"scene": request.scene.model_dump(mode="json"), "asset": "visual-rgb"},
                "render_preset": "natural-color",
                "bounds": [77.5, 12.9, 77.51, 12.91],
                "min_zoom": 0,
                "max_zoom": 16,
                "tile_size": 256,
                "media_type": "image/png",
                "url_template": f"/api/v1/imagery/tiles/{self.tile_set_id}/{{z}}/{{x}}/{{y}}.png",
                "expires_at": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
                "attributions": ["Synthetic fixture"],
                "access": {"state": "available"},
            }
        )


@pytest.mark.parametrize(
    ("message", "operation"),
    [
        ("What is visible in this image?", "visual_question_answering"),
        ("Caption this image", "image_captioning"),
        ("Where is the water?", "referring_grounding"),
    ],
)
def test_inference_operations_call_existing_job_service(message: str, operation: str) -> None:
    service = InferenceDouble()
    request = _request(message, [_scene("A", 1)])
    result = asyncio.run(
        execute_message(
            request, PRINCIPAL, GeoAgentServices(inference=cast(InferenceJobService, service))
        )
    )
    assert result.status == "submitted"
    assert result.job_id == service.job_id and result.result_id is None
    assert result.cancel_path == f"/api/v1/inference/jobs/{service.job_id}/cancel"
    assert result.summary.aoi_sha256 is not None and len(result.summary.aoi_sha256) == 64
    assert service.calls[0][0].operation == operation
    assert service.calls[0][0].scene.item == "A"
    assert str(request.request_id) in service.calls[0][1]


def test_optical_change_calls_existing_job_after_trusted_date_check() -> None:
    service, catalogue = ChangeDouble(), CatalogueDouble()
    request = _request("What changed here?", [_scene("AFTER", 10), _scene("BEFORE", 1)])
    result = asyncio.run(
        execute_message(
            request,
            PRINCIPAL,
            GeoAgentServices(
                processing=cast(PreparationJobService, service),
                catalogue=cast(CatalogueProvider, catalogue),
            ),
        )
    )
    assert result.status == "submitted"
    assert catalogue.calls == ["BEFORE", "AFTER"]
    assert [scene.item for scene in service.calls[0][0].scenes] == ["BEFORE", "AFTER"]
    assert service.calls[0][0].required_bands[0].common_name == "red"
    assert result.cancel_path == f"/api/v1/processing/change-jobs/{service.job_id}/cancel"


def test_changed_client_dates_cannot_submit_bad_real_order() -> None:
    service = ChangeDouble()
    result = asyncio.run(
        execute_message(
            _request("What changed here?", [_scene("AFTER", 10), _scene("BEFORE", 1)]),
            PRINCIPAL,
            GeoAgentServices(
                processing=cast(PreparationJobService, service),
                catalogue=cast(CatalogueProvider, CatalogueDouble(reverse=True)),
            ),
        )
    )
    assert result.status == "unsupported" and result.error_code == "DATE_ORDER_UNVERIFIED"
    assert service.calls == []


def test_optical_sar_uses_only_supported_summary_and_selected_polarization() -> None:
    service = OpticalSarDouble()
    result = asyncio.run(
        execute_message(
            _request("Summarize optical and SAR observations", [_scene("A", 1), _sar()]),
            PRINCIPAL,
            GeoAgentServices(optical_sar=cast(OpticalSarJobService, service)),
        )
    )
    assert result.status == "submitted"
    assert service.calls[0][0].polarization == "VV"
    assert service.calls[0][0].question == "Summarize the separate optical and SAR observations."
    assert result.cancel_path == f"/api/v1/optical-sar/jobs/{service.job_id}/cancel"


def test_imagery_calls_real_tile_metadata_service_without_scientific_claim() -> None:
    service = ImageryDouble()
    result = asyncio.run(
        execute_message(
            _request("Show this image", [_scene("A", 1)], aoi=False),
            PRINCIPAL,
            GeoAgentServices(imagery=cast(ImageryTileService, service)),
        )
    )
    assert result.status == "completed" and result.result_id == service.tile_set_id
    assert result.output is not None and result.output["tile_set_id"] == str(service.tile_set_id)
    assert service.calls[0][1] == "public:earth-search"
    assert "not analytical input" in result.message


def test_unavailable_map_tool_and_missing_job_services_do_not_fabricate_ids() -> None:
    map_result = asyncio.run(
        execute_message(_request("Zoom to this AOI", []), PRINCIPAL, GeoAgentServices())
    )
    assert map_result.status == "unavailable" and map_result.job_id is None
    inference_result = asyncio.run(
        execute_message(
            _request("What is visible?", [_scene("A", 1)]), PRINCIPAL, GeoAgentServices()
        )
    )
    assert inference_result.status == "unavailable" and inference_result.output is None


def test_duplicate_request_reuses_same_idempotency_key_and_job() -> None:
    service = InferenceDouble()
    request = _request("What is visible?", [_scene("A", 1)])
    services = GeoAgentServices(inference=cast(InferenceJobService, service))
    first = asyncio.run(execute_message(request, PRINCIPAL, services))
    second = asyncio.run(execute_message(request, PRINCIPAL, services))
    assert first.job_id == second.job_id == service.job_id
    assert service.calls[0][1] == service.calls[1][1]


def test_dependency_failure_is_safe_and_has_no_result() -> None:
    class FailingInference(InferenceDouble):
        async def submit(
            self,
            principal: ProcessingPrincipal,
            request: InferenceSubmissionRequest,
            *,
            idempotency_key: str,
        ) -> Any:
            raise ProcessingPersistenceError("database secret connection failed")

    result = asyncio.run(
        execute_message(
            _request("What is visible?", [_scene("A", 1)]),
            PRINCIPAL,
            GeoAgentServices(inference=cast(InferenceJobService, FailingInference())),
        )
    )
    assert result.status == "unavailable" and result.result_id is None
    assert "secret" not in result.message


def test_failed_existing_job_returns_its_safe_failure_not_an_answer() -> None:
    class FailedInference(InferenceDouble):
        async def status(self, principal: ProcessingPrincipal, job_id: UUID) -> InferenceJobStatus:
            now = datetime.now(UTC)
            return InferenceJobStatus.model_validate(
                {
                    "job_id": str(job_id),
                    "request_id": str(self.calls[-1][0].request_id),
                    "operation": self.calls[-1][0].operation,
                    "state": "failed",
                    "submitted_at": (now - timedelta(seconds=2)).isoformat(),
                    "started_at": (now - timedelta(seconds=1)).isoformat(),
                    "finished_at": now.isoformat(),
                    "attempt": 1,
                    "error_code": "model_unavailable",
                    "safe_error_message": "The configured answer model is unavailable.",
                }
            )

    service = FailedInference()
    result = asyncio.run(
        execute_message(
            _request("What is visible?", [_scene("A", 1)]),
            PRINCIPAL,
            GeoAgentServices(inference=cast(InferenceJobService, service)),
        )
    )
    assert result.status == "failed" and result.job_id == service.job_id
    assert result.result_id is None
    assert result.error_code == "MODEL_UNAVAILABLE"
    assert result.message == "The configured answer model is unavailable."


def test_timeout_reports_unknown_submission_and_requires_same_id_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SlowInference(InferenceDouble):
        async def submit(
            self,
            principal: ProcessingPrincipal,
            request: InferenceSubmissionRequest,
            *,
            idempotency_key: str,
        ) -> Any:
            await asyncio.sleep(0.02)
            return await super().submit(principal, request, idempotency_key=idempotency_key)

    monkeypatch.setitem(
        TOOL_REGISTRY,
        "inference_vqa",
        ToolSpec("inference_vqa", InferenceSubmissionRequest, 1, True, 0.001, True),
    )
    result = asyncio.run(
        execute_message(
            _request("What is visible?", [_scene("A", 1)]),
            PRINCIPAL,
            GeoAgentServices(inference=cast(InferenceJobService, SlowInference())),
        )
    )
    assert result.status == "submission_unknown"
    assert result.retry_same_request_id is True
    assert result.job_id is None and result.result_id is None


def test_geoagent_route_is_protected_without_configured_identity(ready_client: TestClient) -> None:
    response = ready_client.post(
        "/api/v1/geoagent/execute",
        json=_request("Show this image", [_scene("A", 1)]).model_dump(mode="json"),
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "CAPABILITY_UNAVAILABLE"


def test_geoagent_api_uses_actual_registered_imagery_service(ready_client: TestClient) -> None:
    service = ImageryDouble()

    async def principal(_: Any) -> ProcessingPrincipal:
        return PRINCIPAL

    app = cast(FastAPI, ready_client.app)
    app.state.processing_principal_resolver = principal
    app.state.imagery_tile_service = cast(ImageryTileService, service)
    response = ready_client.post(
        "/api/v1/geoagent/execute",
        json=_request("Show this image", [_scene("A", 1)], aoi=False).model_dump(mode="json"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"
    assert response.json()["result_id"] == str(service.tile_set_id)
    assert service.calls[0][0].scene.item == "A"


def test_registry_is_closed_and_bounded() -> None:
    assert len(TOOL_REGISTRY) == 7
    assert all(spec.submit_timeout_seconds <= 20 for spec in TOOL_REGISTRY.values())
    assert TOOL_REGISTRY["map_aoi_control"].cancellable is False
