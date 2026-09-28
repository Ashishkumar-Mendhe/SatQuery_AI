"""Verification-only ASGI app: real provider/model with in-memory durable-contract fixture.

This is never imported by production. It bypasses unavailable PostgreSQL only so the browser can
exercise the real 7D orchestration, trusted COG extraction, QA decoding, and local grounding model.
It does not supply fake model answers or scientific inputs.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import Request

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "tests"))

from conftest import ReadyDatabase, make_settings  # noqa: E402
from test_processing_jobs import MemoryRepository  # noqa: E402

from satquery.db.processing import ProcessingPrincipal  # noqa: E402
from satquery.inference.grounding import (  # noqa: E402
    ReferringGroundingService,
    TransformersGroundingDinoRuntime,
)
from satquery.inference.jobs import InferenceJobService  # noqa: E402
from satquery.main import create_app  # noqa: E402
from satquery.providers.catalog import EarthSearchCatalogueProvider  # noqa: E402
from satquery.storage import AtomicArtifactStore  # noqa: E402

VERIFICATION_OWNER = UUID("10000000-0000-4000-8000-000000000071")


async def _principal(request: Request) -> ProcessingPrincipal:
    return ProcessingPrincipal(VERIFICATION_OWNER, "verification:phase-7e-real-provider")


def app_factory() -> Any:
    settings = make_settings()
    provider = EarthSearchCatalogueProvider.from_settings(settings)
    service = InferenceJobService(
        MemoryRepository(),
        provider,
        AtomicArtifactStore(
            BACKEND_ROOT.parent / "tmp" / "phase-7e-browser-artifacts",
            max_job_bytes=32 * 1024 * 1024,
        ),
        answer_service=None,
        grounding_service=ReferringGroundingService(
            TransformersGroundingDinoRuntime(local_files_only=True),
            max_concurrency=1,
        ),
        max_concurrency=1,
        timeout_seconds=360.0,
        max_pixels=100_000,
    )
    return create_app(
        settings=settings,
        database=ReadyDatabase(),
        catalogue_provider=provider,
        inference_job_service=service,
        processing_principal_resolver=_principal,
    )
