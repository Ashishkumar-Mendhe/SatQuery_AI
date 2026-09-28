"""Durable GeoAgent context, partitioned by verified owner and access scope."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import SQLAlchemyError

from satquery.api.schemas.geoagent_conversation import ConversationState
from satquery.db.processing import ProcessingPrincipal
from satquery.db.session import Database


class ConversationPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VersionedConversation:
    state: ConversationState
    version: int


class ConversationRepository(Protocol):
    async def get(
        self, principal: ProcessingPrincipal, conversation_id: UUID
    ) -> VersionedConversation | None: ...

    async def save(
        self, principal: ProcessingPrincipal, state: ConversationState, expected_version: int
    ) -> bool: ...

    async def delete(self, principal: ProcessingPrincipal, conversation_id: UUID) -> bool: ...


class PostgresConversationRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def get(
        self, principal: ProcessingPrincipal, conversation_id: UUID
    ) -> VersionedConversation | None:
        try:
            async with self._database.session() as session:
                row = (
                    (
                        await session.execute(
                            text(
                                "SELECT version, state_json FROM geoagent_conversations "
                                "WHERE owner_id=:owner_id AND access_scope=:access_scope "
                                "AND conversation_id=:conversation_id"
                            ),
                            {
                                "owner_id": principal.owner_id,
                                "access_scope": principal.access_scope,
                                "conversation_id": conversation_id,
                            },
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            if row is None:
                return None
            return VersionedConversation(
                ConversationState.model_validate(row["state_json"]), int(row["version"])
            )
        except (SQLAlchemyError, ValueError) as exc:
            raise ConversationPersistenceError("Conversation storage is unavailable.") from exc

    async def save(
        self, principal: ProcessingPrincipal, state: ConversationState, expected_version: int
    ) -> bool:
        import json

        params = {
            "owner_id": principal.owner_id,
            "access_scope": principal.access_scope,
            "conversation_id": state.conversation_id,
            "state_json": json.dumps(state.model_dump(mode="json"), separators=(",", ":")),
            "updated_at": datetime.now(UTC),
            "expected_version": expected_version,
        }
        try:
            async with self._database.session() as session:
                if expected_version == 0:
                    result = await session.execute(
                        text(
                            "INSERT INTO geoagent_conversations "
                            "(owner_id, access_scope, conversation_id, version, "
                            "state_json, updated_at) "
                            "VALUES (:owner_id, :access_scope, :conversation_id, 1, "
                            "CAST(:state_json AS jsonb), :updated_at) ON CONFLICT DO NOTHING"
                        ),
                        params,
                    )
                else:
                    result = await session.execute(
                        text(
                            "UPDATE geoagent_conversations SET version=version+1, "
                            "state_json=CAST(:state_json AS jsonb), updated_at=:updated_at "
                            "WHERE owner_id=:owner_id AND access_scope=:access_scope "
                            "AND conversation_id=:conversation_id AND version=:expected_version"
                        ),
                        params,
                    )
                await session.commit()
                return cast(CursorResult[Any], result).rowcount == 1
        except SQLAlchemyError as exc:
            raise ConversationPersistenceError("Conversation storage is unavailable.") from exc

    async def delete(self, principal: ProcessingPrincipal, conversation_id: UUID) -> bool:
        try:
            async with self._database.session() as session:
                result = await session.execute(
                    text(
                        "DELETE FROM geoagent_conversations WHERE owner_id=:owner_id "
                        "AND access_scope=:access_scope AND conversation_id=:conversation_id"
                    ),
                    {
                        "owner_id": principal.owner_id,
                        "access_scope": principal.access_scope,
                        "conversation_id": conversation_id,
                    },
                )
                await session.commit()
                return cast(CursorResult[Any], result).rowcount == 1
        except SQLAlchemyError as exc:
            raise ConversationPersistenceError("Conversation storage is unavailable.") from exc
