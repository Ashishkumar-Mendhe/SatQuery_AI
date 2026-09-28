from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast
from urllib.parse import urlsplit

import httpx2
from pydantic import TypeAdapter, ValidationError

from satquery.api.schemas.catalog import AcquisitionInterval, CatalogGeometry, ProviderIdentity
from satquery.api.schemas.nisar import (
    NISAR_GCOV_COLLECTION,
    NisarDiagonalTerm,
    NisarDiscoveryRequest,
    NisarDiscoveryResponse,
    NisarFrequencyMetadata,
    NisarGcovScene,
    NisarPolarization,
    NisarQualityEvidence,
)
from satquery.api.schemas.scene_metadata import (
    SceneMetadataResponse,
    UnavailableSceneMetadata,
)
from satquery.api.schemas.viewer import ViewerSceneIdentity
from satquery.providers.catalog.base import CatalogueProviderError

NISAR_PROVIDER_ID = "nasa-cmr-asf"
NISAR_CMR_BASE_URL = "https://cmr.earthdata.nasa.gov/search/"
NISAR_DATA_HOST = "nisar.asf.earthdatacloud.nasa.gov"
NISAR_ATTRIBUTION = "NASA/JPL NISAR L-band data distributed by ASF DAAC."
NISAR_MIN_PROVISIONAL_CRID = 5023
_GEOMETRY: TypeAdapter[CatalogGeometry] = TypeAdapter(CatalogGeometry)
_TERM_BY_POLARIZATION: dict[str, NisarDiagonalTerm] = {
    "HH": "HHHH",
    "HV": "HVHV",
    "VH": "VHVH",
    "VV": "VVVV",
    "RH": "RHRH",
    "RV": "RVRV",
}
_KNOWN_LIMITATIONS = [
    "PROVISIONAL calibration is validated at limited sites and is not the final validated release.",
    "High-latitude ionospheric effects may degrade geolocation and derived "
    "interferometric products.",
    "RFI filtering can leave residual interference or remove features in high-contrast areas.",
    "Low-level ripples may occur over dark backgrounds.",
    "Frequency B 5 MHz data have larger systematic radiometric calibration residuals.",
    "Relative polarimetric phase is not fully calibrated; diagonal power terms are unaffected.",
    "Some products derive from incomplete L0B data and may contain shifts or defocus artifacts.",
]


@dataclass(frozen=True, slots=True)
class NisarResolvedProduct:
    scene: NisarGcovScene
    download_url: str
    filename: str


