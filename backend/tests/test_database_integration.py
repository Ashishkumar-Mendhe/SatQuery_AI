from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from satquery.core.config import load_settings
from satquery.db.migrations import EXPECTED_MIGRATION_REVISION
from satquery.main import create_app

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def require_isolated_database_url() -> str:
    url = os.getenv("SATQUERY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("SATQUERY_TEST_DATABASE_URL is not configured")
    parsed = urlsplit(url.replace("postgresql+psycopg", "postgresql", 1))
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("Integration database must use a loopback host")
    if not parsed.path.removeprefix("/").endswith("_test"):
        pytest.fail("Integration database name must end with '_test'")
    return url


@pytest.mark.integration
def test_migration_and_real_postgis_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    url = require_isolated_database_url()
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SATQUERY_ENV", "test")

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.upgrade(config, "head")

    settings = load_settings(env_file=None)
    app = create_app(settings=settings)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    database_status = response.json()["checks"]["database"]
    assert database_status["migration_revision"] == EXPECTED_MIGRATION_REVISION
    assert database_status["postgis_version"]
