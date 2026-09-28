from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import AnyHttpUrl, Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_ENV_FILE = REPOSITORY_ROOT / ".env"


class SettingsError(RuntimeError):
    """A public-safe configuration failure."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: Literal["development", "test", "staging", "production"] = Field(
        default="development", validation_alias="SATQUERY_ENV"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", validation_alias="SATQUERY_LOG_LEVEL"
    )
    api_prefix: Literal["/api/v1"] = Field(
        default="/api/v1", validation_alias="SATQUERY_API_PREFIX"
    )
    frontend_cors_origins: Annotated[list[AnyHttpUrl], NoDecode] = Field(
        default_factory=lambda: [AnyHttpUrl("http://localhost:3000")],
        validation_alias="FRONTEND_CORS_ORIGINS",
    )
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")
    database_connect_timeout_seconds: int = Field(
        default=3, ge=1, le=30, validation_alias="DB_CONNECT_TIMEOUT_SECONDS"
    )
    database_health_timeout_seconds: float = Field(
        default=5.0, ge=0.1, le=30.0, validation_alias="DB_HEALTH_TIMEOUT_SECONDS"
    )
    database_pool_size: int = Field(default=5, ge=1, le=50, validation_alias="DB_POOL_SIZE")
    database_max_overflow: int = Field(default=5, ge=0, le=100, validation_alias="DB_MAX_OVERFLOW")
    database_pool_timeout_seconds: float = Field(
        default=10.0, ge=0.1, le=60.0, validation_alias="DB_POOL_TIMEOUT_SECONDS"
    )
    catalogue_provider: Literal["earth-search"] = Field(
        default="earth-search", validation_alias="CATALOGUE_PROVIDER"
    )
    earth_search_base_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("https://earth-search.aws.element84.com/v1/"),
        validation_alias="EARTH_SEARCH_BASE_URL",
    )
    earth_search_timeout_seconds: float = Field(
        default=10.0, ge=1.0, le=30.0, validation_alias="EARTH_SEARCH_TIMEOUT_SECONDS"
    )
    earth_search_max_retries: int = Field(
        default=2, ge=0, le=3, validation_alias="EARTH_SEARCH_MAX_RETRIES"
    )
    earth_search_cache_ttl_seconds: int = Field(
        default=300, ge=1, le=3600, validation_alias="EARTH_SEARCH_CACHE_TTL_SECONDS"
    )
    earth_search_cache_max_entries: int = Field(
        default=32, ge=1, le=128, validation_alias="EARTH_SEARCH_CACHE_MAX_ENTRIES"
    )
    imagery_tile_max_zoom: int = Field(
        default=16, ge=0, le=22, validation_alias="IMAGERY_TILE_MAX_ZOOM"
    )
    imagery_tile_request_timeout_seconds: float = Field(
        default=30.0, ge=1.0, le=30.0, validation_alias="IMAGERY_TILE_REQUEST_TIMEOUT_SECONDS"
    )
    imagery_tile_max_concurrency: int = Field(
        default=2, ge=1, le=8, validation_alias="IMAGERY_TILE_MAX_CONCURRENCY"
    )
    imagery_tile_set_ttl_seconds: int = Field(
        default=300, ge=30, le=3600, validation_alias="IMAGERY_TILE_SET_TTL_SECONDS"
    )
    imagery_tile_set_cache_max_entries: int = Field(
        default=32, ge=1, le=128, validation_alias="IMAGERY_TILE_SET_CACHE_MAX_ENTRIES"
    )
    imagery_tile_byte_cache_max_bytes: int = Field(
        default=16 * 1024 * 1024,
        ge=1024 * 1024,
        le=128 * 1024 * 1024,
        validation_alias="IMAGERY_TILE_BYTE_CACHE_MAX_BYTES",
    )
    processing_artifact_root: Path = Field(
        default=REPOSITORY_ROOT / ".satquery-artifacts",
        validation_alias="PROCESSING_ARTIFACT_ROOT",
    )
    nisar_product_cache_root: Path = Field(
        default=REPOSITORY_ROOT / ".satquery-nisar-products",
        validation_alias="NISAR_PRODUCT_CACHE_ROOT",
    )
    processing_max_concurrency: int = Field(
        default=1, ge=1, le=4, validation_alias="PROCESSING_MAX_CONCURRENCY"
    )
    processing_timeout_seconds: float = Field(
        default=300.0, ge=10.0, le=3600.0, validation_alias="PROCESSING_TIMEOUT_SECONDS"
    )
    processing_max_pixels: int = Field(
        default=4_000_000, ge=1, le=4_000_000, validation_alias="PROCESSING_MAX_PIXELS"
    )
    processing_max_memory_bytes: int = Field(
        default=512 * 1024 * 1024,
        ge=64 * 1024 * 1024,
        le=4 * 1024 * 1024 * 1024,
        validation_alias="PROCESSING_MAX_MEMORY_BYTES",
    )
    processing_max_artifact_bytes: int = Field(
        default=512 * 1024 * 1024,
        ge=16 * 1024 * 1024,
        le=4 * 1024 * 1024 * 1024,
        validation_alias="PROCESSING_MAX_ARTIFACT_BYTES",
    )
    runtime_ai_provider: Literal["openai", "xai"] | None = Field(
        default=None, validation_alias="RUNTIME_AI_PROVIDER"
    )
    runtime_ai_api_key: SecretStr | None = Field(
        default=None, validation_alias="RUNTIME_AI_API_KEY"
    )
    xai_api_key: SecretStr | None = Field(default=None, validation_alias="XAI_API_KEY")
    runtime_ai_model: Literal["gpt-4.1-mini-2025-04-14", "grok-4.3"] | None = Field(
        default=None, validation_alias="RUNTIME_AI_MODEL"
    )
    runtime_ai_timeout_seconds: float = Field(
        default=60.0,
        ge=1.0,
        le=120.0,
        validation_alias="RUNTIME_AI_TIMEOUT_SECONDS",
    )
    runtime_ai_max_concurrency: int = Field(
        default=1, ge=1, le=2, validation_alias="RUNTIME_AI_MAX_CONCURRENCY"
    )
    runtime_ai_max_output_tokens: int = Field(
        default=300, ge=1, le=512, validation_alias="RUNTIME_AI_MAX_OUTPUT_TOKENS"
    )

    @field_validator("frontend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        candidate = value.strip()
        if candidate.startswith("["):
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError as exc:
                raise ValueError("must be a JSON array or comma-separated URL list") from exc
            return parsed
        return [item.strip() for item in candidate.split(",") if item.strip()]

    @field_validator("frontend_cors_origins")
    @classmethod
    def validate_cors_origins(cls, values: list[AnyHttpUrl]) -> list[AnyHttpUrl]:
        for origin in values:
            if (
                origin.username
                or origin.password
                or origin.query
                or origin.fragment
                or origin.path not in {None, "", "/"}
            ):
                raise ValueError("entries must be HTTP(S) origins without credentials or paths")
        return values

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            parsed = make_url(value.get_secret_value())
        except ArgumentError as exc:
            raise ValueError("must be a valid SQLAlchemy PostgreSQL URL") from exc
        if parsed.drivername != "postgresql+psycopg" or not parsed.host or not parsed.database:
            raise ValueError("must use postgresql+psycopg with an explicit host and database name")
        return value

    @field_validator("earth_search_base_url")
    @classmethod
    def validate_earth_search_base_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if (
            value.scheme != "https"
            or value.host != "earth-search.aws.element84.com"
            or value.port != 443
            or value.username
            or value.password
            or value.query
            or value.fragment
            or (value.path or "").rstrip("/") != "/v1"
        ):
            raise ValueError("must be the credential-free Earth Search HTTPS v1 endpoint")
        return value

    @field_validator("processing_artifact_root", "nisar_product_cache_root")
    @classmethod
    def resolve_processing_artifact_root(cls, value: Path) -> Path:
        return (REPOSITORY_ROOT / value).resolve() if not value.is_absolute() else value.resolve()

    @field_validator(
        "runtime_ai_provider",
        "runtime_ai_api_key",
        "xai_api_key",
        "runtime_ai_model",
        mode="before",
    )
    @classmethod
    def normalize_empty_runtime_ai_values(cls, value: Any) -> Any:
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def validate_environment_policy(self) -> Self:
        if self.environment == "production":
            local_origins = {"localhost", "127.0.0.1", "::1"}
            if any(origin.host in local_origins for origin in self.frontend_cors_origins):
                raise ValueError("production CORS origins must not use loopback hosts")
        if self.runtime_ai_provider is not None or self.runtime_ai_model is not None:
            selected_key = (
                self.xai_api_key if self.runtime_ai_provider == "xai" else self.runtime_ai_api_key
            )
            configured = (
                self.runtime_ai_provider is not None,
                self.runtime_ai_model is not None,
                selected_key is not None and bool(selected_key.get_secret_value().strip()),
            )
            if any(configured) and not all(configured):
                raise ValueError(
                    "runtime AI provider, pinned model, and non-empty API key must be "
                    "configured together"
                )
            if (self.runtime_ai_provider, self.runtime_ai_model) not in {
                ("openai", "gpt-4.1-mini-2025-04-14"),
                ("xai", "grok-4.3"),
            }:
                raise ValueError("runtime AI provider and pinned model do not match")
        return self

    @property
    def runtime_ai_available(self) -> bool:
        return (
            self.runtime_ai_provider == "openai"
            and self.runtime_ai_model == "gpt-4.1-mini-2025-04-14"
            and self.runtime_ai_api_key is not None
            and bool(self.runtime_ai_api_key.get_secret_value().strip())
        ) or (
            self.runtime_ai_provider == "xai"
            and self.runtime_ai_model == "grok-4.3"
            and self.xai_api_key is not None
            and bool(self.xai_api_key.get_secret_value().strip())
        )

    @property
    def cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.frontend_cors_origins]


def _safe_validation_summary(exc: ValidationError) -> str:
    issues = []
    for error in exc.errors(include_url=False, include_context=False, include_input=False):
        field = ".".join(str(part) for part in error["loc"])
        issues.append(f"{field}: {error['msg']}")
    return "; ".join(issues)


def load_settings(*, env_file: Path | None = DEFAULT_ENV_FILE) -> Settings:
    try:
        return Settings(_env_file=env_file)
    except ValidationError as exc:
        raise SettingsError(
            f"Invalid backend configuration: {_safe_validation_summary(exc)}"
        ) from None


@lru_cache
def get_settings() -> Settings:
    return load_settings()