class NisarCmrProvider:
    """Public CMR discovery plus trusted ASF download resolution for NISAR L2 GCOV."""

    def __init__(self, client: httpx2.AsyncClient | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx2.AsyncClient(
            timeout=httpx2.Timeout(30.0), follow_redirects=False, trust_env=False
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search(self, request: NisarDiscoveryRequest) -> NisarDiscoveryResponse:
        west, south, east, north = _geometry_bounds(request.aoi)
        params = {
            "short_name": NISAR_GCOV_COLLECTION,
            "page_size": str(request.limit),
            "bounding_box": f"{west},{south},{east},{north}",
            "temporal": f"{_utc(request.acquisition.start)},{_utc(request.acquisition.end)}",
            "sort_key[]": "start_date",
        }
        payload = await self._request_json("granules.umm_json", params=params)
        items = payload.get("items")
        if not isinstance(items, list):
            raise _invalid("NASA CMR response did not contain granules.")
        return NisarDiscoveryResponse(
            scenes=[self._scene(_mapping(item)) for item in items[: request.limit]],
            provider_attribution=NISAR_ATTRIBUTION,
        )

    async def resolve(self, source: ViewerSceneIdentity) -> NisarResolvedProduct:
        if source.provider != NISAR_PROVIDER_ID or source.collection != NISAR_GCOV_COLLECTION:
            raise CatalogueProviderError(
                "UNSUPPORTED_NISAR_SOURCE",
                "Select a NISAR PROVISIONAL L2 GCOV scene returned by NASA CMR discovery.",
                retryable=False,
            )
        payload = await self._request_json(
            "granules.umm_json", params={"concept_id": source.item, "page_size": "1"}
        )
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise CatalogueProviderError(
                "NISAR_SOURCE_NOT_FOUND",
                "NASA CMR no longer reports the selected NISAR granule.",
                retryable=False,
            )
        raw = _mapping(items[0])
        scene = self._scene(raw)
        if scene.source != source:
            raise _invalid("NASA CMR returned a different NISAR granule.")
        umm = _mapping(raw.get("umm"))
        url = _hdf5_url(umm)
        filename = f"{scene.granule_ur}.h5"
        return NisarResolvedProduct(scene=scene, download_url=url, filename=filename)

    async def _request_json(self, path: str, *, params: dict[str, str]) -> dict[str, Any]:
        try:
            response = await self._client.get(
                NISAR_CMR_BASE_URL + path,
                params=params,
                headers={"Client-Id": "SatQuery-Phase9C", "Accept": "application/json"},
            )
        except httpx2.HTTPError as exc:
            raise CatalogueProviderError(
                "NISAR_DISCOVERY_UNAVAILABLE",
                "NASA CMR is unreachable; retry the metadata search.",
                retryable=True,
            ) from exc
        if response.status_code >= 400:
            raise CatalogueProviderError(
                "NISAR_DISCOVERY_FAILURE",
                f"NASA CMR returned HTTP {response.status_code}.",
                retryable=response.status_code >= 500,
            )
        try:
            return _mapping(response.json())
        except ValueError as exc:
            raise _invalid("NASA CMR returned invalid JSON.") from exc

    @staticmethod
    def _scene(raw: dict[str, Any]) -> NisarGcovScene:
        meta = _mapping(raw.get("meta"))
        umm = _mapping(raw.get("umm"))
        concept_id = _required(meta, "concept-id")
        if meta.get("provider-id") != "ASF" or not concept_id.startswith("G"):
            raise _invalid("CMR granule is not an ASF NISAR record.")
        collection = _mapping(umm.get("CollectionReference"))
        if collection.get("ShortName") != NISAR_GCOV_COLLECTION:
            raise _invalid("CMR granule is not from the supported PROVISIONAL GCOV collection.")
        platforms = umm.get("Platforms")
        if not isinstance(platforms, list) or not platforms:
            raise _invalid("CMR granule lacks NISAR platform metadata.")
        platform = _mapping(platforms[0])
        instruments = platform.get("Instruments")
        if platform.get("ShortName") != "NISAR" or not isinstance(instruments, list):
            raise _invalid("CMR granule is not a NISAR platform record.")
        if not instruments or _mapping(instruments[0]).get("ShortName") != "L-SAR":
            raise _invalid("Only NISAR L-band GCOV is supported; S-band is not inferred.")
        attributes = _attributes(umm)
        identifiers = _identifiers(umm)
        crid = identifiers.get("CRID")
        if (
            crid is None
            or re.fullmatch(r"P[0-9]{5}", crid) is None
            or int(crid[1:]) < NISAR_MIN_PROVISIONAL_CRID
        ):
            raise _invalid("CMR granule does not carry a PROVISIONAL CRID of P05023 or later.")
        temporal = _mapping(umm.get("TemporalExtent"))
        date_range = _mapping(temporal.get("RangeDateTime"))
        acquisition = AcquisitionInterval(
            start=_datetime(date_range.get("BeginningDateTime")),
            end=_datetime(date_range.get("EndingDateTime")),
        )
        footprint = _footprint(umm)
        frequencies: list[NisarFrequencyMetadata] = []
        reported = attributes.get("FREQUENCIES", [])
        for frequency in ("A", "B"):
            if frequency not in reported:
                continue
            polarizations = attributes.get(f"FREQUENCY_{frequency}_POLARIZATION", [])
            typed_polarizations = [
                cast(NisarPolarization, value)
                for value in polarizations
                if value in {"HH", "HV", "VH", "VV", "RH", "RV", "LH", "LV"}
            ]
            terms = [
                _TERM_BY_POLARIZATION[value]
                for value in typed_polarizations
                if value in _TERM_BY_POLARIZATION
            ]
            bandwidth = _single_int(attributes, f"FREQUENCY_{frequency}_RANGE_BANDWIDTH")
            if not typed_polarizations or bandwidth not in {5, 20, 40, 77}:
                raise _invalid(f"CMR frequency {frequency} metadata is incomplete or unsupported.")
            spacing = {5: 80, 20: 20, 40: 10, 77: 20}[bandwidth]
            frequencies.append(
                NisarFrequencyMetadata(
                    frequency=frequency,
                    range_bandwidth_mhz=bandwidth,
                    nominal_pixel_spacing_metres=spacing,
                    polarizations=typed_polarizations,
                    diagonal_covariance_terms=terms,
                )
            )
        if not frequencies:
            raise _invalid("CMR granule reports no supported L-band frequency layers.")
        granule_ur = _required(umm, "GranuleUR")
        orbit_code = _granule_name_parts(granule_ur)[-4]
        orbit_names: dict[
            str, Literal["precise", "medium", "near_real_time", "forecast", "unknown"]
        ] = {
            "P": "precise",
            "M": "medium",
            "N": "near_real_time",
            "F": "forecast",
        }
        orbit_fidelity = orbit_names.get(orbit_code, "unknown")
        urls = umm.get("RelatedUrls")
        related = urls if isinstance(urls, list) else []
        qa_report = any(
            _mapping(item).get("Subtype") == "PRODUCT QUALITY ASSESSMENT" for item in related
        )
        qa_summary = any(
            str(_mapping(item).get("URL", "")).endswith("_QA_SUMMARY.csv") for item in related
        )
        product_version = _single(attributes, "PRODUCT_VERSION")
        pge = _mapping(umm.get("PGEVersionClass"))
        pge_version = _required(pge, "PGEVersion")
        source = ViewerSceneIdentity(
            provider=NISAR_PROVIDER_ID, collection=NISAR_GCOV_COLLECTION, item=concept_id
        )
        metadata = SceneMetadataResponse(
            outcome=UnavailableSceneMetadata(
                state="unavailable",
                source=source,
                provider=ProviderIdentity(id=NISAR_PROVIDER_ID, name="NASA CMR / ASF DAAC"),
                expected_modality="sar",
                reason_code="metadata_incomplete",
                missing_fields=["crs"],
                retryable=False,
                reason=(
                    "The granule-specific projected CRS is stored inside the authenticated "
                    "HDF5 product."
                ),
                corrective_action=(
                    "Stage and ingest the HDF5 product to validate its projection and grid."
                ),
            )
        )
        return NisarGcovScene(
            source=source,
            concept_id=concept_id,
            granule_ur=granule_ur,
            acquisition=acquisition,
            footprint=footprint,
            product_version=product_version,
            pge_version=pge_version,
            composite_release_id=crid,
            frequencies=frequencies,
            quality=NisarQualityEvidence(
                full_frame=_single_bool(attributes, "FULL_FRAME"),
                joint_observation=_single_bool(attributes, "JOINT_OBSERVATION"),
                orbit_fidelity=orbit_fidelity,
                qa_summary_available=qa_summary,
                qa_report_available=qa_report,
                provisional_known_limitations=list(_KNOWN_LIMITATIONS),
            ),
            metadata=metadata,
        )


def _hdf5_url(umm: dict[str, Any]) -> str:
    urls = umm.get("RelatedUrls")
    for item in urls if isinstance(urls, list) else []:
        value = _mapping(item)
        url = value.get("URL")
        if (
            value.get("Type") != "GET DATA"
            or value.get("Format") != "HDF5"
            or not isinstance(url, str)
        ):
            continue
        parsed = urlsplit(url)
        if (
            parsed.scheme == "https"
            and parsed.hostname == NISAR_DATA_HOST
            and parsed.port is None
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.path.startswith(f"/NISAR/{NISAR_GCOV_COLLECTION}/")
            and parsed.path.endswith(".h5")
        ):
            return url
    raise _invalid("CMR granule lacks an approved ASF HDF5 data link.")


def _footprint(umm: dict[str, Any]) -> CatalogGeometry:
    spatial = _mapping(umm.get("SpatialExtent"))
    horizontal = _mapping(spatial.get("HorizontalSpatialDomain"))
    geometry = _mapping(horizontal.get("Geometry"))
    polygons = geometry.get("GPolygons")
    if not isinstance(polygons, list) or not polygons:
        raise _invalid("CMR granule lacks a polygon footprint.")
    try:
        rings: list[list[list[float]]] = []
        for polygon in polygons:
            boundary = _mapping(_mapping(polygon).get("Boundary"))
            points = boundary.get("Points")
            if not isinstance(points, list):
                raise ValueError("missing boundary points")
            rings.append(
                [
                    [float(_mapping(point)["Longitude"]), float(_mapping(point)["Latitude"])]
                    for point in points
                ]
            )
        if len(rings) == 1:
            return _GEOMETRY.validate_python({"type": "Polygon", "coordinates": [rings[0]]})
        return _GEOMETRY.validate_python(
            {"type": "MultiPolygon", "coordinates": [[ring] for ring in rings]}
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise _invalid("CMR granule has an invalid footprint.") from exc


def _attributes(umm: dict[str, Any]) -> dict[str, list[str]]:
    raw = umm.get("AdditionalAttributes")
    result: dict[str, list[str]] = {}
    for item in raw if isinstance(raw, list) else []:
        value = _mapping(item)
        name = value.get("Name")
        values = value.get("Values")
        if isinstance(name, str) and isinstance(values, list):
            result[name] = [entry for entry in values if isinstance(entry, str)]
    return result


def _identifiers(umm: dict[str, Any]) -> dict[str, str]:
    data_granule = _mapping(umm.get("DataGranule"))
    raw = data_granule.get("Identifiers")
    result: dict[str, str] = {}
    for item in raw if isinstance(raw, list) else []:
        value = _mapping(item)
        key = value.get("IdentifierType")
        identifier = value.get("Identifier")
        if isinstance(key, str) and isinstance(identifier, str):
            result[key] = identifier
    return result


def _geometry_bounds(geometry: CatalogGeometry) -> tuple[float, float, float, float]:
    polygons = [geometry.coordinates] if geometry.type == "Polygon" else geometry.coordinates
    positions = [position for polygon in polygons for ring in polygon for position in ring]
    return (
        min(position[0] for position in positions),
        min(position[1] for position in positions),
        max(position[0] for position in positions),
        max(position[1] for position in positions),
    )


def _granule_name_parts(value: str) -> list[str]:
    parts = value.split("_")
    if len(parts) < 18:
        raise _invalid("NISAR granule identifier does not match the documented naming convention.")
    return parts


def _single(attributes: dict[str, list[str]], key: str) -> str:
    values = attributes.get(key, [])
    if len(values) != 1:
        raise _invalid(f"CMR granule has invalid {key} metadata.")
    return values[0]


def _single_int(attributes: dict[str, list[str]], key: str) -> int:
    try:
        return int(_single(attributes, key))
    except ValueError as exc:
        raise _invalid(f"CMR granule has invalid numeric {key} metadata.") from exc


def _single_bool(attributes: dict[str, list[str]], key: str) -> bool:
    value = _single(attributes, key)
    if value not in {"TRUE", "FALSE"}:
        raise _invalid(f"CMR granule has invalid boolean {key} metadata.")
    return value == "TRUE"


def _datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise _invalid("CMR granule acquisition time is unavailable.")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError as exc:
        raise _invalid("CMR granule acquisition time is invalid.") from exc


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _mapping(value: object) -> dict[str, Any]:
    return {str(key): item for key, item in value.items()} if isinstance(value, dict) else {}


def _required(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise _invalid(f"CMR metadata is missing {key}.")
    return value


def _invalid(message: str) -> CatalogueProviderError:
    return CatalogueProviderError("INVALID_NISAR_METADATA", message, retryable=False)
