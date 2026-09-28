from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Query, Request, status
from pydantic import ValidationError

from satquery.api.dependencies import get_catalogue_provider
from satquery.api.schemas.asset_resolution import (
    AssetResolutionRequest,
    AssetResolutionResponse,
)
from satquery.api.schemas.catalog import (
    CatalogueCollectionsResponse,
    CatalogueCollectionSummary,
    CatalogueScene,
    CatalogueSearchRequest,
    CatalogueSearchResponse,
    CollectionIdentifier,
    ProviderIdentifier,
    ProviderIdentity,
)
from satquery.core.errors import ApiError
from satquery.providers.catalog import CatalogueProvider, CatalogueProviderError

router = APIRouter()
ProviderDependency = Annotated[CatalogueProvider, Depends(get_catalogue_provider)]
ProviderQuery = Annotated[ProviderIdentifier, Query(description="Configured provider identifier")]
CollectionPath = Annotated[CollectionIdentifier, Path()]
ItemPath = Annotated[str, Path(min_length=1, max_length=512)]


def _raise_provider_error(error: CatalogueProviderError, *, item_lookup: bool = False) -> NoReturn:
    if item_lookup and error.upstream_status == status.HTTP_404_NOT_FOUND:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="CATALOGUE_ITEM_NOT_FOUND",
            message="The requested catalogue item was not found.",
        ) from error

    if error.code in {
        "INVALID_CURSOR",
        "INVALID_ITEM_ID",
        "UNSUPPORTED_COLLECTION",
        "UNSUPPORTED_PROVIDER",
    }:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="VALIDATION_FAILED",
            message=error.args[0],
        ) from error
    if error.code in {"UNSUPPORTED_FILTER", "PROVIDER_CAPABILITY_UNAVAILABLE"}:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="CAPABILITY_UNAVAILABLE",
            message=error.args[0],
        ) from error
    if error.code == "PROVIDER_RATE_LIMITED" or error.upstream_status == 429:
        headers = (
            {"Retry-After": str(error.retry_after_seconds)}
            if error.retry_after_seconds is not None
            else None
        )
        raise ApiError(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMITED",
            message="The catalogue provider rate limit was reached.",
            retryable=True,
            headers=headers,
        ) from error
    if error.code == "PROVIDER_TIMEOUT" or error.upstream_status in {408, 504}:
        raise ApiError(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            code="UPSTREAM_TIMEOUT",
            message="The catalogue provider did not respond in time.",
            retryable=True,
        ) from error
    if error.code == "INVALID_PROVIDER_RESPONSE":
        raise ApiError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="UPSTREAM_INVALID_RESPONSE",
            message="The catalogue provider returned an invalid response.",
        ) from error
    raise ApiError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="UPSTREAM_UNAVAILABLE",
        message="The catalogue provider is unavailable.",
        retryable=error.retryable,
    ) from error


def _require_provider(provider_id: str, request: Request) -> None:
    configured = request.app.state.settings.catalogue_provider
    if provider_id != configured:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="VALIDATION_FAILED",
            message="The requested catalogue provider is not enabled.",
            details={"field": "provider"},
        )


@router.get(
    "/collections",
    response_model=CatalogueCollectionsResponse,
    summary="List enabled catalogue collections",
)
async def list_collections(
    request: Request,
    provider: ProviderQuery,
    catalogue_provider: ProviderDependency,
) -> CatalogueCollectionsResponse:
    _require_provider(provider, request)
    try:
        collections = await catalogue_provider.collections()
        items = [
            CatalogueCollectionSummary.model_validate(collection, from_attributes=True)
            for collection in collections
        ]
    except CatalogueProviderError as error:
        _raise_provider_error(error)
    except ValidationError as error:
        raise ApiError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="UPSTREAM_INVALID_RESPONSE",
            message="The catalogue provider returned invalid collection metadata.",
        ) from error
    return CatalogueCollectionsResponse(
        provider=ProviderIdentity(id=provider, name="Earth Search by Element 84"),
        items=items,
        returned_count=len(items),
    )


@router.post(
    "/searches",
    response_model=CatalogueSearchResponse,
    summary="Search configured catalogue metadata",
)
async def search_catalogue(
    request: Request,
    search: CatalogueSearchRequest,
    catalogue_provider: ProviderDependency,
) -> CatalogueSearchResponse:
    _require_provider(search.provider, request)
    try:
        return await catalogue_provider.search(search)
    except CatalogueProviderError as error:
        _raise_provider_error(error)


@router.post(
    "/asset-resolutions",
    response_model=AssetResolutionResponse,
    summary="Resolve a configured catalogue scene into renderable imagery assets",
)
async def resolve_catalogue_asset(
    request: Request,
    resolution: AssetResolutionRequest,
    catalogue_provider: ProviderDependency,
) -> AssetResolutionResponse:
    _require_provider(resolution.scene.provider, request)
    try:
        return await catalogue_provider.resolve_imagery(resolution)
    except CatalogueProviderError as error:
        _raise_provider_error(error)


@router.get(
    "/collections/{collection_id}/items/{item_id}",
    response_model=CatalogueScene,
    summary="Get catalogue item metadata",
)
async def get_catalogue_item(
    request: Request,
    provider: ProviderQuery,
    catalogue_provider: ProviderDependency,
    collection_id: CollectionPath,
    item_id: ItemPath,
) -> CatalogueScene:
    _require_provider(provider, request)
    try:
        return await catalogue_provider.item(collection_id, item_id)
    except CatalogueProviderError as error:
        _raise_provider_error(error, item_lookup=True)
