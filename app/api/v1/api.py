"""
API v1 router aggregator.
Combines all v1 route modules under a single router with /api/v1 prefix.
"""
from fastapi import APIRouter
from app.api.v1.routes import auth, containers, images, volumes, networks, system

api_router = APIRouter()

# Include all route modules
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(containers.router, prefix="/containers", tags=["Containers"])
api_router.include_router(images.router, prefix="/images", tags=["Images"])
api_router.include_router(volumes.router, prefix="/volumes", tags=["Volumes"])
api_router.include_router(networks.router, prefix="/networks", tags=["Networks"])
api_router.include_router(system.router, prefix="/system", tags=["System"])
