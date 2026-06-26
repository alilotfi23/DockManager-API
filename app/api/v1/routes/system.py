"""
System routes: Docker daemon info, version, disk usage, and global prune.
"""
from fastapi import APIRouter, Depends
from app.api.deps import (
    get_current_active_user,
    require_admin,
    get_docker_client
)
from app.db.models import User
from app.schemas.docker import (
    SystemInfo,
    SystemVersion,
    SystemDF,
    PruneResponse,
    MessageResponse
)
import structlog

logger = structlog.get_logger()
router = APIRouter()


@router.get("/info", response_model=SystemInfo)
async def get_system_info(
    current_user: User = Depends(get_current_active_user),
    docker_client = Depends(get_docker_client)
):
    """
    Get Docker daemon system information.
    
    Returns daemon-level info including version, OS, total containers/images, etc.
    
    Docker API: GET /info
    """
    info = await docker_client.get_system_info()
    return info


@router.get("/version", response_model=SystemVersion)
async def get_system_version(
    current_user: User = Depends(get_current_active_user),
    docker_client = Depends(get_docker_client)
):
    """
    Get Docker version information.
    
    Docker API: GET /version
    """
    version = await docker_client.get_system_version()
    return version


@router.get("/df", response_model=SystemDF)
async def get_disk_usage(
    current_user: User = Depends(get_current_active_user),
    docker_client = Depends(get_docker_client)
):
    """
    Get disk usage breakdown.
    
    Returns space used by images, containers, volumes, and build cache.
    
    Docker API: GET /system/df
    """
    df = await docker_client.get_system_df()
    return df


@router.post("/prune", response_model=PruneResponse)
async def prune_all(
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Prune all unused resources.
    
    Removes unused containers, dangling images, unused volumes, and unused networks.
    
    Docker API: POST /containers/prune, /images/prune, /volumes/prune, /networks/prune
    """
    result = await docker_client.prune_all()
    logger.info("System-wide prune executed", user_id=current_user.id, result=result)
    return result
