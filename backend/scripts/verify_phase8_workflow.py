"""Run the real Phase 8 pair through the protected HTTP job/result/tile workflow.

This verification uses the production provider, processing service, routes, and atomic artifact
store. It uses the repository's in-memory test persistence and fixed verification principal only
because PostgreSQL and production identity are not configured locally; the output labels that fact.
"""

from __future__ import annotations

import json
import math
import sys
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "tests"))

from conftest import ReadyDatabase, make_settings  # noqa: E402
from test_processing_jobs import MemoryRepository  # noqa: E402

from satquery.db.processing import ProcessingPrincipal  # noqa: E402
from satquery.main import create_app  # noqa: E402
from satquery.processing.jobs import PreparationJobService  # noqa: E402
from satquery.providers.catalog import EarthSearchCatalogueProvider  # noqa: E402
from satquery.storage import AtomicArtifactStore  # noqa: E402

OWNER = UUID("10000000-0000-4000-8000-000000000088")
AOI = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.585, 12.965],
            [77.605, 12.965],
            [77.605, 12.985],
            [77.585, 12.985],
            [77.585, 12.965],
        ]
    ],
}
SCENES = [
    {
        "provider": "earth-search",
        "collection": "sentinel-2-c1-l2a",
        "item": "S2B_T43PGQ_20251213T052354_L2A",
    },
    {
        "provider": "earth-search",
        "collection": "sentinel-2-c1-l2a",
        "item": "S2B_T43PGQ_20251223T051848_L2A",
    },
]


async def _principal(_request: Request) -> ProcessingPrincipal:
    return ProcessingPrincipal(OWNER, "verification:phase-8f-real-pair")


def _request_body() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "scenes": SCENES,
        "aoi": AOI,
        "required_bands": [
            {"role": role, "common_name": role} for role in ("red", "green", "blue")
        ],
        "intended_task": "optical_pair",
        "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
        "options": {
            "grid_policy": "common_utm",
            "target_resolution_metres": 10.0,
            "continuous_resampling": "bilinear",
            "mask_resampling": "nearest",
            "calibration": "source_metadata",
            "clip_to_aoi": True,
            "preserve_originals": True,
            "max_output_pixels": 60_000,
        },
    }


def _tile(aoi: dict[str, Any], zoom: int = 14) -> tuple[int, int, int]:
    ring = aoi["coordinates"][0]
    longitude = sum(point[0] for point in ring[:-1]) / (len(ring) - 1)
    latitude = sum(point[1] for point in ring[:-1]) / (len(ring) - 1)
    scale = 2**zoom
    x = int((longitude + 180.0) / 360.0 * scale)
    latitude_radians = math.radians(latitude)
    y = int((1.0 - math.asinh(math.tan(latitude_radians)) / math.pi) / 2.0 * scale)
    return zoom, x, y


def verify() -> None:
    provider = EarthSearchCatalogueProvider.from_settings(make_settings())
    repository = MemoryRepository()
    scratch_root = BACKEND_ROOT.parent / ".tmp"
    scratch_root.mkdir(exist_ok=True)
    verification_directory = scratch_root / f"satquery-phase8f-{uuid4().hex}"
    verification_directory.mkdir()
    # Deliberately retain this bounded verification output: GDAL can keep remote dataset handles
    # alive briefly on Windows, which makes eager temporary-directory cleanup mask the real result.
    with nullcontext(verification_directory) as directory:
        service = PreparationJobService(
            repository,
            provider,
            AtomicArtifactStore(Path(directory), max_job_bytes=64 * 1024 * 1024),
            max_pixels=60_000,
            timeout_seconds=300.0,
        )
        app = create_app(
            settings=make_settings(),
            database=ReadyDatabase(),
            catalogue_provider=provider,
            processing_job_service=service,
            processing_principal_resolver=_principal,
        )
        body = _request_body()
        with TestClient(app, raise_server_exceptions=False) as client:
            started = client.post(
                "/api/v1/processing/changes",
                headers={"Idempotency-Key": "phase8f-real-pair-1"},
                json=body,
            )
            started.raise_for_status()
            status = started.json()
            stages: list[str] = []
            deadline = time.monotonic() + 300
            while status["state"] not in {"succeeded", "failed", "cancelled"}:
                if status["current_stage"] and status["current_stage"] not in stages:
                    stages.append(status["current_stage"])
                if time.monotonic() >= deadline:
                    raise TimeoutError("Real Phase 8 HTTP job did not finish within 300 seconds.")
                time.sleep(0.25)
                response = client.get(f"/api/v1/processing/change-jobs/{status['job_id']}")
                response.raise_for_status()
                status = response.json()
            if status["current_stage"] and status["current_stage"] not in stages:
                stages.append(status["current_stage"])
            if status["state"] != "succeeded":
                print(
                    json.dumps(
                        {
                            "persistence": "verification_in_memory_not_production_postgresql",
                            "job_id": status["job_id"],
                            "state": status["state"],
                            "stages_observed": stages,
                            "safe_error_code": status.get("error_code"),
                            "safe_error_message": status.get("safe_error_message"),
                        },
                        indent=2,
                    )
                )
                raise RuntimeError("Real Phase 8 HTTP job did not succeed.")
            result_response = client.get(
                f"/api/v1/processing/change-jobs/{status['job_id']}/result"
            )
            result_response.raise_for_status()
            result = result_response.json()
            zoom, x, y = _tile(AOI)
            tile_response = client.get(
                "/api/v1/processing/artifacts/"
                f"{result['classification_artifact_id']}/tiles/change/{zoom}/{x}/{y}.png"
            )
            tile_response.raise_for_status()
            repeated = client.post(
                "/api/v1/processing/changes",
                headers={"Idempotency-Key": "phase8f-real-pair-2"},
                json=body,
            )
            repeated.raise_for_status()
            area = result["area"]
            expected_percentage = (
                100.0
                * area["changed_area_square_metres"]
                / area["joint_valid_observed_area_square_metres"]
            )
            print(
                json.dumps(
                    {
                        "persistence": "verification_in_memory_not_production_postgresql",
                        "job_id": status["job_id"],
                        "state": status["state"],
                        "stages_observed": stages,
                        "source_match": [item["scene"] for item in result["sources"]] == SCENES,
                        "aoi_match": result["aoi"] == AOI,
                        "processing_version": result["processing_version"],
                        "method_version": result["method_version"],
                        "changed_area_square_metres": area["changed_area_square_metres"],
                        "joint_valid_observed_area_square_metres": (
                            area["joint_valid_observed_area_square_metres"]
                        ),
                        "displayed_changed_percent": (
                            area["changed_percent_of_joint_valid_observed_area"]
                        ),
                        "independently_recomputed_percent": expected_percentage,
                        "unknown_area_square_metres": area["unknown_area_square_metres"],
                        "cause_or_land_cover_category": (result["cause_or_land_cover_category"]),
                        "classification_artifact_id": result["classification_artifact_id"],
                        "tile": {
                            "z": zoom,
                            "x": x,
                            "y": y,
                            "media_type": tile_response.headers["content-type"],
                            "byte_size": len(tile_response.content),
                            "png_signature": tile_response.content[:8].hex(),
                        },
                        "cache_reused_same_job": repeated.json()["job_id"] == status["job_id"],
                    },
                    indent=2,
                )
            )


if __name__ == "__main__":
    verify()
