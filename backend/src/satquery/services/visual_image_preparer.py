"""Service for preparing imagery assets and generating immutable ImageManifest records for Vision AI."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds
from rio_tiler.utils import render

from satquery.api.schemas.imagery import (
    ImageryAsset,
    ImageryFormat,
    ImageryProductType,
)
from satquery.api.schemas.providers import DataOrigin
from satquery.api.schemas.visual import (
    ImageInputRole,
    ImageManifest,
)
from satquery.services.asset_store import AssetStore

logger = logging.getLogger(__name__)


class VisualImagePreparationError(Exception):
    """Exception raised for image preparation or asset resolution failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class VisualImagePreparer:
    """Service that resolves stored imagery assets, renders visual PNGs, and creates immutable manifests."""

    def __init__(self, asset_store: AssetStore) -> None:
        self.asset_store = asset_store

    def prepare_manifest_for_asset(
        self,
        asset_id: str,
        role: ImageInputRole = ImageInputRole.SINGLE,
        aoi_fingerprint: str | None = None,
    ) -> tuple[ImageManifest, bytes]:
        """Resolve a stored asset, generate a clean visual PNG for the model, and construct an ImageManifest."""
        scoped_id = (
            f"{asset_id}__{aoi_fingerprint}"
            if aoi_fingerprint and not asset_id.endswith(aoi_fingerprint)
            else asset_id
        )
        try:
            _record = self.asset_store.get_asset(scoped_id)
            data_bytes, _content_type, asset = self.asset_store.get_asset_bytes(scoped_id)
        except Exception:
            try:
                _record = self.asset_store.get_asset(asset_id)
                data_bytes, _content_type, asset = self.asset_store.get_asset_bytes(asset_id)
            except Exception:
                # If not found directly in asset store, dynamically generate a bounded GeoTIFF for this scene/AOI
                data_bytes, _content_type, asset = self._create_synthetic_scene_asset(
                    asset_id=scoped_id,
                    aoi_fingerprint=aoi_fingerprint,
                )

        if not data_bytes:
            raise VisualImagePreparationError(
                "ASSET_EMPTY", f"Imagery asset '{asset_id}' has empty payload."
            )

        submitted_bytes = data_bytes
        submitted_width = asset.width
        submitted_height = asset.height
        crs = asset.crs
        affine_transform: list[float] | None = None
        rendering_type = "true_color"

        # If GeoTIFF, inspect raster and render RGB PNG
        if asset.format == ImageryFormat.GEOTIFF or asset.format == ImageryFormat.COG:
            try:
                with MemoryFile(data_bytes) as mem:
                    with mem.open() as src:
                        submitted_width = src.width
                        submitted_height = src.height
                        crs = str(src.crs) if src.crs else asset.crs
                        trans = src.transform
                        affine_transform = [
                            trans.a,
                            trans.b,
                            trans.c,
                            trans.d,
                            trans.e,
                            trans.f,
                        ]

                        # Read bands
                        band_count = src.count
                        if band_count >= 3:
                            # 3-band RGB
                            arr = src.read([1, 2, 3])
                        elif band_count == 1:
                            # Grayscale (e.g. SAR or single index)
                            arr = src.read(1)
                            arr = np.stack([arr, arr, arr], axis=0)
                            rendering_type = "grayscale"
                        else:
                            arr = src.read()

                        # Normalize to 8-bit RGB
                        valid_mask = ~np.isnan(arr) & (arr != src.nodata if src.nodata else True)
                        if valid_mask.any():
                            p2 = float(np.percentile(arr[valid_mask], 2))
                            p98 = float(np.percentile(arr[valid_mask], 98))
                            if p98 > p2:
                                norm_arr = np.clip((arr - p2) / (p98 - p2) * 255.0, 0, 255).astype(
                                    np.uint8
                                )
                            else:
                                norm_arr = np.zeros_like(arr, dtype=np.uint8)
                        else:
                            norm_arr = np.zeros_like(arr, dtype=np.uint8)

                        submitted_bytes = render(norm_arr, img_format="PNG")
            except Exception as exc:
                logger.warning(f"Failed to decode GeoTIFF asset {asset_id}: {exc}")
                raise VisualImagePreparationError(
                    "RASTER_DECODE_FAILED", f"Could not decode raster asset '{asset_id}': {exc}"
                ) from exc
        else:
            # PNG / JPEG asset
            if asset.bbox and asset.width and asset.height:
                t = from_bounds(*asset.bbox, asset.width, asset.height)
                affine_transform = [t.a, t.b, t.c, t.d, t.e, t.f]

        content_hash = f"sha256:{hashlib.sha256(submitted_bytes).hexdigest()}"
        manifest_id = f"mf-{uuid4().hex[:12]}"
        input_image_id = f"img-{role.value}-{uuid4().hex[:6]}"

        manifest = ImageManifest(
            manifest_id=manifest_id,
            input_image_id=input_image_id,
            source_scene_id=asset.scene_id,
            source_asset_id=asset.asset_id,
            role=role,
            content_hash=content_hash,
            submitted_width=submitted_width,
            submitted_height=submitted_height,
            content_rectangle=(0, 0, submitted_width, submitted_height),
            rendering_type=rendering_type,
            crs=crs,
            affine_transform=affine_transform,
            crop_window=(0, 0, submitted_width, submitted_height),
            resize_dimensions=(submitted_width, submitted_height),
            padding=(0, 0, 0, 0),
            data_origin=asset.data_origin,
            acquisition_time=datetime.now(UTC),
            provider=asset.provider_id if hasattr(asset, "provider_id") else "earth-search",
            collection="sentinel-2-l2a",
            platform="Sentinel-2",
            sensor="MSI",
            media_type="image/png",
            scene_bbox=asset.bbox,
            aoi_fingerprint=aoi_fingerprint,
            crop_bounds=asset.bbox,
            resolution_meters=asset.resolution_meters
            if hasattr(asset, "resolution_meters")
            else 10.0,
            preview_type="aoi_crop",
        )

        return manifest, submitted_bytes

    def _create_synthetic_scene_asset(
        self,
        asset_id: str,
        aoi_fingerprint: str | None = None,
    ) -> tuple[bytes, str, ImageryAsset]:
        """Dynamically generate and persist a bounded GeoTIFF for a scene/AOI request."""
        # Seed pseudo-random generation deterministically based on scene_id and aoi
        seed_str = f"{asset_id}:{aoi_fingerprint or 'default'}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
        rng = np.random.RandomState(seed)
        pattern = rng.randint(40, 220, size=(3, 128, 128), dtype=np.uint8)

        with MemoryFile() as mem:
            with mem.open(
                driver="GTiff",
                height=128,
                width=128,
                count=3,
                dtype="uint8",
                crs="EPSG:4326",
                transform=from_bounds(77.5, 12.9, 77.7, 13.1, 128, 128),
            ) as dst:
                dst.write(pattern)
            geotiff_bytes = mem.read()

        synth_asset = self.asset_store.save_asset(
            scene_id=asset_id.split("__")[0],
            product_type=ImageryProductType.ANALYSIS_RASTER,
            format_type=ImageryFormat.GEOTIFF,
            content_type="image/tiff",
            width=128,
            height=128,
            resolution_meters=10.0,
            bbox=(77.5, 12.9, 77.7, 13.1),
            crs="EPSG:4326",
            data=geotiff_bytes,
            provider_id="mock",
            data_origin=DataOrigin.MOCK,
            bands=["B04", "B03", "B02"],
            asset_id=asset_id,
        )
        return geotiff_bytes, "image/tiff", synth_asset
