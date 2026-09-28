from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LivenessResponse(StrictResponse):
    status: Literal["live"]
    service: Literal["satquery-api"]
    version: str


class DatabaseHealth(StrictResponse):
    status: Literal["up"]
    postgis: Literal["available"]
    migration: Literal["current"]
    server_version: str
    postgis_version: str
    migration_revision: str


class ReadinessChecks(StrictResponse):
    database: DatabaseHealth


class ReadinessResponse(StrictResponse):
    status: Literal["ready"]
    service: Literal["satquery-api"]
    version: str
    request_id: str
    checks: ReadinessChecks
