"""
Volume management routes: list, inspect, create, remove, prune.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.api.deps import (
    get_current_active_user,
    require_admin,
    get_docker_client
)
from app.db.models import User
from app.schemas.docker import (
    VolumeCreate,
    VolumeResponse,
    MessageResponse
)
from app.services.docker_client import (
    DockerNotFoundError,
    DockerConflictError,
    DockerBadRequestError
)
import structlog

logger = structlog.get_logger()
router = APIRouter()


@router.get("", response_model=List[VolumeResponse])
async def list_volumes(
    current_user: User = Depends(get_current_active_user),
    docker_client = Depends(get_docker_client)
):
    """
    List all volumes.
    
    Docker API: GET /volumes
    """
    result = await docker_client.list_volumes()
    return result.get("Volumes", [])


@router.get("/{volume_name}", response_model=VolumeResponse)
async def get_volume(
    volume_name: str,
    current_user: User = Depends(get_current_active_user),
    docker_client = Depends(get_docker_client)
):
    """
    Get detailed information about a volume.
    
    Docker API: GET /volumes/{name}
    """
    try:
        volume = await docker_client.get_volume(volume_name)
        return volume
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Volume {volume_name} not found"
        )


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_volume(
    volume_data: VolumeCreate,
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Create a new volume.
    
    Docker API: POST /volumes/create
    """
    config = {
        "Name": volume_data.name,
        "Driver": volume_data.driver,
    }
    
    if volume_data.driver_opts:
        config["DriverOpts"] = volume_data.driver_opts
    
    if volume_data.labels:
        config["Labels"] = volume_data.labels
    
    try:
        volume = await docker_client.create_volume(config)
        logger.info("Volume created", volume_name=volume_data.name, user_id=current_user.id)
        return {"message": f"Volume {volume_data.name} created", "volume": volume}
    except DockerConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except DockerBadRequestError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{volume_name}", response_model=MessageResponse)
async def remove_volume(
    volume_name: str,
    force: bool = False,
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Remove a volume.
    
    Docker API: DELETE /volumes/{name}
    """
    try:
        await docker_client.remove_volume(volume_name, force=force)
        logger.info("Volume removed", volume_name=volume_name, user_id=current_user.id)
        return {"message": f"Volume {volume_name} removed"}
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Volume {volume_name} not found"
        )
    except DockerConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.post("/prune", response_model=MessageResponse)
async def prune_volumes(
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Remove unused volumes.
    
    Docker API: POST /volumes/prune
    """
    result = await docker_client.prune_volumes()
    logger.info("Volumes pruned", user_id=current_user.id, result=result)
    return {
        "message": f"Pruned {len(result.get('VolumesDeleted', []))} volumes",
        "details": result
    }
