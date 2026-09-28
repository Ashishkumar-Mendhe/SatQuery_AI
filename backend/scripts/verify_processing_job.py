"""Run one real Task 6G preparation through durable production boundaries."""

from __future__ import annotations

import asyncio
import json
from uuid import UUID

from satquery.api.schemas.processing import PreparationRequest
from satquery.core.config import load_settings
from satquery.db.processing import (
    PostgresProcessingRepository,
    ProcessingPersistenceError,
    ProcessingPrincipal,
)
from satquery.db.session import Database
from satquery.processing.jobs import PreparationJobService
from satquery.providers.catalog import EarthSearchCatalogueProvider
from satquery.storage import AtomicArtifactStore

REQUEST = PreparationRequest.model_validate(
    {
        "scenes": [
            {
                "provider": "earth-search",
                "collection": "sentinel-2-c1-l2a",
                "item": "S2C_T43PGQ_20251228T052411_L2A",
            }
        ],
        "aoi": {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.0000, 13.0000],
                    [77.0010, 13.0000],
                    [77.0010, 13.0010],
                    [77.0000, 13.0010],
                    [77.0000, 13.0000],
                ]
            ],
        },
        "required_bands": [
            {"role": role, "common_name": role} for role in ("red", "green", "blue")
        ],
        "intended_task": "optical_single_scene",
        "processing_profile": "sentinel-2-l2a-surface-reflectance-v1",
        "options": {
            "grid_policy": "common_utm",
            "target_resolution_metres": 10.0,
            "continuous_resampling": "bilinear",
            "max_output_pixels": 10_000,
        },
    }
)
PRINCIPAL = ProcessingPrincipal(
    owner_id=UUID("00000000-0000-4000-8000-00000000006a"),
    access_scope="verification:phase-6g",
)


async def verify() -> None:
    settings = load_settings()
    database = Database.from_settings(settings)
    provider = EarthSearchCatalogueProvider.from_settings(settings)
    service = PreparationJobService(
        PostgresProcessingRepository(database),
        provider,
        AtomicArtifactStore(
            settings.processing_artifact_root,
            max_job_bytes=settings.processing_max_artifact_bytes,
        ),
        max_concurrency=settings.processing_max_concurrency,
        timeout_seconds=settings.processing_timeout_seconds,
        max_pixels=settings.processing_max_pixels,
        max_memory_bytes=settings.processing_max_memory_bytes,
    )
    try:
        await service.start()
        record = await service.submit(
            PRINCIPAL,
            REQUEST,
            idempotency_key="phase-6g-real-single-v1",
        )
        while True:
            status = await service.status(PRINCIPAL, record.job_id)
            if status.state in {"succeeded", "failed", "cancelled"}:
                print(status.model_dump_json(indent=2))
                if status.state != "succeeded":
                    raise SystemExit(1)
                return
            await asyncio.sleep(0.2)
    except ProcessingPersistenceError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, indent=2))
        raise SystemExit(1) from None
    finally:
        await service.stop()
        await provider.aclose()
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(verify())
