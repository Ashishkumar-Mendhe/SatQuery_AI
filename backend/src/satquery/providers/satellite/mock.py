"""Deterministic offline mock satellite imagery provider."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from satquery.api.schemas.analysis import (
    AOIGeometry,
    GeometryType,
    SatelliteScene,
    SensorType,
)
from satquery.api.schemas.providers import (
    DataOrigin,
    ProviderCapability,
    ProviderExecutionMetadata,
    ProviderInfo,
    ProviderMode,
    ProviderStatus,
)
from satquery.providers.satellite.base import (
    InvalidProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    SatelliteProvider,
    SceneNotFoundError,
    SceneSearchRequest,
    SceneSearchResponse,
)

# Realistic synthetic coordinates for Bengaluru test AOI
BENGALURU_BBOX: tuple[float, float, float, float] = (77.45, 12.85, 77.75, 13.15)
BENGALURU_FOOTPRINT = AOIGeometry(
    type=GeometryType.POLYGON,
    coordinates=[
        [
            [77.45, 12.85],
            [77.75, 12.85],
            [77.75, 13.15],
            [77.45, 13.15],
            [77.45, 12.85],
        ]
    ],
    bbox=BENGALURU_BBOX,
    crs="EPSG:4326",
)

SYNTHETIC_SCENES: list[SatelliteScene] = [
    SatelliteScene(
        id="mock-scene-optical-01",
        provider="mock",
        collection="sentinel-2-c1-l2a",
        acquisition_time=datetime(2026, 5, 12, 5, 22, 1, tzinfo=UTC),
        sensor_type=SensorType.MULTISPECTRAL,
        platform="Sentinel-2B",
        cloud_cover=4.2,
        geometry=BENGALURU_FOOTPRINT,
        bbox=BENGALURU_BBOX,
        thumbnail_url="https://mock.satquery.internal/previews/mock-scene-optical-01.jpg",
        available_bands=["B02", "B03", "B04", "B08", "B11", "B12"],
        resolution_meters=10.0,
        quality_score=0.96,
        metadata={"processing_level": "Level-2A", "is_synthetic": True},
    ),
    SatelliteScene(
        id="mock-scene-optical-02-before",
        provider="mock",
        collection="sentinel-2-c1-l2a",
        acquisition_time=datetime(2025, 12, 13, 5, 23, 54, tzinfo=UTC),
        sensor_type=SensorType.MULTISPECTRAL,
        platform="Sentinel-2B",
        cloud_cover=2.1,
        geometry=BENGALURU_FOOTPRINT,
        bbox=BENGALURU_BBOX,
        thumbnail_url="https://mock.satquery.internal/previews/mock-scene-optical-02.jpg",
        available_bands=["B02", "B03", "B04", "B08", "B11", "B12"],
        resolution_meters=10.0,
        quality_score=0.98,
        metadata={"processing_level": "Level-2A", "is_synthetic": True, "temporal_role": "before"},
    ),
    SatelliteScene(
        id="mock-scene-optical-03-after",
        provider="mock",
        collection="sentinel-2-c1-l2a",
        acquisition_time=datetime(2025, 12, 28, 5, 24, 11, tzinfo=UTC),
        sensor_type=SensorType.MULTISPECTRAL,
        platform="Sentinel-2C",
        cloud_cover=8.5,
        geometry=BENGALURU_FOOTPRINT,
        bbox=BENGALURU_BBOX,
        thumbnail_url="https://mock.satquery.internal/previews/mock-scene-optical-03.jpg",
        available_bands=["B02", "B03", "B04", "B08", "B11", "B12"],
        resolution_meters=10.0,
        quality_score=0.92,
        metadata={"processing_level": "Level-2A", "is_synthetic": True, "temporal_role": "after"},
    ),
    SatelliteScene(
        id="mock-scene-sar-01",
        provider="mock",
        collection="sentinel-1-grd",
        acquisition_time=datetime(2026, 5, 10, 0, 30, 0, tzinfo=UTC),
        sensor_type=SensorType.SAR,
        platform="Sentinel-1A",
        cloud_cover=0.0,
        geometry=BENGALURU_FOOTPRINT,
        bbox=BENGALURU_BBOX,
        thumbnail_url="https://mock.satquery.internal/previews/mock-scene-sar-01.jpg",
        available_bands=["VV", "VH"],
        resolution_meters=10.0,
        quality_score=0.95,
        metadata={"polarization": "VV+VH", "is_synthetic": True},
    ),
    SatelliteScene(
        id="mock-scene-cloudy-01",
        provider="mock",
        collection="sentinel-2-c1-l2a",
        acquisition_time=datetime(2026, 5, 1, 5, 20, 0, tzinfo=UTC),
        sensor_type=SensorType.OPTICAL,
        platform="Sentinel-2A",
        cloud_cover=78.4,
        geometry=BENGALURU_FOOTPRINT,
        bbox=BENGALURU_BBOX,
        thumbnail_url="https://mock.satquery.internal/previews/mock-scene-cloudy-01.jpg",
        available_bands=["B02", "B03", "B04", "B08"],
        resolution_meters=10.0,
        quality_score=0.25,
        metadata={"is_synthetic": True},
    ),
    SatelliteScene(
        id="mock-scene-spectral-01",
        provider="mock",
        collection="sentinel-2-c1-l2a",
        acquisition_time=datetime(2026, 4, 15, 5, 22, 0, tzinfo=UTC),
        sensor_type=SensorType.MULTISPECTRAL,
        platform="Sentinel-2B",
        cloud_cover=1.5,
        geometry=BENGALURU_FOOTPRINT,
        bbox=BENGALURU_BBOX,
        thumbnail_url="https://mock.satquery.internal/previews/mock-scene-spectral-01.jpg",
        available_bands=["B02", "B03", "B04", "B08", "B11", "B12"],
        resolution_meters=10.0,
        quality_score=0.99,
        metadata={"is_synthetic": True},
    ),
]


def _bboxes_intersect(
    box1: tuple[float, float, float, float] | list[float],
    box2: tuple[float, float, float, float] | list[float],
) -> bool:
    """Check if two bounding boxes [minX, minY, maxX, maxY] intersect."""
    return not (
        box1[2] < box2[0]  # box1 maxX < box2 minX
        or box1[0] > box2[2]  # box1 minX > box2 maxX
        or box1[3] < box2[1]  # box1 maxY < box2 minY
        or box1[1] > box2[3]  # box1 minY > box2 maxY
    )


class MockSatelliteProvider(SatelliteProvider):
    """Deterministic offline satellite provider for testing and disconnected demo mode."""

    def __init__(
        self,
        *,
        scenes: list[SatelliteScene] | None = None,
        simulate_failure: Literal["timeout", "unavailable", "invalid_response", "empty"]
        | None = None,
    ) -> None:
        self._scenes = scenes if scenes is not None else list(SYNTHETIC_SCENES)
        self.simulate_failure = simulate_failure

    @property
    def provider_id(self) -> str:
        return "mock"

    @property
    def display_name(self) -> str:
        return "Mock Satellite Provider (Offline Synthetic)"

    @property
    def mode(self) -> ProviderMode:
        return ProviderMode.MOCK

    @property
    def capabilities(self) -> list[ProviderCapability]:
        return [
            ProviderCapability.SCENE_SEARCH,
            ProviderCapability.SCENE_METADATA,
            ProviderCapability.SCENE_PREVIEW,
            ProviderCapability.OPTICAL_IMAGERY,
            ProviderCapability.SAR_IMAGERY,
            ProviderCapability.SPECTRAL_PROCESSING,
            ProviderCapability.CHANGE_DETECTION,
        ]

    def is_configured(self) -> bool:
        return True

    async def health_check(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            provider_type="satellite",
            mode=self.mode,
            status=ProviderStatus.READY,
            capabilities=self.capabilities,
            configured=True,
            healthy=True,
            data_origin=DataOrigin.MOCK,
            last_checked_at=datetime.now(UTC),
            message="Mock satellite provider is ready for offline operation.",
            limitations=[
                "Synthetic scene data only",
                "Does not connect to external satellite constellations",
            ],
            metadata={"synthetic_scene_count": len(self._scenes)},
        )

    async def search_scenes(self, request: SceneSearchRequest) -> SceneSearchResponse:
        start_time = datetime.now(UTC)

        # Handle test failure simulations
        if self.simulate_failure == "timeout":
            raise ProviderTimeoutError(self.provider_id)
        if self.simulate_failure == "unavailable":
            raise ProviderUnavailableError(self.provider_id)
        if self.simulate_failure == "invalid_response":
            raise InvalidProviderResponseError(self.provider_id)
        if self.simulate_failure == "empty":
            return SceneSearchResponse(
                request_id=f"mock-req-{uuid4().hex[:8]}",
                scenes=[],
                total_matched=0,
                returned_count=0,
                next_cursor=None,
                provider_id=self.provider_id,
                execution=ProviderExecutionMetadata(
                    provider_id=self.provider_id,
                    provider_mode=self.mode,
                    data_origin=DataOrigin.MOCK,
                    requested_at=start_time,
                    completed_at=datetime.now(UTC),
                    duration_milliseconds=5,
                    attempt_count=1,
                    limitations=["Deterministic synthetic data"],
                ),
                data_origin=DataOrigin.MOCK,
            )

        # Apply filtering
        filtered: list[SatelliteScene] = []
        request_bbox = request.aoi.bbox
        if request_bbox is None:
            # Derive bounding box from coordinates if not provided
            all_lons = [p[0] for ring in request.aoi.coordinates for p in ring]
            all_lats = [p[1] for ring in request.aoi.coordinates for p in ring]
            request_bbox = (min(all_lons), min(all_lats), max(all_lons), max(all_lats))

        for scene in self._scenes:
            # 1. AOI bounding box intersection
            if not _bboxes_intersect(request_bbox, scene.bbox):
                continue

            # 2. Cloud cover ceiling
            if scene.cloud_cover is not None and scene.cloud_cover > request.max_cloud_cover:
                continue

            # 3. Collection filter
            if request.collections and scene.collection not in request.collections:
                continue

            # 4. Sensor type filter
            if request.sensor_types and scene.sensor_type not in request.sensor_types:
                continue

            # 5. Date range filter
            if request.date_range:
                scene_date_str = scene.acquisition_time.strftime("%Y-%m-%d")
                if (
                    scene_date_str < request.date_range.start_date
                    or scene_date_str > request.date_range.end_date
                ):
                    continue

            # 6. Required bands
            if request.required_bands:
                if not all(band in scene.available_bands for band in request.required_bands):
                    continue

            filtered.append(scene)

        # Sort deterministic
        filtered.sort(
            key=lambda s: s.acquisition_time,
            reverse=(request.sort_order == "desc"),
        )

        total_matched = len(filtered)
        paged_scenes = filtered[: request.limit]
        completed_time = datetime.now(UTC)

        return SceneSearchResponse(
            request_id=f"mock-req-{uuid4().hex[:8]}",
            scenes=paged_scenes,
            total_matched=total_matched,
            returned_count=len(paged_scenes),
            next_cursor=None,
            provider_id=self.provider_id,
            execution=ProviderExecutionMetadata(
                provider_id=self.provider_id,
                provider_mode=self.mode,
                data_origin=DataOrigin.MOCK,
                requested_at=start_time,
                completed_at=completed_time,
                duration_milliseconds=max(
                    1, int((completed_time - start_time).total_seconds() * 1000)
                ),
                attempt_count=1,
                limitations=["Deterministic synthetic data for offline testing"],
            ),
            data_origin=DataOrigin.MOCK,
        )

    async def get_scene(self, scene_id: str) -> SatelliteScene:
        for scene in self._scenes:
            if scene.id == scene_id:
                return scene
        raise SceneNotFoundError(scene_id)
