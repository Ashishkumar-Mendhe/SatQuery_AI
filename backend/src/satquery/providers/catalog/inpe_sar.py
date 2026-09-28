from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import quote, urlsplit

import httpx2
from pydantic import TypeAdapter, ValidationError

from satquery.api.schemas.catalog import AcquisitionInterval, CatalogGeometry, ProviderIdentity
from satquery.api.schemas.sar import SarDiscoveryRequest, SarDiscoveryResponse, SarDiscoveryScene
from satquery.api.schemas.scene_metadata import (
    AlreadyCalibrated,
    AvailableSceneMetadata,
    AvailableValidDataMask,
    NativeResolution,
    SarPolarizationMetadata,
    SarSceneMetadata,
    SceneCrs,
    SceneMetadataResponse,
)
from satquery.api.schemas.viewer import ViewerSceneIdentity
from satquery.providers.catalog.base import CatalogueProviderError

INPE_SAR_PROVIDER_ID = "inpe-bdc"
INPE_SAR_COLLECTION = "sentinel-1-rtc-1"
INPE_SAR_BASE_URL = "https://data.inpe.br/bdc/stac/v1/"
INPE_SAR_DATA_PREFIX = "/bdc/data/sentinel-1/rtc/v1/"
INPE_SAR_ATTRIBUTION = "Sentinel-1 data: ESA/Copernicus; RTC processing and hosting: INPE."
_GEOMETRY: TypeAdapter[CatalogGeometry] = TypeAdapter(CatalogGeometry)


@dataclass(frozen=True, slots=True)
class InpeSarAsset:
    polarization: Literal["HH", "HV", "VH", "VV"]
    location: str
    nodata: float
    checksum: str | None


@dataclass(frozen=True, slots=True)
class InpeSarResolvedScene:
    scene: SarDiscoveryScene
    backscatter: InpeSarAsset
    layover_shadow_mask: str
    terrain_model: str


