from fastapi import APIRouter

from satquery.api.routes.catalog import router as catalog_router
from satquery.api.routes.geoagent import router as geoagent_router
from satquery.api.routes.health import router as health_router
from satquery.api.routes.imagery import router as imagery_router
from satquery.api.routes.inference import router as inference_router
from satquery.api.routes.nisar import router as nisar_router
from satquery.api.routes.optical_sar import router as optical_sar_router
from satquery.api.routes.processing import router as processing_router
from satquery.api.routes.sar import router as sar_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(catalog_router, prefix="/catalog", tags=["catalog"])
api_router.include_router(imagery_router, prefix="/imagery", tags=["imagery"])
api_router.include_router(processing_router, prefix="/processing", tags=["processing"])
api_router.include_router(inference_router, prefix="/inference", tags=["inference"])
api_router.include_router(sar_router, prefix="/sar", tags=["sar"])
api_router.include_router(nisar_router, prefix="/nisar", tags=["nisar"])
api_router.include_router(optical_sar_router, prefix="/optical-sar", tags=["optical-sar"])
api_router.include_router(geoagent_router, prefix="/geoagent", tags=["geoagent"])
