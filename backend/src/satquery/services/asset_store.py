"""Temporary storage and cache service for retrieved imagery and raster assets."""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from satquery.api.schemas.imagery import (
    ImageryAsset,
    ImageryFormat,
    ImageryProductType,
    RasterMetadata,
    VisualizationPreset,
)
from satquery.api.schemas.providers import DataOrigin

logger = logging.getLogger(__name__)


class AssetStoreError(RuntimeError):
    """Base error for asset store failures."""

    def __init__(self, code: str, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class AssetNotFoundError(AssetStoreError):
    def __init__(self, asset_id: str) -> None:
        super().__init__(
            "IMAGERY_ASSET_NOT_FOUND", f"Asset '{asset_id}' not found.", status_code=404
        )


class AssetExpiredError(AssetStoreError):
    def __init__(self, asset_id: str) -> None:
        super().__init__(
            "IMAGERY_ASSET_EXPIRED", f"Asset '{asset_id}' has expired.", status_code=410
        )


@dataclass(slots=True)
class StoredAssetRecord:
    asset: ImageryAsset
    file_path: Path
    raster_metadata: RasterMetadata | None = None


class AssetStore:
    """Thread-safe bounded on-disk asset store with TTL expiration and index."""

    def __init__(
        self,
        storage_dir: Path | str = "tmp/imagery_assets",
        default_ttl_seconds: int = 1800,
        max_bytes: int = 100 * 1024 * 1024,
    ) -> None:
        self.storage_dir = Path(storage_dir).resolve()
        self.default_ttl_seconds = default_ttl_seconds
        self.max_bytes = max_bytes
        self._lock = threading.Lock()
        self._assets: dict[str, StoredAssetRecord] = {}
        self._cache_keys: dict[str, str] = {}  # cache_key -> asset_id
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def generate_cache_key(
        self,
        *,
        provider_id: str,
        scene_id: str,
        aoi_fingerprint: str,
        product_type: str,
        preset: str | None,
        format_type: str,
        width: int | None,
        height: int | None,
        resolution_meters: float | None,
    ) -> str:
        """Create a deterministic SHA-256 cache fingerprint from normalized query attributes."""
        parts = [
            provider_id,
            scene_id,
            aoi_fingerprint,
            product_type,
            str(preset or "default"),
            format_type,
            str(width or "auto"),
            str(height or "auto"),
            str(resolution_meters or "auto"),
        ]
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_by_cache_key(self, cache_key: str) -> StoredAssetRecord | None:
        """Retrieve non-expired stored asset by its request cache key."""
        with self._lock:
            asset_id = self._cache_keys.get(cache_key)
            if not asset_id:
                return None
            record = self._assets.get(asset_id)
            if not record:
                self._cache_keys.pop(cache_key, None)
                return None
            if record.asset.expires_at and record.asset.expires_at < datetime.now(UTC):
                self._remove_asset_unlocked(asset_id)
                return None
            return record

    def save_asset(
        self,
        *,
        scene_id: str,
        product_type: ImageryProductType,
        format_type: ImageryFormat,
        content_type: str,
        width: int,
        height: int,
        resolution_meters: float,
        bbox: tuple[float, float, float, float],
        crs: str,
        data: bytes,
        provider_id: str,
        data_origin: DataOrigin = DataOrigin.REAL,
        bands: list[str] | None = None,
        visualization_preset: VisualizationPreset | None = None,
        ttl_seconds: int | None = None,
        cache_key: str | None = None,
        raster_metadata: RasterMetadata | None = None,
        processing_metadata: dict[str, Any] | None = None,
        asset_id: str | None = None,
        warnings: list[Any] | None = None,
    ) -> ImageryAsset:
        """Atomically persist asset bytes to disk and register in the store."""
        with self._lock:
            self._cleanup_expired_unlocked()
            now = datetime.now(UTC)
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
            expires_at = now + timedelta(seconds=ttl)

            assigned_asset_id = asset_id or f"img-{uuid4().hex[:16]}"
            checksum = hashlib.sha256(data).hexdigest()
            ext = format_type.value
            if format_type in {ImageryFormat.GEOTIFF, ImageryFormat.COG}:
                ext = "tif"

            import re

            sanitized_id = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", assigned_asset_id)
            safe_filename = f"{sanitized_id}.{ext}"
            file_path = (self.storage_dir / safe_filename).resolve()

            # Verify resolved path is strictly within storage directory (prevent path traversal)
            if not file_path.is_relative_to(self.storage_dir):
                raise AssetStoreError("SECURITY_ERROR", "Path traversal detected in asset storage.")

            # Write file atomically
            temp_path = file_path.with_suffix(f".tmp-{uuid4().hex[:8]}")
            try:
                temp_path.write_bytes(data)
                temp_path.replace(file_path)
            except Exception as exc:
                if temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                raise AssetStoreError(
                    "ASSET_WRITE_FAILED", f"Failed to write asset data: {exc}"
                ) from exc

            display_url = f"/api/v1/imagery/assets/{assigned_asset_id}"
            metadata_url = f"/api/v1/imagery/assets/{assigned_asset_id}/metadata"
            download_url = (
                f"/api/v1/imagery/assets/{assigned_asset_id}?download=true"
                if product_type == ImageryProductType.ANALYSIS_RASTER
                else None
            )

            asset = ImageryAsset(
                asset_id=assigned_asset_id,
                scene_id=scene_id,
                product_type=product_type,
                format=format_type,
                content_type=content_type,
                width=width,
                height=height,
                resolution_meters=resolution_meters,
                bbox=bbox,
                crs=crs,
                bands=bands or [],
                size_bytes=len(data),
                checksum=checksum,
                created_at=now,
                expires_at=expires_at,
                data_origin=data_origin,
                provider_id=provider_id,
                visualization_preset=visualization_preset,
                display_url=display_url,
                metadata_url=metadata_url,
                download_url=download_url,
                warnings=warnings or [],
                processing_metadata=processing_metadata or {},
            )

            record = StoredAssetRecord(
                asset=asset,
                file_path=file_path,
                raster_metadata=raster_metadata,
            )
            self._assets[assigned_asset_id] = record
            if cache_key:
                self._cache_keys[cache_key] = assigned_asset_id

            return asset

    def asset_exists(self, asset_id: str) -> bool:
        """Check if asset exists and has not expired."""
        with self._lock:
            record = self._assets.get(asset_id)
            if not record:
                return False
            if record.asset.expires_at and record.asset.expires_at < datetime.now(UTC):
                return False
            return record.file_path.exists()

    def get_asset(self, asset_id: str) -> StoredAssetRecord:
        """Retrieve stored asset record by ID, raising if expired or not found."""
        with self._lock:
            record = self._assets.get(asset_id)
            if not record:
                raise AssetNotFoundError(asset_id)
            if record.asset.expires_at and record.asset.expires_at < datetime.now(UTC):
                self._remove_asset_unlocked(asset_id)
                raise AssetExpiredError(asset_id)
            if not record.file_path.exists():
                self._remove_asset_unlocked(asset_id)
                raise AssetNotFoundError(asset_id)
            return record

    def get_asset_bytes(self, asset_id: str) -> tuple[bytes, str, ImageryAsset]:
        """Get the raw bytes, media type, and asset descriptor for an asset."""
        record = self.get_asset(asset_id)
        try:
            data = record.file_path.read_bytes()
            return data, record.asset.content_type, record.asset
        except Exception as exc:
            raise AssetStoreError(
                "ASSET_READ_FAILED", f"Failed to read asset from disk: {exc}"
            ) from exc

    def _remove_asset_unlocked(self, asset_id: str) -> None:
        record = self._assets.pop(asset_id, None)
        if record and record.file_path.exists():
            try:
                record.file_path.unlink(missing_ok=True)
            except Exception as err:
                logger.warning("Failed to delete expired asset file %s: %s", record.file_path, err)
        # Clean cache keys referencing this asset
        stale_keys = [k for k, v in self._cache_keys.items() if v == asset_id]
        for k in stale_keys:
            self._cache_keys.pop(k, None)

    def _cleanup_expired_unlocked(self) -> None:
        now = datetime.now(UTC)
        expired_ids = [
            asset_id
            for asset_id, record in self._assets.items()
            if record.asset.expires_at and record.asset.expires_at < now
        ]
        for asset_id in expired_ids:
            self._remove_asset_unlocked(asset_id)

    def clear(self) -> None:
        """Purge all stored assets and files in the storage directory."""
        with self._lock:
            for record in self._assets.values():
                if record.file_path.exists():
                    record.file_path.unlink(missing_ok=True)
            self._assets.clear()
            self._cache_keys.clear()
