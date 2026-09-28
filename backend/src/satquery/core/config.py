from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
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

    # -----------------------------------------------------------------------
    # Application settings
    # -----------------------------------------------------------------------
    app_name: str = Field(default="SatQuery AI", validation_alias="SATQUERY_APP_NAME")
    environment: Literal["development", "test", "staging", "production"] = Field(
        default="development",
        validation_alias=AliasChoices("SATQUERY_ENV", "SATQUERY_ENVIRONMENT"),
    )
    debug: bool = Field(default=False, validation_alias="SATQUERY_DEBUG")
    contract_version: str = Field(default="1.0", validation_alias="SATQUERY_CONTRACT_VERSION")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", validation_alias="SATQUERY_LOG_LEVEL"
    )
    api_prefix: Literal["/api/v1"] = Field(
        default="/api/v1", validation_alias="SATQUERY_API_PREFIX"
    )
    frontend_cors_origins: Annotated[list[AnyHttpUrl], NoDecode] = Field(
        default_factory=lambda: [AnyHttpUrl("http://localhost:3000")],
        validation_alias=AliasChoices("FRONTEND_CORS_ORIGINS", "SATQUERY_ALLOWED_ORIGINS"),
    )

    # -----------------------------------------------------------------------
    # Database settings
    # -----------------------------------------------------------------------
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

    # -----------------------------------------------------------------------
    # Satellite imagery provider settings
    # -----------------------------------------------------------------------
    catalogue_provider: Literal[
        "earth-search", "sentinel_hub", "copernicus_dataspace", "planetary_computer", "mock"
    ] = Field(
        default="earth-search",
        validation_alias=AliasChoices("SATQUERY_SATELLITE_PROVIDER", "CATALOGUE_PROVIDER"),
    )
    satellite_provider_mode: Literal["mock", "real", "disabled"] = Field(
        default="real", validation_alias="SATQUERY_SATELLITE_PROVIDER_MODE"
    )
    satellite_base_url: AnyHttpUrl | None = Field(
        default=None, validation_alias="SATQUERY_SATELLITE_BASE_URL"
    )
    satellite_client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SATQUERY_SATELLITE_CLIENT_ID", "EO_PROVIDER_CLIENT_ID"),
    )
    satellite_client_secret: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SATQUERY_SATELLITE_CLIENT_SECRET", "EO_PROVIDER_CLIENT_SECRET"
        ),
    )
    satellite_access_token: SecretStr | None = Field(
        default=None, validation_alias="SATQUERY_SATELLITE_ACCESS_TOKEN"
    )
    satellite_timeout_seconds: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        validation_alias=AliasChoices(
            "SATQUERY_SATELLITE_TIMEOUT_SECONDS", "EARTH_SEARCH_TIMEOUT_SECONDS"
        ),
    )
    satellite_max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        validation_alias=AliasChoices("SATQUERY_SATELLITE_MAX_RETRIES", "EARTH_SEARCH_MAX_RETRIES"),
    )
    default_collection: str = Field(
        default="sentinel-2-c1-l2a", min_length=1, validation_alias="SATQUERY_DEFAULT_COLLECTION"
    )
    default_cloud_cover: float = Field(
        default=20.0, ge=0.0, le=100.0, validation_alias="SATQUERY_DEFAULT_CLOUD_COVER"
    )
    max_catalog_results: int = Field(
        default=50, ge=1, le=200, validation_alias="SATQUERY_MAX_CATALOG_RESULTS"
    )
    max_aoi_square_km: float = Field(
        default=10000.0, ge=0.1, le=50000.0, validation_alias="SATQUERY_MAX_AOI_SQUARE_KM"
    )

    # Legacy Earth Search STAC settings
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

    # -----------------------------------------------------------------------
    # Imagery tile settings
    # -----------------------------------------------------------------------
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
    max_preview_width: int = Field(
        default=2048, ge=64, le=4096, validation_alias="IMAGERY_MAX_PREVIEW_WIDTH"
    )
    max_preview_height: int = Field(
        default=2048, ge=64, le=4096, validation_alias="IMAGERY_MAX_PREVIEW_HEIGHT"
    )
    max_preview_pixels: int = Field(
        default=4_194_304,
        ge=16384,
        le=16_777_216,
        validation_alias="IMAGERY_MAX_PREVIEW_PIXELS",
    )
    max_analysis_raster_pixels: int = Field(
        default=16_777_216,
        ge=65536,
        le=67_108_864,
        validation_alias="IMAGERY_MAX_ANALYSIS_RASTER_PIXELS",
    )
    max_imagery_file_size_bytes: int = Field(
        default=50 * 1024 * 1024,
        ge=1024 * 1024,
        le=200 * 1024 * 1024,
        validation_alias="IMAGERY_MAX_FILE_SIZE_BYTES",
    )
    min_allowed_resolution_meters: float = Field(
        default=1.0, ge=0.1, le=100.0, validation_alias="IMAGERY_MIN_ALLOWED_RESOLUTION_METERS"
    )
    max_allowed_resolution_meters: float = Field(
        default=1000.0,
        ge=10.0,
        le=10000.0,
        validation_alias="IMAGERY_MAX_ALLOWED_RESOLUTION_METERS",
    )
    imagery_asset_cache_ttl_seconds: int = Field(
        default=1800, ge=60, le=86400, validation_alias="IMAGERY_ASSET_CACHE_TTL_SECONDS"
    )
    imagery_storage_dir: Path = Field(
        default=Path("tmp/imagery_assets"), validation_alias="IMAGERY_STORAGE_DIR"
    )

    # -----------------------------------------------------------------------
    # AI / VLM provider settings
    # -----------------------------------------------------------------------
    ai_provider: Literal["gemini", "openai", "mock", "disabled"] = Field(
        default="gemini",
        validation_alias=AliasChoices("SATQUERY_AI_PROVIDER", "RUNTIME_AI_PROVIDER"),
    )
    ai_provider_mode: Literal["mock", "real", "disabled"] = Field(
        default="mock", validation_alias="SATQUERY_AI_PROVIDER_MODE"
    )
    ai_base_url: AnyHttpUrl | None = Field(default=None, validation_alias="SATQUERY_AI_BASE_URL")
    ai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SATQUERY_AI_API_KEY", "RUNTIME_AI_API_KEY", "GEMINI_API_KEY"
        ),
    )
    ai_model: str = Field(
        default="gemini-2.0-flash",
        min_length=1,
        validation_alias=AliasChoices("SATQUERY_AI_MODEL", "RUNTIME_AI_MODEL"),
    )
    ai_timeout_seconds: float = Field(
        default=30.0, ge=1.0, le=120.0, validation_alias="SATQUERY_AI_TIMEOUT_SECONDS"
    )
    ai_max_retries: int = Field(default=2, ge=0, le=5, validation_alias="SATQUERY_AI_MAX_RETRIES")
    ai_enabled: bool = Field(default=True, validation_alias="SATQUERY_AI_ENABLED")

    # -----------------------------------------------------------------------
    # Processing & Demo / Fallback settings
    # -----------------------------------------------------------------------
    processing_mode: Literal["standard", "fast", "deep"] = Field(
        default="standard", validation_alias="SATQUERY_PROCESSING_MODE"
    )
    max_concurrent_jobs: int = Field(
        default=4, ge=1, le=20, validation_alias="SATQUERY_MAX_CONCURRENT_JOBS"
    )
    default_resolution_meters: float = Field(
        default=10.0, ge=1.0, le=100.0, validation_alias="SATQUERY_DEFAULT_RESOLUTION_METERS"
    )
    overlay_generation_enabled: bool = Field(
        default=True, validation_alias="SATQUERY_OVERLAY_GENERATION_ENABLED"
    )
    report_generation_enabled: bool = Field(
        default=True, validation_alias="SATQUERY_REPORT_GENERATION_ENABLED"
    )
    demo_mode: bool = Field(default=False, validation_alias="SATQUERY_DEMO_MODE")
    allow_mock_fallback: bool = Field(default=True, validation_alias="SATQUERY_ALLOW_MOCK_FALLBACK")
    mock_latency_ms: int = Field(
        default=0, ge=0, le=5000, validation_alias="SATQUERY_MOCK_LATENCY_MS"
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
            raise ValueError("must be a valid SQLAlchemy Database URL") from exc
        if parsed.drivername in {"sqlite+aiosqlite", "sqlite"}:
            return value
        if parsed.drivername != "postgresql+psycopg" or not parsed.host or not parsed.database:
            raise ValueError(
                "must use postgresql+psycopg with an explicit host and database name or sqlite+aiosqlite"
            )
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

    @model_validator(mode="after")
    def validate_environment_policy(self) -> Self:
        if self.environment == "production":
            if self.debug:
                raise ValueError("Production mode cannot enable debug")
            local_origins = {"localhost", "127.0.0.1", "::1"}
            if any(origin.host in local_origins for origin in self.frontend_cors_origins):
                raise ValueError("production CORS origins must not use loopback hosts")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.frontend_cors_origins]

    def get_safe_summary(self) -> dict[str, Any]:
        """Return a public-safe configuration snapshot with all secrets redacted."""
        return {
            "app_name": self.app_name,
            "environment": self.environment,
            "debug": self.debug,
            "contract_version": self.contract_version,
            "log_level": self.log_level,
            "api_prefix": self.api_prefix,
            "cors_origins": self.cors_origins,
            "satellite_provider": self.catalogue_provider,
            "satellite_provider_mode": self.satellite_provider_mode,
            "satellite_has_credentials": bool(
                self.satellite_client_secret or self.satellite_access_token
            ),
            "ai_provider": self.ai_provider,
            "ai_provider_mode": self.ai_provider_mode,
            "ai_model": self.ai_model,
            "ai_has_api_key": bool(self.ai_api_key),
            "processing_mode": self.processing_mode,
            "demo_mode": self.demo_mode,
            "allow_mock_fallback": self.allow_mock_fallback,
        }


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
