from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from satquery.core.config import Settings
from satquery.db.session import DatabaseReadiness, DatabaseUnavailableError
from satquery.main import create_app


class ReadyDatabase:
    async def check_readiness(self) -> DatabaseReadiness:
        return DatabaseReadiness(
            server_version="18.synthetic",
            postgis_version="3.6.synthetic",
            migration_revision="20260907_0001",
        )

    async def dispose(self) -> None:
        return None


class UnavailableDatabase(ReadyDatabase):
    async def check_readiness(self) -> DatabaseReadiness:
        raise DatabaseUnavailableError("Synthetic unavailable database")


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        log_level="INFO",
        api_prefix="/api/v1",
        frontend_cors_origins=["http://localhost:3000"],
        database_url=SecretStr("postgresql+psycopg://user:password@127.0.0.1/satquery_test"),
    )


@pytest.fixture
def ready_client() -> Iterator[TestClient]:
    app = create_app(settings=make_settings(), database=ReadyDatabase())
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
