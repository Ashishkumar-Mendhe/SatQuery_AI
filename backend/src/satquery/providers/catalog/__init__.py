"""Provider-neutral catalogue boundary and Earth Search implementation."""

from satquery.providers.catalog.base import (
    CatalogueCollection,
    CatalogueProvider,
    CatalogueProviderCapabilities,
    CatalogueProviderError,
    QualityRasterMetadata,
    ResolvedImagerySourceSet,
    ResolvedQualityRasterSource,
    ResolvedQualitySourceSet,
    ResolvedRasterSource,
)
from satquery.providers.catalog.earth_search import EarthSearchCatalogueProvider
from satquery.providers.catalog.inpe_sar import InpeSarProvider
from satquery.providers.catalog.nisar_cmr import NisarCmrProvider

__all__ = [
    "CatalogueCollection",
    "CatalogueProvider",
    "CatalogueProviderCapabilities",
    "CatalogueProviderError",
    "EarthSearchCatalogueProvider",
    "InpeSarProvider",
    "NisarCmrProvider",
    "QualityRasterMetadata",
    "ResolvedImagerySourceSet",
    "ResolvedQualityRasterSource",
    "ResolvedQualitySourceSet",
    "ResolvedRasterSource",
]
