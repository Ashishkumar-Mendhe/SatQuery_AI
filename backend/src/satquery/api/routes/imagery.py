"""FastAPI routes for satellite imagery retrieval, map previews, and analysis rasters."""

from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, Response

from satquery.api.dependencies import get_imagery_service, get_imagery_tile_service
from satquery.api.routes.catalog import _raise_provider_error
from satquery.api.schemas.imagery import (
    ImageryAsset,
    ImageryRequest,
    RasterMetadata,
    TemporalImageryRequest,
    TemporalImageryResponse,
)
from satquery.api.schemas.viewer import TileMetadata, TileMetadataRequest
from satquery.core.errors import ApiError
from satquery.providers.catalog import CatalogueProviderError
from satquery.services.asset_store import AssetExpiredError, AssetNotFoundError, AssetStoreError
from satquery.services.imagery_service import ImageryProcessingError, ImageryService
from satquery.services.raster_validator import RasterValidationError
from satquery.tiles import ImageryTileService, TileServiceError

router = APIRouter()
TileServiceDependency = Annotated[ImageryTileService, Depends(get_imagery_tile_service)]
ImageryServiceDependency = Annotated[ImageryService, Depends(get_imagery_service)]
TileSetPath = Annotated[UUID, Path()]
TileCoordinatePath = Annotated[int, Path(ge=0)]


def _access_scope(request: Request) -> str:
    return f"public:{request.app.state.settings.catalogue_provider}"


def _raise_tile_error(error: TileServiceError) -> NoReturn:
    raise ApiError(
        status_code=error.status_code,
        code=error.code,
        message=str(error),
        retryable=error.retryable,
    ) from error


# ---------------------------------------------------------------------------
# Phase 3A: Analysis-Grade Imagery Retrieval and Map Previews
# ---------------------------------------------------------------------------


@router.post(
    "/request",
    response_model=ImageryAsset,
    summary="Request single-scene map preview or analysis raster for an AOI",
)
async def request_scene_imagery(
    request: Request,
    payload: ImageryRequest,
    imagery_service: ImageryServiceDependency,
) -> ImageryAsset:
    """Retrieve or generate bounded imagery asset for a selected scene and AOI."""
    provider_mode = request.app.state.settings.satellite_provider_mode
    try:
        return imagery_service.request_imagery(payload, provider_mode=provider_mode)
    except RasterValidationError as err:
        raise ApiError(
            status_code=422,
            code=err.code,
            message=err.message,
            details=err.details,
        ) from err
    except ImageryProcessingError as err:
        raise ApiError(
            status_code=err.status_code,
            code=err.code,
            message=err.message,
        ) from err
    except Exception as exc:
        raise ApiError(
            status_code=500,
            code="IMAGERY_RETRIEVAL_FAILED",
            message=f"Failed to process imagery request: {exc}",
        ) from exc


@router.post(
    "/temporal-request",
    response_model=TemporalImageryResponse,
    summary="Request multitemporal before/after map previews or analysis rasters",
)
async def request_temporal_imagery(
    request: Request,
    payload: TemporalImageryRequest,
    imagery_service: ImageryServiceDependency,
) -> TemporalImageryResponse:
    """Retrieve before and after imagery assets with spatial alignment evaluation."""
    provider_mode = request.app.state.settings.satellite_provider_mode
    try:
        return imagery_service.request_temporal_imagery(payload, provider_mode=provider_mode)
    except RasterValidationError as err:
        raise ApiError(
            status_code=422,
            code=err.code,
            message=err.message,
            details=err.details,
        ) from err
    except ImageryProcessingError as err:
        raise ApiError(
            status_code=err.status_code,
            code=err.code,
            message=err.message,
        ) from err
    except Exception as exc:
        raise ApiError(
            status_code=500,
            code="TEMPORAL_IMAGERY_FAILED",
            message=f"Failed to process multitemporal imagery: {exc}",
        ) from exc


@router.get(
    "/assets/{asset_id}",
    response_class=Response,
    summary="Deliver rendered map preview image or analysis raster dataset",
)
async def get_imagery_asset(
    asset_id: str,
    imagery_service: ImageryServiceDependency,
    download: bool = Query(default=False),
) -> Response:
    """Stream stored imagery asset data with proper content headers."""
    try:
        data, content_type, asset = imagery_service.asset_store.get_asset_bytes(asset_id)
    except AssetNotFoundError as err:
        raise ApiError(status_code=404, code=err.code, message=err.message) from err
    except AssetExpiredError as err:
        raise ApiError(status_code=410, code=err.code, message=err.message) from err
    except AssetStoreError as err:
        raise ApiError(status_code=err.status_code, code=err.code, message=err.message) from err

    headers: dict[str, str] = {
        "Cache-Control": "public, max-age=1800",
        "ETag": f'"{asset.checksum}"',
    }
    if download:
        filename = f"{asset.scene_id}_{asset.product_type.value}.{asset.format.value}"
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    return Response(
        content=data,
        media_type=content_type,
        headers=headers,
    )


@router.get(
    "/assets/{asset_id}/metadata",
    response_model=RasterMetadata,
    summary="Retrieve geospatial and scientific metadata of an imagery asset",
)
async def get_imagery_asset_metadata(
    asset_id: str,
    imagery_service: ImageryServiceDependency,
) -> RasterMetadata:
    """Get metadata for a stored imagery asset."""
    try:
        record = imagery_service.asset_store.get_asset(asset_id)
        if not record.raster_metadata:
            raise ApiError(
                status_code=404,
                code="METADATA_NOT_FOUND",
                message=f"Raster metadata for asset '{asset_id}' is unavailable.",
            )
        return record.raster_metadata
    except AssetNotFoundError as err:
        raise ApiError(status_code=404, code=err.code, message=err.message) from err
    except AssetExpiredError as err:
        raise ApiError(status_code=410, code=err.code, message=err.message) from err


# ---------------------------------------------------------------------------
# Existing Tile Routes
# ---------------------------------------------------------------------------


@router.post(
    "/tile-sets",
    response_model=TileMetadata,
    summary="Resolve a stable catalogue scene into bounded imagery tile metadata",
)
async def create_tile_set(
    request: Request,
    tile_request: TileMetadataRequest,
    tile_service: TileServiceDependency,
) -> TileMetadata:
    if tile_request.scene.provider != request.app.state.settings.catalogue_provider:
        raise ApiError(
            status_code=422,
            code="VALIDATION_FAILED",
            message="The requested catalogue provider is not enabled.",
            details={"field": "scene.provider"},
        )
    try:
        return await tile_service.metadata(tile_request, access_scope=_access_scope(request))
    except CatalogueProviderError as error:
        _raise_provider_error(error)
    except TileServiceError as error:
        _raise_tile_error(error)


@router.get(
    "/tiles/{tile_set_id}/{z}/{x}/{y}.png",
    response_class=Response,
    summary="Render one authorized WebMercatorQuad natural-colour imagery tile",
)
async def get_imagery_tile(
    request: Request,
    tile_set_id: TileSetPath,
    z: TileCoordinatePath,
    x: TileCoordinatePath,
    y: TileCoordinatePath,
    tile_service: TileServiceDependency,
) -> Response:
    try:
        tile = await tile_service.tile(tile_set_id, z, x, y, access_scope=_access_scope(request))
    except TileServiceError as error:
        _raise_tile_error(error)
    return Response(
        content=tile.body,
        media_type=tile.media_type,
        headers={"Cache-Control": "private, max-age=60"},
    )
