from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import random
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from math import isfinite
from typing import Any, Literal, TypeVar, cast
from urllib.parse import quote, unquote, urljoin, urlsplit
from uuid import uuid4

import httpx2
from pydantic import TypeAdapter, ValidationError

from satquery.api.schemas.asset_resolution import (
    AssetResolutionRequest,
    AssetResolutionResponse,
    AssetResolutionStatus,
    ResolvedRasterComponent,
)
from satquery.api.schemas.catalog import (
    AcquisitionInterval,
    AssetAccess,
    CatalogGeometry,
    CatalogueLicense,
    CataloguePreview,
    CatalogueProvenance,
    CatalogueScene,
    CatalogueSearchRequest,
    CatalogueSearchResponse,
    CloudCoverMetadata,
    CollectionIdentity,
    FieldAvailability,
    FieldProvenance,
    ProviderIdentity,
    SpatialResolution,
)
from satquery.api.schemas.viewer import (
    AnalysisReadiness,
    AssetAccessibility,
    CatalogueAvailability,
    RenderStatus,
    ResolvedImageryAsset,
    ResolvedImageryAssetIdentity,
    SupportedRenderPreset,
)
from satquery.core.config import Settings
from satquery.providers.catalog.base import (
    CatalogueCollection,
    CatalogueProviderCapabilities,
    CatalogueProviderError,
    ResolvedImagerySourceSet,
    ResolvedRasterSource,
)

EARTH_SEARCH_PROVIDER_ID = "earth-search"
EARTH_SEARCH_PROVIDER_NAME = "Earth Search by Element 84"
EARTH_SEARCH_ADAPTER_VERSION = "1.0"
EARTH_SEARCH_DEFAULT_BASE_URL = "https://earth-search.aws.element84.com/v1/"
EARTH_SEARCH_ALLOWED_COLLECTIONS = frozenset({"sentinel-2-c1-l2a"})
EARTH_SEARCH_DEFAULT_COLLECTION = "sentinel-2-c1-l2a"
EARTH_SEARCH_PREVIEW_HOSTS = frozenset(
    {"e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com"}
)
EARTH_SEARCH_RASTER_HOSTS = EARTH_SEARCH_PREVIEW_HOSTS
EARTH_SEARCH_ATTRIBUTION = "Earth Search metadata; Copernicus Sentinel data."

_TRANSIENT_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
_MAX_METADATA_BYTES = 10 * 1024 * 1024
_MAX_PROVIDER_TOKEN_LENGTH = 1024
_GEOMETRY_ADAPTER: TypeAdapter[CatalogGeometry] = TypeAdapter(CatalogGeometry)
_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class _RasterCandidate:
    asset_id: str
    href: str
    band_name: str
    common_name: Literal["red", "green", "blue"]
    media_type: str
    asset_version: str | None
    scale: float | None
    offset: float | None
    nodata: float | Literal["nan", "inf", "-inf"] | None
    crs: str | None
    resolution_metres: float | None
    shape: tuple[int, int] | None
    transform: tuple[float, ...] | None
    expires_at: datetime | None


class _MetadataCache:
    def __init__(
        self,
        *,
        max_entries: int,
        ttl_seconds: int,
        clock: Callable[[], float],
    ) -> None:
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        inserted_at, value = entry
        if self._clock() - inserted_at >= self._ttl_seconds:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return deepcopy(value)

    def put(self, key: str, value: Any) -> None:
        self._entries[key] = (self._clock(), deepcopy(value))
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)