class InpeSarProvider:
    """Trusted adapter for INPE's public, GRD-derived Sentinel-1 RTC collection."""

    def __init__(self, client: httpx2.AsyncClient | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx2.AsyncClient(
            timeout=httpx2.Timeout(30.0), follow_redirects=False, trust_env=False
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search(self, request: SarDiscoveryRequest) -> SarDiscoveryResponse:
        payload = await self._request_json(
            "POST",
            "search",
            json_body={
                "collections": [INPE_SAR_COLLECTION],
                "intersects": request.aoi.model_dump(mode="json"),
                "datetime": (f"{_utc(request.acquisition.start)}/{_utc(request.acquisition.end)}"),
                "limit": request.limit,
            },
        )
        features = payload.get("features")
        if not isinstance(features, list):
            raise _invalid("INPE search response did not contain features.")
        scenes = [self._scene(_mapping(item)) for item in features[: request.limit]]
        return SarDiscoveryResponse(scenes=scenes, provider_attribution=INPE_SAR_ATTRIBUTION)

    async def resolve(
        self, source: ViewerSceneIdentity, polarization: Literal["HH", "HV", "VH", "VV"]
    ) -> InpeSarResolvedScene:
        if source.provider != INPE_SAR_PROVIDER_ID or source.collection != INPE_SAR_COLLECTION:
            raise CatalogueProviderError(
                "UNSUPPORTED_SAR_SOURCE",
                "Select an INPE Sentinel-1 RTC scene returned by SAR discovery.",
                retryable=False,
            )
        payload = await self._request_json(
            "GET",
            f"collections/{INPE_SAR_COLLECTION}/items/{quote(source.item, safe='')}",
        )
        scene = self._scene(payload)
        if scene.source != source:
            raise _invalid("INPE returned a different SAR scene.")
        assets = _mapping(payload.get("assets"))
        key = f"Gamma0_{polarization}"
        if key not in assets:
            available = ", ".join(scene.polarizations)
            raise CatalogueProviderError(
                "SAR_POLARIZATION_UNAVAILABLE",
                f"{polarization} is unavailable for this scene. Available: {available}.",
                retryable=False,
            )
        data_asset = _mapping(assets[key])
        mask_asset = _mapping(assets.get("layover_shadow_mask"))
        data_url = _trusted_data_url(data_asset.get("href"))
        mask_url = _trusted_data_url(mask_asset.get("href"))
        properties = _mapping(payload.get("properties"))
        return InpeSarResolvedScene(
            scene=scene,
            backscatter=InpeSarAsset(
                polarization=polarization,
                location=data_url,
                nodata=-32768.0,
                checksum=_optional(data_asset.get("checksum:multihash")),
            ),
            layover_shadow_mask=mask_url,
            terrain_model=_optional(properties.get("rtc_dem")) or "unavailable",
        )

    async def _request_json(
        self, method: str, path: str, *, json_body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(method, INPE_SAR_BASE_URL + path, json=json_body)
        except httpx2.HTTPError as exc:
            raise CatalogueProviderError(
                "SAR_PROVIDER_UNAVAILABLE",
                "INPE Sentinel-1 service is unreachable; retry or verify network access.",
                retryable=True,
            ) from exc
        if response.status_code == 404:
            raise CatalogueProviderError(
                "SAR_SOURCE_NOT_FOUND",
                "The selected SAR scene is no longer available.",
                retryable=False,
            )
        if response.status_code in {401, 403}:
            raise CatalogueProviderError(
                "SAR_ACCESS_DENIED",
                "INPE denied the RTC asset request; verify provider access policy or credentials.",
                retryable=False,
            )
        if response.status_code >= 400:
            raise CatalogueProviderError(
                "SAR_PROVIDER_FAILURE",
                f"INPE SAR service returned HTTP {response.status_code}.",
                retryable=response.status_code >= 500,
            )
        try:
            value = response.json()
        except ValueError as exc:
            raise _invalid("INPE returned invalid JSON.") from exc
        return _mapping(value)

    @staticmethod
    def _scene(raw: dict[str, Any]) -> SarDiscoveryScene:
        item_id = _required(raw, "id")
        if raw.get("collection") != INPE_SAR_COLLECTION:
            raise _invalid("INPE returned an unsupported collection.")
        properties = _mapping(raw.get("properties"))
        try:
            footprint = _GEOMETRY.validate_python(raw.get("geometry"))
        except ValidationError as exc:
            raise _invalid("INPE returned invalid scene geometry.") from exc
        start = _datetime(properties.get("start_datetime") or properties.get("datetime"))
        end = _datetime(properties.get("end_datetime") or properties.get("datetime"))
        assets = _mapping(raw.get("assets"))
        polarizations = [value for value in ("HH", "HV", "VH", "VV") if f"Gamma0_{value}" in assets]
        if not polarizations or "layover_shadow_mask" not in assets:
            raise _invalid("INPE scene lacks gamma0 data or the terrain-validity mask.")
        mode = _optional(properties.get("operational_mode"))
        if mode not in {"IW", "EW", "SM"}:
            raise _invalid("INPE scene has an unsupported instrument mode.")
        resolution = {"IW": 10.0, "EW": 40.0, "SM": 10.0}[mode]
        source = ViewerSceneIdentity(
            provider=INPE_SAR_PROVIDER_ID, collection=INPE_SAR_COLLECTION, item=item_id
        )
        acquisition = AcquisitionInterval(start=start, end=end)
        digest = hashlib.sha256(
            json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        metadata = SarSceneMetadata(
            modality="sar",
            source=source,
            source_version=digest,
            provider=ProviderIdentity(id=INPE_SAR_PROVIDER_ID, name="INPE Brazil Data Cube"),
            mission="Sentinel-1",
            acquisition=acquisition,
            footprint=footprint,
            native_resolution=NativeResolution(
                x_metres=resolution, y_metres=resolution, source_field="instrument mode policy"
            ),
            crs=SceneCrs(
                identifier="EPSG:4326", axis_units="degree", source_field="collection description"
            ),
            processing_level="Level-2 RTC (RTCH)",
            product_maturity="operational",
            calibration=AlreadyCalibrated(
                source_values="calibrated",
                method="identity",
                units="gamma0_power",
                explanation=(
                    "INPE supplies terrain-normalized gamma-0 power; no scale or offset is applied."
                ),
            ),
            valid_data_mask=AvailableValidDataMask(
                state="available",
                source_role="layover_shadow_mask plus finite/non-nodata gamma0",
                convention="categorical_quality",
                valid_values=[0],
                explanation=(
                    "Mask class 0 is unaffected by layover/shadow; classes 1, 2, 3, and "
                    "255 are excluded, together with non-finite or nodata gamma0."
                ),
            ),
            polarizations=[
                SarPolarizationMetadata(
                    polarization=value, native_resolution_metres=resolution, units="gamma0_power"
                )
                for value in polarizations
            ],
        )
        return SarDiscoveryScene(
            source=source,
            acquisition=acquisition,
            footprint=footprint,
            polarizations=polarizations,
            instrument_mode=mode,
            processing_level="RTCH",
            native_resolution_metres=resolution,
            metadata=SceneMetadataResponse(
                outcome=AvailableSceneMetadata(state="available", metadata=metadata)
            ),
        )


def _trusted_data_url(value: object) -> str:
    if not isinstance(value, str):
        raise _invalid("INPE scene is missing an RTC asset URL.")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "data.inpe.br"
        or parsed.port is not None
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith(INPE_SAR_DATA_PREFIX)
        or not parsed.path.lower().endswith(".tif")
        or ".." in parsed.path.split("/")
    ):
        raise _invalid("INPE returned an untrusted SAR asset location.")
    return value


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise _invalid("INPE scene is missing acquisition time.")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _invalid("INPE scene has invalid acquisition time.") from exc
    return result.astimezone(UTC)


def _mapping(value: object) -> dict[str, Any]:
    return {str(key): item for key, item in value.items()} if isinstance(value, dict) else {}


def _required(raw: dict[str, Any], key: str) -> str:
    value = _optional(raw.get(key))
    if value is None:
        raise _invalid(f"INPE scene is missing {key}.")
    return value


def _optional(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _invalid(message: str) -> CatalogueProviderError:
    return CatalogueProviderError("INVALID_SAR_PROVIDER_RESPONSE", message, retryable=False)
