"""Real satellite provider adapter connecting to STAC catalogues (Element 84)."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import httpx2
from pydantic import ValidationError

from satquery.api.schemas.analysis import (
    AnalysisWarning,
    AOIGeometry,
    GeometryType,
    SatelliteScene,
    SensorType,
    WarningCode,
    WarningSeverity,
)
from satquery.api.schemas.providers import (
    DataOrigin,
    ProviderCapability,
    ProviderExecutionMetadata,
    ProviderInfo,
    ProviderMode,
    ProviderStatus,
)
from satquery.core.config import Settings
from satquery.core.logging import get_logger
from satquery.providers.satellite.base import (
    InvalidProviderResponseError,
    ProviderAuthenticationError,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    SatelliteProvider,
    SatelliteProviderError,
    SceneNotFoundError,
    SceneSearchRequest,
    SceneSearchResponse,
)

logger = get_logger(__name__)

EARTH_SEARCH_DEFAULT_BASE_URL = "https://earth-search.aws.element84.com/v1/"
EARTH_SEARCH_DEFAULT_COLLECTION = "sentinel-2-c1-l2a"
EARTH_SEARCH_ALLOWED_COLLECTIONS = frozenset({"sentinel-2-c1-l2a", "sentinel-2-l2a"})
EARTH_SEARCH_ALLOWED_PREVIEW_HOSTS = frozenset(
    {
        "e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com",
        "earth-search.aws.element84.com",
        "sentinel-cogs.s3.us-west-2.amazonaws.com",
    }
)
S2_KNOWN_BANDS = [
    "B01",
    "B02",
    "B03",
    "B04",
    "B05",
    "B06",
    "B07",
    "B08",
    "B8A",
    "B09",
    "B11",
    "B12",
    "AOT",
    "WVP",
    "SCL",
]
TRANSIENT_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


class _LRUSearchCache:
    """Bounded in-memory cache for search responses."""

    def __init__(self, capacity: int = 64, ttl_seconds: float = 300.0) -> None:
        self._capacity = capacity
        self._ttl_seconds = ttl_seconds
        self._entries: OrderedDict[str, tuple[float, SceneSearchResponse]] = OrderedDict()

    def get(self, key: str) -> SceneSearchResponse | None:
        if key not in self._entries:
            return None
        expires_at, response = self._entries[key]
        if time.time() > expires_at:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return response

    def put(self, key: str, response: SceneSearchResponse) -> None:
        if key in self._entries:
            del self._entries[key]
        elif len(self._entries) >= self._capacity:
            self._entries.popitem(last=False)
        self._entries[key] = (time.time() + self._ttl_seconds, response)


class RealSatelliteProviderAdapter(SatelliteProvider):
    """Production adapter for STAC satellite catalogues (e.g. Element 84 Earth Search)."""

    def __init__(
        self,
        *,
        provider_id: str = "earth-search",
        display_name: str = "AWS Earth Search Sentinel-2 L2A",
        base_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
        client: httpx2.AsyncClient | None = None,
        enable_cache: bool = True,
    ) -> None:
        self._provider_id = provider_id
        self._display_name = display_name
        self._base_url = (base_url or EARTH_SEARCH_DEFAULT_BASE_URL).rstrip("/") + "/"
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._client = client
        self._owns_client = client is None
        self._cache = _LRUSearchCache() if enable_cache else None

    @classmethod
    def from_settings(
        cls, settings: Settings, client: httpx2.AsyncClient | None = None
    ) -> RealSatelliteProviderAdapter:
        return cls(
            provider_id=settings.catalogue_provider,
            display_name=f"Real Satellite Provider ({settings.catalogue_provider})",
            base_url=str(settings.satellite_base_url or settings.earth_search_base_url),
            client_id=settings.satellite_client_id,
            client_secret=(
                settings.satellite_client_secret.get_secret_value()
                if settings.satellite_client_secret
                else None
            ),
            timeout_seconds=settings.satellite_timeout_seconds,
            max_retries=settings.satellite_max_retries,
            client=client,
        )

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def mode(self) -> ProviderMode:
        return ProviderMode.REAL

    @property
    def capabilities(self) -> list[ProviderCapability]:
        return [
            ProviderCapability.SCENE_SEARCH,
            ProviderCapability.SCENE_METADATA,
            ProviderCapability.SCENE_PREVIEW,
            ProviderCapability.OPTICAL_IMAGERY,
            ProviderCapability.SPECTRAL_PROCESSING,
            ProviderCapability.CHANGE_DETECTION,
        ]

    def is_configured(self) -> bool:
        if self.provider_id == "earth-search":
            return bool(self._base_url)
        return bool(self._client_id and self._client_secret)

    async def _get_client(self) -> httpx2.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx2.AsyncClient(
                timeout=httpx2.Timeout(self._timeout_seconds),
                limits=httpx2.Limits(max_connections=10, max_keepalive_connections=5),
            )
            self._owns_client = True
        return self._client

    async def health_check(self) -> ProviderInfo:
        configured = self.is_configured()
        status = ProviderStatus.READY if configured else ProviderStatus.NOT_CONFIGURED
        message = (
            f"Provider '{self.provider_id}' is configured and ready."
            if configured
            else f"Provider '{self.provider_id}' requires credentials which are not configured."
        )

        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            provider_type="satellite",
            mode=self.mode,
            status=status,
            capabilities=self.capabilities,
            configured=configured,
            healthy=configured,
            data_origin=DataOrigin.REAL,
            last_checked_at=datetime.now(UTC),
            message=message,
            limitations=[
                "External provider rate limits apply",
                "Metadata-only STAC discovery",
                "Requires live Internet access",
            ],
            metadata={"base_url": self._base_url},
        )

    def _build_search_body(
        self, request: SceneSearchRequest, pagination_token: str | None = None
    ) -> dict[str, Any]:
        # Validate collection
        collections = (
            request.collections if request.collections else [EARTH_SEARCH_DEFAULT_COLLECTION]
        )
        for col in collections:
            if col not in EARTH_SEARCH_ALLOWED_COLLECTIONS and self.provider_id == "earth-search":
                raise SatelliteProviderError(
                    "UNSUPPORTED_COLLECTION",
                    f"Collection '{col}' is not supported by provider '{self.provider_id}'. "
                    f"Supported collections: {sorted(EARTH_SEARCH_ALLOWED_COLLECTIONS)}",
                    status_code=400,
                )

        # Convert AOI geometry
        geometry_dict: dict[str, Any]
        if request.aoi.type == GeometryType.POLYGON:
            geometry_dict = {"type": "Polygon", "coordinates": request.aoi.coordinates}
        elif request.aoi.type == GeometryType.MULTI_POLYGON:
            geometry_dict = {"type": "MultiPolygon", "coordinates": request.aoi.coordinates}
        else:
            raise SatelliteProviderError(
                "UNSUPPORTED_GEOMETRY",
                f"Geometry type '{request.aoi.type}' is not supported for catalogue search.",
                status_code=400,
            )

        body: dict[str, Any] = {
            "collections": collections,
            "intersects": geometry_dict,
            "limit": min(request.limit, 100),
        }

        # Date range formatting
        if request.date_range:
            start_str = request.date_range.start_date
            end_str = request.date_range.end_date
            # Ensure full ISO format with Z
            if "T" not in start_str:
                start_str = f"{start_str}T00:00:00Z"
            elif not start_str.endswith("Z") and "+" not in start_str:
                start_str = f"{start_str}Z"

            if "T" not in end_str:
                end_str = f"{end_str}T23:59:59Z"
            elif not end_str.endswith("Z") and "+" not in end_str:
                end_str = f"{end_str}Z"

            body["datetime"] = f"{start_str}/{end_str}"

        # Cloud cover filter (only apply to optical sensors)
        is_optical = not request.sensor_types or any(
            st in {SensorType.MULTISPECTRAL, SensorType.OPTICAL} for st in request.sensor_types
        )
        if is_optical and request.max_cloud_cover < 100.0:
            body["query"] = {"eo:cloud_cover": {"lte": request.max_cloud_cover}}

        # Sort order
        sort_dir = "desc" if request.sort_order == "desc" else "asc"
        body["sortby"] = [{"field": "properties.datetime", "direction": sort_dir}]

        # Pagination token
        if pagination_token:
            body["token"] = pagination_token

        return body

    def _generate_cache_key(self, request: SceneSearchRequest) -> str:
        raw = json.dumps(
            {
                "provider": self.provider_id,
                "aoi": request.aoi.coordinates,
                "dates": (
                    [request.date_range.start_date, request.date_range.end_date]
                    if request.date_range
                    else None
                ),
                "cols": sorted(request.collections),
                "sensors": [s.value for s in request.sensor_types],
                "cloud": request.max_cloud_cover,
                "limit": request.limit,
                "sort": request.sort_order,
                "cursor": request.cursor,
            },
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def _encode_cursor(self, next_token: str | None) -> str | None:
        if not next_token:
            return None
        payload = {"provider": self.provider_id, "token": next_token, "v": 1}
        return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()

    def _decode_cursor(self, cursor: str | None) -> str | None:
        if not cursor:
            return None
        try:
            raw = base64.urlsafe_b64decode(cursor.encode()).decode()
            data = json.loads(raw)
            if data.get("provider") != self.provider_id:
                return None
            token = data.get("token")
            return str(token) if token is not None else None
        except Exception:
            return None

    def _validate_preview_url(self, href: str | None) -> str | None:
        if not href or not isinstance(href, str):
            return None
        try:
            parts = urlsplit(href)
            if parts.scheme not in {"http", "https"}:
                return None
            if parts.hostname in EARTH_SEARCH_ALLOWED_PREVIEW_HOSTS:
                return href
            return None
        except Exception:
            return None

    def _normalize_scene(
        self,
        item: dict[str, Any],
        collection_id: str,
    ) -> SatelliteScene | None:
        """Normalizes a raw STAC Feature into a validated SatelliteScene."""
        try:
            item_id = str(item.get("id") or "").strip()
            if not item_id:
                return None

            properties = item.get("properties") or {}
            geometry_raw = item.get("geometry")
            bbox_raw = item.get("bbox")

            # Timestamp parsing
            dt_str = properties.get("datetime") or properties.get("created")
            if not dt_str:
                return None
            if dt_str.endswith("Z"):
                dt_str = dt_str[:-1] + "+00:00"
            acq_time = datetime.fromisoformat(dt_str)
            if acq_time.tzinfo is None:
                acq_time = acq_time.replace(tzinfo=UTC)

            # Footprint & Bounding Box
            if not geometry_raw or not isinstance(geometry_raw, dict):
                return None
            geom_type_str = geometry_raw.get("type")
            if geom_type_str == "Polygon":
                g_type = GeometryType.POLYGON
            elif geom_type_str == "MultiPolygon":
                g_type = GeometryType.MULTI_POLYGON
            else:
                return None

            footprint = AOIGeometry(
                type=g_type,
                coordinates=geometry_raw.get("coordinates"),
                crs="EPSG:4326",
            )

            # Compute or validate bbox
            if isinstance(bbox_raw, list) and len(bbox_raw) == 4:
                bbox_tuple = (
                    float(bbox_raw[0]),
                    float(bbox_raw[1]),
                    float(bbox_raw[2]),
                    float(bbox_raw[3]),
                )
            else:
                # Fallback calculate from coordinates
                coords = geometry_raw.get("coordinates")
                lons: list[float] = []
                lats: list[float] = []
                if g_type == GeometryType.POLYGON and coords:
                    for ring in coords:
                        for p in ring:
                            lons.append(float(p[0]))
                            lats.append(float(p[1]))
                if lons and lats:
                    bbox_tuple = (min(lons), min(lats), max(lons), max(lats))
                else:
                    return None

            # Platform & Sensor
            raw_plat = properties.get("platform") or properties.get("constellation") or ""
            if "2b" in str(raw_plat).lower() or item_id.upper().startswith("S2B"):
                platform_str = "Sentinel-2B"
            elif "2a" in str(raw_plat).lower() or item_id.upper().startswith("S2A"):
                platform_str = "Sentinel-2A"
            elif "2c" in str(raw_plat).lower() or item_id.upper().startswith("S2C"):
                platform_str = "Sentinel-2C"
            elif str(raw_plat).strip():
                platform_str = str(raw_plat).strip()
            else:
                platform_str = "Sentinel-2"

            sensor_type = SensorType.MULTISPECTRAL

            # Cloud cover
            cloud_val = properties.get("eo:cloud_cover")
            cloud_float: float | None = None
            if cloud_val is not None:
                try:
                    cloud_float = round(float(cloud_val), 2)
                    if not (0.0 <= cloud_float <= 100.0):
                        cloud_float = None
                except (ValueError, TypeError):
                    cloud_float = None

            # Assets & Previews
            assets = item.get("assets") or {}
            thumbnail_url: str | None = None
            preview_url: str | None = None

            if "thumbnail" in assets and isinstance(assets["thumbnail"], dict):
                thumbnail_url = self._validate_preview_url(assets["thumbnail"].get("href"))
            if "rendered_preview" in assets and isinstance(assets["rendered_preview"], dict):
                preview_url = self._validate_preview_url(assets["rendered_preview"].get("href"))
            elif "visual" in assets and isinstance(assets["visual"], dict):
                preview_url = self._validate_preview_url(assets["visual"].get("href"))

            if not thumbnail_url and preview_url:
                thumbnail_url = preview_url

            # Available bands
            available_bands = list(S2_KNOWN_BANDS)

            # Quality score heuristic (0.0 to 1.0)
            if cloud_float is not None:
                quality_score = round(max(0.0, min(1.0, 1.0 - (cloud_float / 100.0) * 0.6)), 2)
            else:
                quality_score = 0.85

            # Safe metadata
            safe_meta: dict[str, Any] = {
                "stac_id": item_id,
                "collection": collection_id,
                "grid_code": properties.get("grid:code"),
                "constellation": properties.get("constellation"),
                "epsg": properties.get("proj:epsg", 32643),
                "processing_level": properties.get("s2:processing_baseline", "Level-2A"),
            }

            return SatelliteScene(
                id=item_id,
                provider=self.provider_id,
                collection=collection_id,
                acquisition_time=acq_time,
                sensor_type=sensor_type,
                platform=platform_str,
                cloud_cover=cloud_float,
                geometry=footprint,
                bbox=bbox_tuple,
                thumbnail_url=thumbnail_url,
                preview_url=preview_url,
                available_bands=available_bands,
                resolution_meters=10.0,
                quality_score=quality_score,
                metadata=safe_meta,
            )
        except (ValidationError, Exception) as exc:
            logger.warning(
                "scene_normalization_failed", extra={"item_id": item.get("id"), "error": str(exc)}
            )
            return None

    async def search_scenes(self, request: SceneSearchRequest) -> SceneSearchResponse:
        if not self.is_configured():
            raise ProviderNotConfiguredError(self.provider_id)

        # Check Cache
        cache_key = self._generate_cache_key(request)
        if self._cache is not None:
            cached_res = self._cache.get(cache_key)
            if cached_res is not None:
                return cached_res

        req_id = f"search_{uuid4().hex[:12]}"
        t_start = time.perf_counter()
        token = self._decode_cursor(request.cursor)
        body = self._build_search_body(request, token)
        target_url = urljoin(self._base_url, "search")

        client = await self._get_client()
        last_error: Exception | None = None
        response_json: dict[str, Any] | None = None
        attempt_count = 0

        for attempt in range(self._max_retries + 1):
            attempt_count += 1
            try:
                resp = await client.post(
                    target_url,
                    json=body,
                    headers={
                        "Accept": "application/geo+json, application/json",
                        "User-Agent": "SatQuery-AI/1.0",
                        "X-Request-ID": req_id,
                    },
                )

                if resp.status_code == 200:
                    try:
                        response_json = resp.json()
                        break
                    except Exception as e:
                        raise InvalidProviderResponseError(
                            self.provider_id, f"Invalid JSON received from STAC catalog: {e}"
                        ) from e

                if resp.status_code == 401 or resp.status_code == 403:
                    raise ProviderAuthenticationError(
                        self.provider_id,
                        f"Authentication failed with status {resp.status_code}.",
                    )

                if resp.status_code == 429:
                    if attempt < self._max_retries:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    raise ProviderRateLimitError(
                        self.provider_id,
                        "Provider rate limit exceeded. Please try again later.",
                    )

                if resp.status_code in TRANSIENT_HTTP_STATUSES:
                    if attempt < self._max_retries:
                        await asyncio.sleep(0.3 * (2**attempt))
                        continue
                    raise ProviderUnavailableError(
                        self.provider_id,
                        f"STAC provider returned status {resp.status_code}.",
                    )

                if 400 <= resp.status_code < 500:
                    text_snippet = resp.text[:200]
                    raise SatelliteProviderError(
                        "INVALID_REQUEST",
                        (
                            f"STAC catalogue rejected request with HTTP {resp.status_code}: "
                            f"{text_snippet}"
                        ),
                        status_code=400,
                    )

                raise ProviderUnavailableError(
                    self.provider_id,
                    f"Unexpected HTTP status {resp.status_code} from provider.",
                )

            except (
                httpx2.ConnectTimeout,
                httpx2.ReadTimeout,
                httpx2.TimeoutException,
            ) as timeout_exc:
                last_error = timeout_exc
                if attempt < self._max_retries:
                    await asyncio.sleep(0.3 * (2**attempt))
                    continue
                raise ProviderTimeoutError(
                    self.provider_id,
                    f"STAC catalogue request timed out after {self._timeout_seconds}s.",
                ) from timeout_exc
            except httpx2.RequestError as req_exc:
                last_error = req_exc
                if attempt < self._max_retries:
                    await asyncio.sleep(0.3 * (2**attempt))
                    continue
                raise ProviderUnavailableError(
                    self.provider_id, f"Network error contacting STAC catalogue: {req_exc}"
                ) from req_exc

        if response_json is None:
            raise ProviderUnavailableError(
                self.provider_id,
                f"Failed to receive response from provider: {last_error}",
            )

        duration_ms = round((time.perf_counter() - t_start) * 1000)
        features = response_json.get("features")
        if not isinstance(features, list):
            raise InvalidProviderResponseError(
                self.provider_id, "STAC response did not contain a 'features' array."
            )

        # Normalize features
        scenes: list[SatelliteScene] = []
        malformed_count = 0
        default_col = (
            request.collections[0] if request.collections else EARTH_SEARCH_DEFAULT_COLLECTION
        )

        for feat in features:
            if not isinstance(feat, dict):
                malformed_count += 1
                continue
            scene = self._normalize_scene(feat, default_col)
            if scene is not None:
                scenes.append(scene)
            else:
                malformed_count += 1

        warnings: list[AnalysisWarning] = []

        if malformed_count > 0:
            warnings.append(
                AnalysisWarning(
                    code=WarningCode.PARTIAL_COVERAGE,
                    severity=WarningSeverity.LOW,
                    title="Malformed Scenes Skipped",
                    message=(
                        f"{malformed_count} provider scene(s) had invalid geometry or "
                        "missing fields and were excluded."
                    ),
                    suggested_action="Try adjusting your date range or cloud cover filter.",
                )
            )

        if len(scenes) == 0:
            warnings.append(
                AnalysisWarning(
                    code=WarningCode.INSUFFICIENT_EVIDENCE,
                    severity=WarningSeverity.INFO,
                    title="No Scenes Found",
                    message=(
                        "No satellite scenes matched the selected Area of Interest, "
                        "date range, and filters."
                    ),
                    suggested_action=(
                        "Expand the date range, increase cloud cover ceiling, "
                        "or adjust the AOI boundary."
                    ),
                )
            )

        # Next cursor handling from links or token
        next_cursor: str | None = None
        next_token: str | None = None
        # Check next link
        for link in response_json.get("links") or []:
            if isinstance(link, dict) and link.get("rel") == "next":
                href = link.get("href", "")
                if "token=" in href:
                    next_token = href.split("token=")[-1].split("&")[0]
                elif link.get("body") and isinstance(link["body"], dict):
                    next_token = link["body"].get("token")
        if not next_token and response_json.get("next"):
            next_token = str(response_json["next"])
        if next_token:
            next_cursor = self._encode_cursor(next_token)

        total_matched = response_json.get("context", {}).get("matched")

        result = SceneSearchResponse(
            request_id=req_id,
            scenes=scenes,
            total_matched=total_matched,
            returned_count=len(scenes),
            next_cursor=next_cursor,
            provider_id=self.provider_id,
            execution=ProviderExecutionMetadata(
                provider_id=self.provider_id,
                provider_mode=ProviderMode.REAL,
                data_origin=DataOrigin.REAL,
                requested_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                duration_milliseconds=duration_ms,
                attempt_count=attempt_count,
                fallback_used=False,
                cached=False,
                provider_request_id=req_id,
                limitations=[
                    "Metadata-only STAC search",
                    "Imagery preview URLs expire per provider policy",
                ],
            ),
            warnings=warnings,
            data_origin=DataOrigin.REAL,
        )

        if self._cache is not None:
            self._cache.put(cache_key, result)

        return result

    async def get_scene(self, scene_id: str) -> SatelliteScene:
        if not self.is_configured():
            raise ProviderNotConfiguredError(self.provider_id)

        target_url = urljoin(
            self._base_url,
            f"collections/{EARTH_SEARCH_DEFAULT_COLLECTION}/items/{scene_id}",
        )
        client = await self._get_client()

        try:
            resp = await client.get(
                target_url,
                headers={"Accept": "application/geo+json, application/json"},
            )
            if resp.status_code == 404:
                raise SceneNotFoundError(scene_id)
            if resp.status_code != 200:
                raise ProviderUnavailableError(
                    self.provider_id, f"STAC catalogue returned {resp.status_code}"
                )

            item = resp.json()
            scene = self._normalize_scene(item, EARTH_SEARCH_DEFAULT_COLLECTION)
            if scene is None:
                raise InvalidProviderResponseError(
                    self.provider_id, f"Failed to normalize STAC item '{scene_id}'"
                )
            return scene
        except (httpx2.TimeoutException, httpx2.RequestError) as e:
            raise ProviderUnavailableError(self.provider_id, str(e)) from e

    async def aclose(self) -> None:
        if self._owns_client and self._client and not self._client.is_closed:
            await self._client.aclose()
