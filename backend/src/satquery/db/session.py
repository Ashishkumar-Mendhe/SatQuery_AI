from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Import models to register them with Base.metadata
import satquery.db.models  # noqa: F401
from satquery.core.config import Settings
from satquery.db.base import Base
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
        is_sqlite: bool = False,
    ) -> None:
        self.engine = engine
        self.session_factory = session_factory
        self.health_timeout_seconds = health_timeout_seconds
        self.is_sqlite = is_sqlite

    @classmethod
    def from_settings(cls, settings: Settings) -> Database:
        url_str = settings.database_url.get_secret_value()
        parsed = make_url(url_str)
        is_sqlite = parsed.drivername in {"sqlite+aiosqlite", "sqlite"}

        if is_sqlite:
            if parsed.database and parsed.database != ":memory:":
                db_path = Path(parsed.database)
                if not db_path.is_absolute():
                    db_path = Path.cwd() / db_path
                db_path.parent.mkdir(parents=True, exist_ok=True)
            engine = create_async_engine(
                url_str,
                connect_args={"timeout": settings.database_connect_timeout_seconds},
            )
        else:
            engine = create_async_engine(
                url_str,
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
            is_sqlite=is_sqlite,
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

    async def init_schema(self) -> None:
        """Idempotently create tables if they do not exist."""
        try:
            async with self.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        except Exception as exc:
            raise DatabaseUnavailableError("Failed to initialize database schema.") from exc

    async def check_readiness(self) -> DatabaseReadiness:
        try:
            async with asyncio.timeout(self.health_timeout_seconds):
                async with self.engine.connect() as connection:
                    if self.is_sqlite:
                        server_version = str(
                            (await connection.execute(text("SELECT sqlite_version()"))).scalar_one()
                        )
                        # Ensure tables exist
                        table_check = (
                            await connection.execute(
                                text(
                                    "SELECT name FROM sqlite_master WHERE type='table' AND name='workspaces'"
                                )
                            )
                        ).scalar_one_or_none()
                        if table_check is None:
                            # Auto-create if not yet created
                            await self.init_schema()
                        return DatabaseReadiness(
                            server_version=f"SQLite {server_version}",
                            postgis_version="sqlite-spatial-json",
                            migration_revision="current",
                        )

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