class EarthSearchCatalogueProvider:
    """Restricted STAC metadata and asset resolver for the allow-listed collection."""

    def __init__(
        self,
        *,
        base_url: str = EARTH_SEARCH_DEFAULT_BASE_URL,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        cache_ttl_seconds: int = 300,
        cache_max_entries: int = 32,
        client: httpx2.AsyncClient | None = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[float, float], float] = random.uniform,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._base_url = self._validate_base_url(base_url)
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._sleeper = sleeper
        self._jitter = jitter
        self._now = now or (lambda: datetime.now(UTC))
        self._cache = _MetadataCache(
            max_entries=cache_max_entries,
            ttl_seconds=cache_ttl_seconds,
            clock=clock,
        )
        self._owns_client = client is None
        self._client = client or httpx2.AsyncClient(
            timeout=httpx2.Timeout(timeout_seconds),
            follow_redirects=False,
            trust_env=False,
            headers={"Accept": "application/json, application/geo+json"},
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> EarthSearchCatalogueProvider:
        return cls(
            base_url=str(settings.earth_search_base_url),
            timeout_seconds=settings.earth_search_timeout_seconds,
            max_retries=settings.earth_search_max_retries,
            cache_ttl_seconds=settings.earth_search_cache_ttl_seconds,
            cache_max_entries=settings.earth_search_cache_max_entries,
        )

    @staticmethod
    def _validate_base_url(value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "earth-search.aws.element84.com"
            or parsed.port is not None
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path.rstrip("/") != "/v1"
        ):
            raise ValueError("Earth Search base URL is not an approved provider endpoint")
        return "https://earth-search.aws.element84.com/v1/"

    async def __aenter__(self) -> EarthSearchCatalogueProvider:
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def capabilities(self) -> CatalogueProviderCapabilities:
        cache_key = "capabilities"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cast(CatalogueProviderCapabilities, cached)

        root = await self._request_json("GET", "")
        queryables = await self._request_json(
            "GET", f"collections/{EARTH_SEARCH_DEFAULT_COLLECTION}/queryables"
        )
        conformance = self._string_list(root.get("conformsTo"))
        queryable_names = tuple(sorted(self._mapping(queryables.get("properties")).keys()))
        capabilities = CatalogueProviderCapabilities(
            provider_id=EARTH_SEARCH_PROVIDER_ID,
            stac_version=self._required_string(root, "stac_version", "catalogue root"),
            supports_intersects=any("item-search" in item for item in conformance),
            supports_cloud_filter="eo:cloud_cover" in queryable_names,
            supports_sort=any("item-search#sort" in item for item in conformance),
            supported_queryables=queryable_names,
        )
        if not (
            capabilities.supports_intersects
            and capabilities.supports_cloud_filter
            and capabilities.supports_sort
        ):
            raise CatalogueProviderError(
                "PROVIDER_CAPABILITY_UNAVAILABLE",
                "Earth Search does not advertise all required catalogue search capabilities.",
                retryable=False,
            )
        self._cache.put(cache_key, capabilities)
        return capabilities

    async def collections(self) -> list[CatalogueCollection]:
        cache_key = "collections"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cast(list[CatalogueCollection], cached)

        payload = await self._request_json("GET", "collections")
        raw_collections = payload.get("collections")
        if not isinstance(raw_collections, list):
            raise self._invalid_response("Earth Search collections are missing.")
        discovered = [
            self._normalize_collection(self._mapping(raw))
            for raw in raw_collections
            if isinstance(raw, Mapping) and raw.get("id") in EARTH_SEARCH_ALLOWED_COLLECTIONS
        ]
        if {item.id for item in discovered} != EARTH_SEARCH_ALLOWED_COLLECTIONS:
            raise self._invalid_response(
                "The required Sentinel-2 L2A collection was not discovered."
            )
        self._cache.put(cache_key, discovered)
        return discovered

    async def search(self, request: CatalogueSearchRequest) -> CatalogueSearchResponse:
        if request.provider != EARTH_SEARCH_PROVIDER_ID:
            raise CatalogueProviderError(
                "UNSUPPORTED_PROVIDER",
                "This adapter serves only the earth-search provider.",
                retryable=False,
            )
        if request.cloud_cover is not None and request.cloud_cover.include_unknown:
            raise CatalogueProviderError(
                "UNSUPPORTED_FILTER",
                "Earth Search cloud filtering cannot include records with unknown cloud cover.",
                retryable=False,
            )
        collections = self._resolve_collections(request.collections)
        await self.capabilities()
        collection_map = {item.id: item for item in await self.collections()}
        signature = self._request_signature(request, collections)
        continuation = self._decode_cursor(request.cursor, signature) if request.cursor else None
        body = self._search_body(request, collections, continuation)
        payload = await self._request_json("POST", "search", json_body=body)
        features = payload.get("features")
        if not isinstance(features, list):
            raise self._invalid_response("Earth Search search results are missing features.")
        retrieved_at = self._utc_now()
        items = [
            self._normalize_item(
                self._mapping(feature),
                collection_map,
                retrieved_at=retrieved_at,
            )
            for feature in features[: request.limit]
        ]
        next_cursor = self._next_cursor(payload, signature)
        return CatalogueSearchResponse(
            search_id=uuid4(),
            status="succeeded",
            query=request,
            provider=self._provider_identity(),
            items=items,
            returned_count=len(items),
            next_cursor=next_cursor,
            searched_at=retrieved_at,
            attributions=[EARTH_SEARCH_ATTRIBUTION],
        )

    async def item(self, collection_id: str, item_id: str) -> CatalogueScene:
        self._require_collection(collection_id)
        if not item_id or len(item_id) > 512 or any(ord(char) < 0x20 for char in item_id):
            raise CatalogueProviderError(
                "INVALID_ITEM_ID", "The provider item identifier is invalid.", retryable=False
            )
        cache_key = f"item:{collection_id}:{item_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cast(CatalogueScene, cached)
        collection_map = {item.id: item for item in await self.collections()}
        payload = await self._item_payload(collection_id, item_id)
        scene = self._normalize_item(payload, collection_map, retrieved_at=self._utc_now())
        if scene.provider_asset_id != item_id or scene.collection.id != collection_id:
            raise self._invalid_response("Earth Search returned a different catalogue item.")
        self._cache.put(cache_key, scene)
        return scene

    async def resolve_imagery(self, request: AssetResolutionRequest) -> AssetResolutionResponse:
        source_set = await self.resolve_imagery_sources(request)
        return source_set.resolution

    async def resolve_imagery_sources(
        self, request: AssetResolutionRequest
    ) -> ResolvedImagerySourceSet:
        identity = request.scene
        if identity.provider != EARTH_SEARCH_PROVIDER_ID:
            raise CatalogueProviderError(
                "UNSUPPORTED_PROVIDER",
                "This adapter serves only the earth-search provider.",
                retryable=False,
            )
        self._require_collection(identity.collection)
        if (
            not identity.item
            or len(identity.item) > 512
            or any(ord(char) < 0x20 for char in identity.item)
        ):
            raise CatalogueProviderError(
                "INVALID_ITEM_ID", "The provider item identifier is invalid.", retryable=False
            )

        collection_map = {item.id: item for item in await self.collections()}
        checked_at = self._utc_now()
        try:
            raw = await self._item_payload(identity.collection, identity.item)
        except CatalogueProviderError as error:
            if error.upstream_status == 404:
                return ResolvedImagerySourceSet(
                    resolution=self._resolution_failure(
                        request,
                        None,
                        checked_at,
                        "unavailable_asset",
                        "The selected catalogue scene is no longer available from the provider.",
                    ),
                    sources=(),
                )
            raise
        scene = self._normalize_item(raw, collection_map, retrieved_at=checked_at)
        if scene.provider_asset_id != identity.item or scene.collection.id != identity.collection:
            raise self._invalid_response("Earth Search returned a different catalogue item.")

        candidates = self._rgb_candidates(raw)
        missing = [role for role in ("red", "green", "blue") if role not in candidates]
        if missing:
            return ResolvedImagerySourceSet(
                resolution=self._resolution_failure(
                    request,
                    scene,
                    checked_at,
                    "unavailable_asset",
                    (
                        "Current provider metadata does not identify data assets for: "
                        f"{', '.join(missing)}."
                    ),
                ),
                sources=(),
            )

        ordered = [candidates[role] for role in ("red", "green", "blue")]
        expired = next(
            (
                candidate
                for candidate in ordered
                if candidate.expires_at is not None and candidate.expires_at <= checked_at
            ),
            None,
        )
        if expired is not None:
            return ResolvedImagerySourceSet(
                resolution=self._resolution_failure(
                    request,
                    scene,
                    checked_at,
                    "unavailable_asset",
                    f"The {expired.common_name} asset reference has expired.",
                    asset_access_state="expired",
                    expires_at=expired.expires_at,
                ),
                sources=(),
            )
        if any(not self._is_supported_cog(candidate.media_type) for candidate in ordered):
            return ResolvedImagerySourceSet(
                resolution=self._resolution_failure(
                    request,
                    scene,
                    checked_at,
                    "unsupported_format",
                    (
                        "At least one required RGB asset is not advertised as a Cloud "
                        "Optimized GeoTIFF."
                    ),
                ),
                sources=(),
            )
        if any(
            candidate.crs is None
            or candidate.resolution_metres is None
            or candidate.shape is None
            or candidate.transform is None
            for candidate in ordered
        ):
            return ResolvedImagerySourceSet(
                resolution=self._resolution_failure(
                    request,
                    scene,
                    checked_at,
                    "unavailable_asset",
                    (
                        "Required per-band CRS, resolution, shape, or transform metadata "
                        "is unavailable."
                    ),
                ),
                sources=(),
            )

        components: list[ResolvedRasterComponent] = []
        validated_candidates: list[_RasterCandidate] = []
        for candidate in ordered:
            access_state, content_length, validated_location = await self._check_raster_access(
                candidate
            )
            if access_state == "credentials_required":
                return ResolvedImagerySourceSet(
                    resolution=self._resolution_failure(
                        request,
                        scene,
                        checked_at,
                        "access_credentials_required",
                        f"The {candidate.common_name} asset requires provider access credentials.",
                    ),
                    sources=(),
                )
            if access_state == "unsupported_format":
                return ResolvedImagerySourceSet(
                    resolution=self._resolution_failure(
                        request,
                        scene,
                        checked_at,
                        "unsupported_format",
                        f"The {candidate.common_name} asset header reports an unsupported format.",
                    ),
                    sources=(),
                )
            if access_state != "accessible":
                return ResolvedImagerySourceSet(
                    resolution=self._resolution_failure(
                        request,
                        scene,
                        checked_at,
                        "unavailable_asset",
                        f"The {candidate.common_name} asset did not pass the bounded access check.",
                    ),
                    sources=(),
                )
            assert validated_location is not None
            validated_candidates.append(replace(candidate, href=validated_location))
            components.append(
                ResolvedRasterComponent(
                    identity=ResolvedImageryAssetIdentity(
                        scene=identity,
                        asset=candidate.asset_id,
                        asset_version=candidate.asset_version,
                    ),
                    render_role=candidate.common_name,
                    band_name=candidate.band_name,
                    common_name=candidate.common_name,
                    band_index=1,
                    media_type="image/tiff",
                    scale=candidate.scale,
                    offset=candidate.offset,
                    nodata=candidate.nodata,
                    crs=cast(str, candidate.crs),
                    resolution_metres=cast(float, candidate.resolution_metres),
                    shape=candidate.shape,
                    transform=candidate.transform,
                    access_check="head_succeeded",
                    content_length_bytes=content_length,
                )
            )

        component_ids = [component.identity.asset for component in components]
        group_digest = hashlib.sha256(
            json.dumps(component_ids, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:24]
        resolved = ResolvedImageryAsset(
            identity=ResolvedImageryAssetIdentity(
                scene=identity,
                asset=f"rgb-{group_digest}",
                asset_version=scene.provider_asset_version,
            ),
            acquisition=scene.acquisition,
            media_type="image/tiff",
            bounds=scene.bbox,
            render_presets=[
                SupportedRenderPreset(
                    id="natural-color",
                    title="Natural colour",
                    description=(
                        "Provider reflectance red, green, and blue bands for visualization."
                    ),
                    mode="rgb",
                    bands=component_ids,
                )
            ],
            default_render_preset="natural-color",
            catalogue_availability=CatalogueAvailability(state="available"),
            asset_accessibility=AssetAccessibility(state="accessible", method="backend_mediated"),
            analysis_readiness=AnalysisReadiness(
                state="not_assessed",
                reason="Visualization resolution does not perform analytical intake or validation.",
            ),
            attributions=[EARTH_SEARCH_ATTRIBUTION],
            resolved_at=checked_at,
        )
        resolution = AssetResolutionResponse(
            scene=identity,
            status=AssetResolutionStatus(state="supported"),
            catalogue_availability=resolved.catalogue_availability,
            asset_accessibility=resolved.asset_accessibility,
            render_status=RenderStatus(state="not_requested"),
            analysis_readiness=resolved.analysis_readiness,
            resolved_asset=resolved,
            components=components,
            thumbnail=scene.preview,
            license=scene.license,
            attributions=[EARTH_SEARCH_ATTRIBUTION],
            checked_at=checked_at,
        )
        return ResolvedImagerySourceSet(
            resolution=resolution,
            sources=tuple(
                ResolvedRasterSource(
                    component=component,
                    location=candidate.href,
                    expires_at=candidate.expires_at,
                )
                for component, candidate in zip(components, validated_candidates, strict=True)
            ),
        )

    async def _item_payload(self, collection_id: str, item_id: str) -> dict[str, Any]:
        cache_key = f"item-record:{collection_id}:{item_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cast(dict[str, Any], cached)
        payload = await self._request_json(
            "GET",
            f"collections/{quote(collection_id, safe='')}/items/{quote(item_id, safe='')}",
        )
        self._cache.put(cache_key, payload)
        return payload

    def _rgb_candidates(
        self, raw: dict[str, Any]
    ) -> dict[Literal["red", "green", "blue"], _RasterCandidate]:
        properties = self._mapping(raw.get("properties"))
        candidates: dict[Literal["red", "green", "blue"], _RasterCandidate] = {}
        for asset_id in sorted(self._assets(raw)):
            asset = self._mapping(self._assets(raw).get(asset_id))
            if (
                not asset
                or not asset_id
                or len(asset_id) > 512
                or any(ord(char) < 0x20 or ord(char) == 0x7F for char in asset_id)
            ):
                continue
            roles = set(self._string_list(asset.get("roles")))
            if "data" not in roles or not roles.issubset({"data", "reflectance"}):
                continue
            eo_bands = [
                self._mapping(value)
                for value in self._list(asset.get("eo:bands"))
                if isinstance(value, Mapping)
            ]
            if len(eo_bands) != 1:
                continue
            common_name = self._optional_string(eo_bands[0].get("common_name"))
            if common_name not in {"red", "green", "blue"} or common_name in candidates:
                continue
            typed_common_name = cast(Literal["red", "green", "blue"], common_name)
            band_name = self._optional_string(eo_bands[0].get("name"))
            href = self._optional_string(asset.get("href"))
            media_type = self._optional_string(asset.get("type"))
            if band_name is None or href is None or media_type is None:
                continue
            raster_bands = [
                self._mapping(value)
                for value in self._list(asset.get("raster:bands"))
                if isinstance(value, Mapping)
            ]
            raster_band = raster_bands[0] if len(raster_bands) == 1 else {}
            candidate = _RasterCandidate(
                asset_id=asset_id,
                href=href,
                band_name=band_name,
                common_name=typed_common_name,
                media_type=media_type,
                asset_version=self._optional_string(
                    asset.get("file:checksum") or asset.get("checksum:multihash")
                ),
                scale=self._optional_finite_number(raster_band.get("scale")),
                offset=self._optional_finite_number(raster_band.get("offset")),
                nodata=self._nodata(raster_band.get("nodata")),
                crs=self._projection_code(asset, properties),
                resolution_metres=self._positive_number(
                    asset.get("gsd") or raster_band.get("spatial_resolution")
                ),
                shape=self._raster_shape(asset.get("proj:shape") or properties.get("proj:shape")),
                transform=self._raster_transform(
                    asset.get("proj:transform") or properties.get("proj:transform")
                ),
                expires_at=self._asset_expiry(asset),
            )
            candidates[typed_common_name] = candidate
        return candidates

    async def _check_raster_access(
        self, candidate: _RasterCandidate
    ) -> tuple[
        Literal["accessible", "credentials_required", "unsupported_format", "unavailable"],
        int | None,
        str | None,
    ]:
        url = self._approved_raster_url(candidate.href)
        for _redirect in range(3):
            try:
                response = await self._client.request(
                    "HEAD",
                    url,
                    timeout=self._timeout_seconds,
                    follow_redirects=False,
                    headers={"Accept": "image/tiff", "Accept-Encoding": "identity"},
                )
            except (httpx2.TimeoutException, httpx2.RequestError):
                return "unavailable", None, None
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if location is None:
                    return "unavailable", None, None
                url = self._approved_raster_url(urljoin(url, location))
                continue
            if response.status_code in {401, 403}:
                return "credentials_required", None, None
            if response.status_code < 200 or response.status_code >= 300:
                return "unavailable", None, None
            header_media_type = response.headers.get("content-type")
            if (
                header_media_type
                and header_media_type.split(";", 1)[0].strip().lower() != "image/tiff"
            ):
                return "unsupported_format", None, None
            content_length = self._content_length(response.headers.get("content-length"))
            return "accessible", content_length, url
        return "unavailable", None, None

    @staticmethod
    def _is_supported_cog(value: str) -> bool:
        parameters = {part.strip().lower() for part in value.split(";")}
        return "image/tiff" in parameters and {
            "application=geotiff",
            "profile=cloud-optimized",
        }.issubset(parameters)

    @staticmethod
    def _content_length(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed >= 0 else None

    @staticmethod
    def _optional_finite_number(value: Any) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        return number if isfinite(number) else None

    @classmethod
    def _positive_number(cls, value: Any) -> float | None:
        number = cls._optional_finite_number(value)
        return number if number is not None and number > 0 else None

    @classmethod
    def _nodata(cls, value: Any) -> float | Literal["nan", "inf", "-inf"] | None:
        if isinstance(value, str) and value.lower() in {"nan", "inf", "-inf"}:
            return cast(Literal["nan", "inf", "-inf"], value.lower())
        return cls._optional_finite_number(value)

    @classmethod
    def _projection_code(cls, asset: dict[str, Any], properties: dict[str, Any]) -> str | None:
        code = cls._optional_string(asset.get("proj:code")) or cls._optional_string(
            properties.get("proj:code")
        )
        if code is not None:
            return code
        epsg = asset.get("proj:epsg") or properties.get("proj:epsg")
        if isinstance(epsg, int) and not isinstance(epsg, bool) and epsg > 0:
            return f"EPSG:{epsg}"
        return None

    @staticmethod
    def _raster_shape(value: Any) -> tuple[int, int] | None:
        if (
            not isinstance(value, list)
            or len(value) != 2
            or any(
                not isinstance(number, int) or isinstance(number, bool) or number <= 0
                for number in value
            )
        ):
            return None
        return value[0], value[1]

    @classmethod
    def _raster_transform(cls, value: Any) -> tuple[float, ...] | None:
        if not isinstance(value, list) or len(value) not in {6, 9}:
            return None
        numbers = tuple(cls._optional_finite_number(number) for number in value)
        if any(number is None for number in numbers):
            return None
        return cast(tuple[float, ...], numbers)

    @classmethod
    def _asset_expiry(cls, asset: dict[str, Any]) -> datetime | None:
        value = cls._optional_string(asset.get("expires") or asset.get("expires_at"))
        return cls._parse_datetime(value) if value is not None else None

    @staticmethod
    def _approved_raster_url(value: str) -> str:
        parsed = urlsplit(value)
        decoded_path = unquote(parsed.path)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in EARTH_SEARCH_RASTER_HOSTS
            or parsed.port not in {None, 443}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not decoded_path.startswith(f"/{EARTH_SEARCH_DEFAULT_COLLECTION}/")
            or ".." in decoded_path.split("/")
        ):
            raise EarthSearchCatalogueProvider._invalid_response(
                "Earth Search returned an unapproved raster location or redirect."
            )
        return value

    @staticmethod
    def _resolution_failure(
        request: AssetResolutionRequest,
        scene: CatalogueScene | None,
        checked_at: datetime,
        state: Literal["unsupported_format", "unavailable_asset", "access_credentials_required"],
        reason: str,
        *,
        asset_access_state: Literal["requires_authorization", "expired", "unavailable"]
        | None = None,
        expires_at: datetime | None = None,
    ) -> AssetResolutionResponse:
        catalogue_availability = CatalogueAvailability(
            state="available" if scene is not None else "unavailable",
            reason=None if scene is not None else "The current provider item was not found.",
        )
        access_state = asset_access_state or (
            "requires_authorization" if state == "access_credentials_required" else "unavailable"
        )
        return AssetResolutionResponse(
            scene=request.scene,
            status=AssetResolutionStatus(state=state, reason=reason),
            catalogue_availability=catalogue_availability,
            asset_accessibility=AssetAccessibility(
                state=access_state,
                method="none",
                reason=reason,
                expires_at=expires_at,
            ),
            render_status=RenderStatus(state="not_requested"),
            analysis_readiness=AnalysisReadiness(
                state="not_assessed",
                reason="Asset resolution does not perform analytical intake or validation.",
            ),
            thumbnail=scene.preview if scene is not None else None,
            license=scene.license if scene is not None else None,
            attributions=[EARTH_SEARCH_ATTRIBUTION],
            checked_at=checked_at,
        )

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = self._approved_url(path)
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(
                    method,
                    url,
                    json=json_body,
                    timeout=self._timeout_seconds,
                    follow_redirects=False,
                )
            except (httpx2.TimeoutException, httpx2.RequestError) as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                await self._sleeper(self._backoff_delay(attempt))
                continue
            if response.status_code in _TRANSIENT_STATUSES and attempt < self._max_retries:
                await self._sleeper(self._retry_delay(response, attempt))
                continue
            if response.status_code >= 400:
                if response.status_code == 429:
                    code = "PROVIDER_RATE_LIMITED"
                elif response.status_code in {408, 504}:
                    code = "PROVIDER_TIMEOUT"
                elif response.status_code >= 500:
                    code = "PROVIDER_UNAVAILABLE"
                else:
                    code = "PROVIDER_REQUEST_FAILED"
                raise CatalogueProviderError(
                    code,
                    f"Earth Search returned HTTP {response.status_code}.",
                    retryable=response.status_code in _TRANSIENT_STATUSES,
                    upstream_status=response.status_code,
                    retry_after_seconds=self._retry_after_seconds(response),
                )
            content_type = response.headers.get("content-type", "").lower()
            media_type = content_type.split(";", maxsplit=1)[0].strip()
            if media_type != "application/json" and not (
                media_type.startswith("application/") and media_type.endswith("+json")
            ):
                raise self._invalid_response("Earth Search returned a non-JSON metadata response.")
            if len(response.content) > _MAX_METADATA_BYTES:
                raise self._invalid_response("Earth Search metadata exceeded the response limit.")
            try:
                parsed = response.json()
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
                raise self._invalid_response(
                    "Earth Search returned invalid JSON metadata."
                ) from exc
            if not isinstance(parsed, dict):
                raise self._invalid_response("Earth Search returned an invalid metadata object.")
            return cast(dict[str, Any], parsed)
        if isinstance(last_error, httpx2.TimeoutException):
            raise CatalogueProviderError(
                "PROVIDER_TIMEOUT",
                "Earth Search timed out after bounded retries.",
                retryable=True,
            ) from last_error
        raise CatalogueProviderError(
            "PROVIDER_UNAVAILABLE",
            "Earth Search could not be reached after bounded retries.",
            retryable=True,
        ) from last_error

    def _approved_url(self, path: str) -> str:
        if path.startswith(("/", "http:")) or path.startswith("https:") or ".." in path:
            raise ValueError("Provider request path must be relative and bounded")
        return f"{self._base_url}{path}"

    def _retry_delay(self, response: httpx2.Response, attempt: int) -> float:
        retry_after = response.headers.get("retry-after")
        if retry_after is not None:
            try:
                delay = float(str(retry_after))
                return float(min(max(delay, 0.0), 2.0))
            except ValueError:
                pass
        return self._backoff_delay(attempt)

    @staticmethod
    def _retry_after_seconds(response: httpx2.Response) -> int | None:
        retry_after = response.headers.get("retry-after")
        if retry_after is None:
            return None
        try:
            return min(max(int(float(retry_after)), 0), 120)
        except ValueError:
            return None

    def _backoff_delay(self, attempt: int) -> float:
        base = (0.25, 0.5, 1.0, 2.0)[min(attempt, 3)]
        return min(base + self._jitter(0.0, base * 0.25), 2.0)

    def _normalize_collection(self, raw: dict[str, Any]) -> CatalogueCollection:
        collection_id = self._required_string(raw, "id", "collection")
        self._require_collection(collection_id)
        summaries = self._mapping(raw.get("summaries"))
        extent = self._mapping(raw.get("extent"))
        temporal = self._mapping(extent.get("temporal"))
        interval = temporal.get("interval")
        temporal_start: str | None = None
        temporal_end: str | None = None
        if isinstance(interval, list) and interval and isinstance(interval[0], list):
            temporal_start = self._optional_string(interval[0][0] if interval[0] else None)
            temporal_end = self._optional_string(interval[0][1] if len(interval[0]) > 1 else None)
        license_url = self._link_href(raw, "license")
        gsd_values = tuple(
            sorted(
                {
                    float(value)
                    for value in self._list(summaries.get("gsd"))
                    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
                }
            )
        )[:3]
        return CatalogueCollection(
            id=collection_id,
            title=self._optional_string(raw.get("title")),
            description=self._optional_string(raw.get("description")),
            license_name=self._optional_string(raw.get("license")),
            license_url=license_url,
            temporal_start=temporal_start,
            temporal_end=temporal_end,
            platforms=tuple(self._string_list(summaries.get("platform"))),
            instruments=tuple(self._string_list(summaries.get("instruments"))),
            spatial_resolutions_metres=gsd_values,
        )

    def _normalize_item(
        self,
        raw: dict[str, Any],
        collections: dict[str, CatalogueCollection],
        *,
        retrieved_at: datetime,
    ) -> CatalogueScene:
        item_id = self._required_string(raw, "id", "item")
        collection_id = self._required_string(raw, "collection", "item")
        self._require_collection(collection_id)
        collection = collections.get(collection_id)
        if collection is None:
            raise self._invalid_response("Earth Search returned an undiscovered collection.")
        properties = self._mapping(raw.get("properties"))
        start, end, acquisition_fields = self._acquisition(properties)
        try:
            footprint = _GEOMETRY_ADAPTER.validate_python(raw.get("geometry"))
        except ValidationError as exc:
            raise self._invalid_response("Earth Search returned invalid item geometry.") from exc
        bbox = self._geometry_bbox(footprint)
        platform = self._optional_string(properties.get("platform"))
        instruments = self._string_list(properties.get("instruments"))
        cloud = self._cloud_cover(properties)
        resolutions = self._spatial_resolutions(raw, collection)
        bands = self._bands(raw)
        preview = self._preview(raw)
        license_metadata = self._license(collection)
        asset_access = self._asset_access(raw)
        fields = [
            FieldProvenance(
                normalized_field="provider_asset_id",
                source="provider_record",
                source_field="id",
            ),
            FieldProvenance(
                normalized_field="collection.id",
                source="provider_record",
                source_field="collection",
            ),
            FieldProvenance(
                normalized_field="acquisition.start",
                source="provider_record",
                source_field=acquisition_fields[0],
            ),
            FieldProvenance(
                normalized_field="acquisition.end",
                source="provider_record",
                source_field=acquisition_fields[1],
            ),
            FieldProvenance(
                normalized_field="footprint",
                source="provider_record",
                source_field="geometry",
            ),
            FieldProvenance(
                normalized_field="bbox",
                source="adapter_derived",
                source_field="geometry",
                method="Minimum WGS84 bounds computed from the validated footprint.",
            ),
            FieldProvenance(
                normalized_field="asset_access",
                source="adapter_derived",
                source_field="assets[*].roles",
                method="Classified from advertised metadata only; no asset bytes were requested.",
            ),
        ]
        optional_provenance: list[tuple[bool, str, str]] = [
            (platform is not None, "platform", "properties.platform"),
            (bool(instruments), "instruments", "properties.instruments"),
            (cloud is not None, "cloud_cover", "properties.eo:cloud_cover"),
            (
                bool(resolutions),
                "spatial_resolution",
                resolutions[0].source_field if resolutions else "assets[*].gsd",
            ),
            (bool(bands), "bands", "assets[*].eo:bands"),
            (
                preview is not None,
                "preview",
                f"assets.{preview.purpose}" if preview is not None else "assets.thumbnail",
            ),
            (license_metadata is not None, "license", "collection.license"),
        ]
        fields.extend(
            FieldProvenance(normalized_field=field, source="provider_record", source_field=source)
            for present, field, source in optional_provenance
            if present
        )
        unavailable = [
            FieldAvailability(field=field, reason=reason)
            for field, value, reason in (
                ("provider_asset_version", None, "Earth Search did not report an asset version."),
                ("product_type", None, "Earth Search did not report a product type."),
                ("processing_level", None, "Earth Search did not report a processing level."),
                ("platform", platform, "Earth Search did not report a platform."),
                ("instruments", instruments, "Earth Search did not report instruments."),
                ("cloud_cover", cloud, "Earth Search did not report cloud cover."),
                (
                    "spatial_resolution",
                    resolutions,
                    "Earth Search did not report spatial resolution.",
                ),
                ("bands", bands, "Earth Search did not report spectral bands."),
                ("polarizations", [], "This optical collection does not report SAR polarizations."),
                ("preview", preview, "Earth Search did not advertise an approved public preview."),
                ("license", license_metadata, "Earth Search did not report collection licensing."),
            )
            if not value
        ]
        digest = hashlib.sha256(
            json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest()
        return CatalogueScene(
            provider=self._provider_identity(),
            provider_asset_id=item_id,
            provider_asset_version=None,
            collection=CollectionIdentity(id=collection_id, title=collection.title),
            acquisition=AcquisitionInterval(start=start, end=end),
            platform=platform,
            instruments=instruments,
            product_type=None,
            processing_level=None,
            footprint=footprint,
            bbox=bbox,
            cloud_cover=cloud,
            spatial_resolution=resolutions,
            bands=bands,
            polarizations=[],
            preview=preview,
            license=license_metadata,
            asset_access=asset_access,
            provenance=CatalogueProvenance(
                adapter="earth-search-stac",
                adapter_version=EARTH_SEARCH_ADAPTER_VERSION,
                retrieved_at=retrieved_at,
                source_record_id=item_id,
                source_record_version=None,
                metadata_digest_sha256=digest,
                fields=fields,
            ),
            unavailable_fields=unavailable,
        )

    @staticmethod
    def _provider_identity() -> ProviderIdentity:
        return ProviderIdentity(id=EARTH_SEARCH_PROVIDER_ID, name=EARTH_SEARCH_PROVIDER_NAME)

    def _resolve_collections(self, requested: list[str]) -> list[str]:
        resolved = requested or [EARTH_SEARCH_DEFAULT_COLLECTION]
        for collection_id in resolved:
            self._require_collection(collection_id)
        return resolved

    @staticmethod
    def _require_collection(collection_id: str) -> None:
        if collection_id not in EARTH_SEARCH_ALLOWED_COLLECTIONS:
            raise CatalogueProviderError(
                "UNSUPPORTED_COLLECTION",
                "The requested collection is not enabled for this provider.",
                retryable=False,
            )

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

    def _search_body(
        self,
        request: CatalogueSearchRequest,
        collections: list[str],
        continuation: str | None,
    ) -> dict[str, Any]:
        direction = "desc" if request.sort == "acquired_desc" else "asc"
        body: dict[str, Any] = {
            "collections": collections,
            "intersects": request.aoi.model_dump(mode="json"),
            "datetime": (
                f"{self._format_datetime(request.acquisition.start)}/"
                f"{self._format_datetime(request.acquisition.end)}"
            ),
            "sortby": [
                {"field": "properties.datetime", "direction": direction},
                {"field": "id", "direction": "asc"},
            ],
            "limit": request.limit,
        }
        if request.cloud_cover is not None:
            body["query"] = {"eo:cloud_cover": {"lte": request.cloud_cover.max_percent}}
        if continuation is not None:
            body["next"] = continuation
        return body

    @staticmethod
    def _request_signature(request: CatalogueSearchRequest, collections: list[str]) -> str:
        value = request.model_dump(mode="json", exclude={"cursor"})
        value["collections"] = collections
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _next_cursor(self, payload: dict[str, Any], signature: str) -> str | None:
        links = payload.get("links")
        if not isinstance(links, list):
            return None
        next_links = [
            link for link in links if isinstance(link, Mapping) and link.get("rel") == "next"
        ]
        if not next_links:
            return None
        link = self._mapping(next_links[0])
        href = self._required_string(link, "href", "next link")
        parsed = urlsplit(href)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "earth-search.aws.element84.com"
            or parsed.port is not None
            or parsed.username
            or parsed.password
            or parsed.path.rstrip("/") != "/v1/search"
            or parsed.query
            or parsed.fragment
            or str(link.get("method", "")).upper() != "POST"
        ):
            raise self._invalid_response("Earth Search returned an unapproved pagination link.")
        body = self._mapping(link.get("body"))
        token = self._optional_string(body.get("next"))
        if (
            token is None
            or len(token) > _MAX_PROVIDER_TOKEN_LENGTH
            or any(ord(char) < 0x20 or ord(char) == 0x7F for char in token)
        ):
            raise self._invalid_response("Earth Search returned an invalid pagination token.")
        cursor_payload = json.dumps(
            {"v": 1, "provider": EARTH_SEARCH_PROVIDER_ID, "query": signature, "next": token},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(cursor_payload).decode().rstrip("=")

    def _decode_cursor(self, cursor: str, signature: str) -> str:
        try:
            padding = "=" * (-len(cursor) % 4)
            decoded = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
            payload = json.loads(decoded)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CatalogueProviderError(
                "INVALID_CURSOR", "The catalogue cursor is invalid.", retryable=False
            ) from exc
        if (
            not isinstance(payload, dict)
            or payload.get("v") != 1
            or payload.get("provider") != EARTH_SEARCH_PROVIDER_ID
            or payload.get("query") != signature
        ):
            raise CatalogueProviderError(
                "INVALID_CURSOR",
                "The catalogue cursor does not match this search.",
                retryable=False,
            )
        token = payload.get("next")
        if (
            not isinstance(token, str)
            or not token
            or len(token) > _MAX_PROVIDER_TOKEN_LENGTH
            or any(ord(char) < 0x20 or ord(char) == 0x7F for char in token)
        ):
            raise CatalogueProviderError(
                "INVALID_CURSOR", "The catalogue cursor is invalid.", retryable=False
            )
        return token

    @staticmethod
    def _acquisition(properties: dict[str, Any]) -> tuple[datetime, datetime, tuple[str, str]]:
        instant = EarthSearchCatalogueProvider._optional_string(properties.get("datetime"))
        if instant is not None:
            parsed = EarthSearchCatalogueProvider._parse_datetime(instant)
            return parsed, parsed, ("properties.datetime", "properties.datetime")
        start_value = EarthSearchCatalogueProvider._optional_string(
            properties.get("start_datetime")
        )
        end_value = EarthSearchCatalogueProvider._optional_string(properties.get("end_datetime"))
        if start_value is None or end_value is None:
            raise EarthSearchCatalogueProvider._invalid_response(
                "Earth Search did not report an acquisition time."
            )
        return (
            EarthSearchCatalogueProvider._parse_datetime(start_value),
            EarthSearchCatalogueProvider._parse_datetime(end_value),
            ("properties.start_datetime", "properties.end_datetime"),
        )

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise EarthSearchCatalogueProvider._invalid_response(
                "Earth Search returned an invalid acquisition time."
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise EarthSearchCatalogueProvider._invalid_response(
                "Earth Search returned an acquisition time without an offset."
            )
        return parsed.astimezone(UTC)

    @staticmethod
    def _geometry_bbox(geometry: CatalogGeometry) -> tuple[float, float, float, float]:
        polygons = [geometry.coordinates] if geometry.type == "Polygon" else geometry.coordinates
        positions = [position for polygon in polygons for ring in polygon for position in ring]
        longitudes = [position[0] for position in positions]
        latitudes = [position[1] for position in positions]
        return min(longitudes), min(latitudes), max(longitudes), max(latitudes)

    @staticmethod
    def _cloud_cover(properties: dict[str, Any]) -> CloudCoverMetadata | None:
        value = properties.get("eo:cloud_cover")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        if not 0 <= value <= 100:
            raise EarthSearchCatalogueProvider._invalid_response(
                "Earth Search returned cloud cover outside 0 to 100 percent."
            )
        return CloudCoverMetadata(
            percent=float(value),
            source_field="properties.eo:cloud_cover",
            semantics="Provider-reported percentage of the item covered by clouds.",
        )

    @staticmethod
    def _assets(raw: dict[str, Any]) -> dict[str, Any]:
        return EarthSearchCatalogueProvider._mapping(raw.get("assets"))

    def _spatial_resolutions(
        self, raw: dict[str, Any], collection: CatalogueCollection
    ) -> list[SpatialResolution]:
        values: set[float] = set()
        for asset in self._assets(raw).values():
            if not isinstance(asset, Mapping):
                continue
            gsd = asset.get("gsd")
            if isinstance(gsd, (int, float)) and not isinstance(gsd, bool) and gsd > 0:
                values.add(float(gsd))
        source = "assets[*].gsd"
        if not values:
            values.update(collection.spatial_resolutions_metres)
            source = "collection.summaries.gsd"
        return [SpatialResolution(value=value, source_field=source) for value in sorted(values)[:3]]

    def _bands(self, raw: dict[str, Any]) -> list[str]:
        values: list[str] = []
        for asset in self._assets(raw).values():
            if not isinstance(asset, Mapping):
                continue
            bands = asset.get("eo:bands")
            if not isinstance(bands, list):
                continue
            for band in bands:
                if not isinstance(band, Mapping):
                    continue
                label = self._optional_string(band.get("common_name")) or self._optional_string(
                    band.get("name")
                )
                if label is not None and label not in values:
                    values.append(label)
        return values

    def _preview(self, raw: dict[str, Any]) -> CataloguePreview | None:
        assets = self._assets(raw)
        candidates: list[tuple[str, Literal["thumbnail", "preview"]]] = []
        for key in sorted(assets):
            asset = self._mapping(assets.get(key))
            roles = set(self._string_list(asset.get("roles")))
            if key == "thumbnail" or "thumbnail" in roles:
                candidates.append((key, "thumbnail"))
            elif key == "preview" or roles.intersection({"overview", "preview"}):
                candidates.append((key, "preview"))
        candidates.sort(key=lambda candidate: (candidate[1] != "thumbnail", candidate[0]))
        for key, purpose in candidates:
            raw_asset = assets.get(key)
            if not isinstance(raw_asset, Mapping):
                continue
            href = self._optional_string(raw_asset.get("href"))
            if href is None:
                continue
            parsed = urlsplit(href)
            if (
                parsed.scheme != "https"
                or parsed.hostname not in EARTH_SEARCH_PREVIEW_HOSTS
                or parsed.username
                or parsed.password
            ):
                continue
            media_type = self._optional_string(raw_asset.get("type"))
            width = raw_asset.get("proj:shape", [None, None])
            width_value = width[1] if isinstance(width, list) and len(width) == 2 else None
            height_value = width[0] if isinstance(width, list) and len(width) == 2 else None
            return CataloguePreview(
                purpose=purpose,
                access="public",
                href=href,
                media_type=media_type,
                width=width_value if isinstance(width_value, int) else None,
                height=height_value if isinstance(height_value, int) else None,
                attribution=EARTH_SEARCH_ATTRIBUTION,
            )
        return None

    @staticmethod
    def _license(collection: CatalogueCollection) -> CatalogueLicense | None:
        if collection.license_name is None:
            return None
        return CatalogueLicense(
            name=collection.license_name,
            url=collection.license_url,
            permits_analytical_use=None,
            summary="Access and use remain subject to the provider-linked collection terms.",
        )

    def _asset_access(self, raw: dict[str, Any]) -> AssetAccess:
        for asset in self._assets(raw).values():
            if not isinstance(asset, Mapping):
                continue
            roles = self._string_list(asset.get("roles"))
            href = self._optional_string(asset.get("href"))
            if "data" in roles and href is not None and urlsplit(href).scheme == "https":
                return AssetAccess(
                    state="provider_accessible",
                    method="provider_reference",
                    reason=(
                        "Earth Search advertises a data asset reference; the adapter fetched only "
                        "metadata and did not download or validate raster bytes."
                    ),
                )
        return AssetAccess(
            state="unknown",
            method="none",
            reason="Earth Search did not advertise a usable data asset reference.",
        )

    @staticmethod
    def _link_href(raw: dict[str, Any], rel: str) -> str | None:
        links = raw.get("links")
        if not isinstance(links, list):
            return None
        for link in links:
            if not isinstance(link, Mapping) or link.get("rel") != rel:
                continue
            href = EarthSearchCatalogueProvider._optional_string(link.get("href"))
            if href is None:
                continue
            parsed = urlsplit(href)
            if parsed.scheme == "https" and not parsed.username and not parsed.password:
                return href
        return None

    def _utc_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise RuntimeError("provider clock must return an offset-aware datetime")
        return value.astimezone(UTC)

    @staticmethod
    def _mapping(value: object) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            return {}
        return {str(key): item for key, item in value.items()}

    @staticmethod
    def _list(value: object) -> list[Any]:
        return value if isinstance(value, list) else []

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item]

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _required_string(raw: dict[str, Any], key: str, context: str) -> str:
        value = EarthSearchCatalogueProvider._optional_string(raw.get(key))
        if value is None:
            raise EarthSearchCatalogueProvider._invalid_response(
                f"Earth Search {context} is missing {key}."
            )
        return value

    @staticmethod
    def _invalid_response(message: str) -> CatalogueProviderError:
        return CatalogueProviderError("INVALID_PROVIDER_RESPONSE", message, retryable=False)
