from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, Response

from satquery.api.dependencies import get_imagery_tile_service
from satquery.api.routes.catalog import _raise_provider_error
from satquery.api.schemas.viewer import TileMetadata, TileMetadataRequest
from satquery.core.errors import ApiError
from satquery.providers.catalog import CatalogueProviderError
from satquery.tiles import ImageryTileService, TileServiceError

router = APIRouter()
TileServiceDependency = Annotated[ImageryTileService, Depends(get_imagery_tile_service)]
TileSetPath = Annotated[UUID, Path()]
TileCoordinatePath = Annotated[int, Path(ge=0)]


def _access_scope(request: Request) -> str:
    # Phase 5C has public catalogue imagery only. A future authenticated provider must
    # replace this with its authorized principal/access-grant scope before cache lookup.
    return f"public:{request.app.state.settings.catalogue_provider}"


def _raise_tile_error(error: TileServiceError) -> NoReturn:
    raise ApiError(
        status_code=error.status_code,
        code=error.code,
        message=str(error),
        retryable=error.retryable,
    ) from error


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
