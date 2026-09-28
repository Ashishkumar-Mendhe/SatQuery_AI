from fastapi import APIRouter

from satquery.api.routes.aoi import router as aoi_router
from satquery.api.routes.catalog import router as catalog_router
from satquery.api.routes.change import router as change_router
from satquery.api.routes.fusion import router as fusion_router
from satquery.api.routes.health import router as health_router
from satquery.api.routes.imagery import router as imagery_router
from satquery.api.routes.preparation import router as preparation_router
from satquery.api.routes.providers import router as providers_router
from satquery.api.routes.query import router as query_router
from satquery.api.routes.reports import router as reports_router
from satquery.api.routes.scenes import router as scenes_router
from satquery.api.routes.spectral import router as spectral_router
from satquery.api.routes.workspaces import router as workspaces_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(workspaces_router)
api_router.include_router(catalog_router, prefix="/catalog", tags=["catalog"])
api_router.include_router(imagery_router, prefix="/imagery", tags=["imagery"])
api_router.include_router(preparation_router)
api_router.include_router(spectral_router, prefix="/spectral")
api_router.include_router(change_router)
api_router.include_router(fusion_router)
api_router.include_router(query_router)
api_router.include_router(reports_router)
api_router.include_router(providers_router, prefix="/providers", tags=["providers"])
api_router.include_router(aoi_router, prefix="/aoi", tags=["aoi"])
api_router.include_router(scenes_router, prefix="/scenes", tags=["scenes"])
