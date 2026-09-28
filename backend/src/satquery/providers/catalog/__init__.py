"""Provider-neutral catalogue boundary and Earth Search implementation."""

from satquery.providers.catalog.base import (
    CatalogueCollection,
    CatalogueProvider,
    CatalogueProviderCapabilities,
    CatalogueProviderError,
    ResolvedImagerySourceSet,
    ResolvedRasterSource,
)
from satquery.providers.catalog.earth_search import EarthSearchCatalogueProvider

__all__ = [
    "CatalogueCollection",
    "CatalogueProvider",
    "CatalogueProviderCapabilities",
    "CatalogueProviderError",
    "EarthSearchCatalogueProvider",
    "ResolvedImagerySourceSet",
    "ResolvedRasterSource",
]
