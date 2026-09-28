from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from satquery.core.config import Settings
from satquery.db.migrations import EXPECTED_MIGRATION_REVISION


class DatabaseUnavailableError(RuntimeError):
    """A public-safe database readiness failure."""


@dataclass(frozen=True, slots=True)
class DatabaseReadiness:
    server_version: str
    postgis_version: str
    migration_revision: str


class ReadinessDatabase(Protocol):
    async def check_readiness(self) -> DatabaseReadiness: ...

    async def dispose(self) -> None: ...


class Database:
    def __init__(
        self,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        health_timeout_seconds: float,
    ) -> None:
        self.engine = engine
        self.session_factory = session_factory
        self.health_timeout_seconds = health_timeout_seconds

    @classmethod
    def from_settings(cls, settings: Settings) -> Database:
        engine = create_async_engine(
            settings.database_url.get_secret_value(),
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout_seconds,
            connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
        )
        return cls(
            engine,
            async_sessionmaker(engine, expire_on_commit=False),
            health_timeout_seconds=settings.database_health_timeout_seconds,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        session = self.session_factory()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def check_readiness(self) -> DatabaseReadiness:
        try:
            async with asyncio.timeout(self.health_timeout_seconds):
                async with self.engine.connect() as connection:
                    server_version = str(
                        (await connection.execute(text("SHOW server_version"))).scalar_one()
                    )
                    postgis_version = (
                        await connection.execute(
                            text("SELECT extversion FROM pg_extension WHERE extname = 'postgis'")
                        )
                    ).scalar_one_or_none()
                    revision = (
                        await connection.execute(text("SELECT version_num FROM alembic_version"))
                    ).scalar_one_or_none()
        except (SQLAlchemyError, TimeoutError, OSError) as exc:
            raise DatabaseUnavailableError("Database readiness check failed.") from exc

        if postgis_version is None:
            raise DatabaseUnavailableError("PostGIS is not installed.")
        if revision != EXPECTED_MIGRATION_REVISION:
            raise DatabaseUnavailableError("Database migration revision is not current.")
        return DatabaseReadiness(
            server_version=server_version,
            postgis_version=str(postgis_version),
            migration_revision=str(revision),
        )

    async def dispose(self) -> None:
        await self.engine.dispose()
