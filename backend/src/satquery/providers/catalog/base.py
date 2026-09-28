from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from satquery.api.schemas.asset_resolution import (
    AssetResolutionRequest,
    AssetResolutionResponse,
    ResolvedRasterComponent,
)
from satquery.api.schemas.catalog import (
    CatalogueScene,
    CatalogueSearchRequest,
    CatalogueSearchResponse,
)


@dataclass(frozen=True, slots=True)
class CatalogueProviderCapabilities:
    provider_id: str
    stac_version: str
    supports_intersects: bool
    supports_cloud_filter: bool
    supports_sort: bool
    supported_queryables: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CatalogueCollection:
    id: str
    title: str | None
    description: str | None
    license_name: str | None
    license_url: str | None
    temporal_start: str | None
    temporal_end: str | None
    platforms: tuple[str, ...]
    instruments: tuple[str, ...]
    spatial_resolutions_metres: tuple[float, ...]


class CatalogueProviderError(RuntimeError):
    """A stable, public-safe provider failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool,
        upstream_status: int | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.upstream_status = upstream_status
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class ResolvedRasterSource:
    """Server-only raster location paired with its validated public metadata."""

    component: ResolvedRasterComponent
    location: str
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class ResolvedImagerySourceSet:
    resolution: AssetResolutionResponse
    sources: tuple[ResolvedRasterSource, ...]


class CatalogueProvider(Protocol):
    async def capabilities(self) -> CatalogueProviderCapabilities: ...

    async def collections(self) -> list[CatalogueCollection]: ...

    async def search(self, request: CatalogueSearchRequest) -> CatalogueSearchResponse: ...

    async def item(self, collection_id: str, item_id: str) -> CatalogueScene: ...

    async def resolve_imagery(self, request: AssetResolutionRequest) -> AssetResolutionResponse: ...

    async def resolve_imagery_sources(
        self, request: AssetResolutionRequest
    ) -> ResolvedImagerySourceSet: ...

    async def aclose(self) -> None: ...
