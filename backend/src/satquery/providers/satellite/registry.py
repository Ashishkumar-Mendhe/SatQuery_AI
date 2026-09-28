"""Registry and factory for satellite imagery providers."""

from __future__ import annotations

from typing import Any

from satquery.api.schemas.analysis import AnalysisWarning, WarningCode, WarningSeverity
from satquery.api.schemas.providers import (
    DataOrigin,
    ProviderInfo,
    ProviderMode,
    ProviderStatus,
)
from satquery.core.config import Settings
from satquery.core.logging import get_logger
from satquery.providers.satellite.base import (
    ProviderUnavailableError,
    SatelliteProvider,
    SceneSearchRequest,
    SceneSearchResponse,
)
from satquery.providers.satellite.mock import MockSatelliteProvider
from satquery.providers.satellite.real_adapter import RealSatelliteProviderAdapter

logger = get_logger(__name__)


class DisabledSatelliteProvider(SatelliteProvider):
    """Placeholder provider used when satellite discovery is explicitly disabled."""

    @property
    def provider_id(self) -> str:
        return "disabled"

    @property
    def display_name(self) -> str:
        return "Disabled Satellite Provider"

    @property
    def mode(self) -> ProviderMode:
        return ProviderMode.DISABLED

    @property
    def capabilities(self) -> list[Any]:
        return []

    def is_configured(self) -> bool:
        return False

    async def health_check(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id="disabled",
            display_name="Disabled Satellite Provider",
            provider_type="satellite",
            mode=ProviderMode.DISABLED,
            status=ProviderStatus.DISABLED,
            capabilities=[],
            configured=False,
            healthy=False,
            data_origin=DataOrigin.MOCK,
            message="Satellite discovery is disabled in current configuration.",
        )

    async def search_scenes(self, request: SceneSearchRequest) -> SceneSearchResponse:
        raise ProviderUnavailableError("disabled", "Satellite discovery is disabled.")

    async def get_scene(self, scene_id: str) -> Any:
        raise ProviderUnavailableError("disabled", "Satellite discovery is disabled.")


class SatelliteProviderRegistry:
    """Manages active satellite providers and controlled fallback."""

    def __init__(
        self,
        *,
        primary_provider: SatelliteProvider,
        mock_provider: SatelliteProvider | None = None,
        allow_fallback: bool = True,
    ) -> None:
        self.primary_provider = primary_provider
        self.mock_provider = mock_provider or MockSatelliteProvider()
        self.allow_fallback = allow_fallback

    @classmethod
    def from_settings(cls, settings: Settings) -> SatelliteProviderRegistry:
        mode = settings.satellite_provider_mode
        primary: SatelliteProvider
        if mode == "disabled":
            primary = DisabledSatelliteProvider()
        elif mode == "mock":
            primary = MockSatelliteProvider()
        else:
            primary = RealSatelliteProviderAdapter.from_settings(settings)

        return cls(
            primary_provider=primary,
            mock_provider=MockSatelliteProvider(),
            allow_fallback=settings.allow_mock_fallback,
        )

    async def health_check(self) -> ProviderInfo:
        return await self.primary_provider.health_check()

    async def search_scenes(self, request: SceneSearchRequest) -> SceneSearchResponse:
        try:
            return await self.primary_provider.search_scenes(request)
        except Exception as exc:
            if not self.allow_fallback:
                logger.error(
                    "satellite_provider_search_failed_no_fallback",
                    extra={"provider": self.primary_provider.provider_id, "error": str(exc)},
                )
                raise

            logger.warning(
                "satellite_provider_search_failed_using_mock_fallback",
                extra={"provider": self.primary_provider.provider_id, "error": str(exc)},
            )
            # Execute through mock provider and tag execution metadata
            mock_resp = await self.mock_provider.search_scenes(request)
            mock_resp.data_origin = DataOrigin.FALLBACK
            mock_resp.execution.data_origin = DataOrigin.FALLBACK
            mock_resp.execution.fallback_used = True
            mock_resp.execution.fallback_reason = (
                f"Primary provider '{self.primary_provider.provider_id}' failed: {exc!s}"
            )
            mock_resp.warnings.append(
                AnalysisWarning(
                    code=WarningCode.MOCK_DATA_USED,
                    severity=WarningSeverity.MEDIUM,
                    title="Mock Fallback Data Used",
                    message=(
                        "Satellite imagery search fell back to synthetic data because "
                        f"primary provider '{self.primary_provider.provider_id}' was unavailable."
                    ),
                    suggested_action="Verify provider credentials or network connectivity.",
                )
            )
            return mock_resp

    async def aclose(self) -> None:
        await self.primary_provider.aclose()
        await self.mock_provider.aclose()
