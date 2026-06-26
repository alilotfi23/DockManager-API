"""
Image management routes: list, inspect, pull, tag, remove, prune.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from typing import Optional, List
from app.api.deps import (
    get_current_active_user,
    require_admin,
    get_pagination_params,
    get_docker_client
)
from app.db.models import User
from app.schemas.docker import (
    ImagePull,
    ImageTag,
    ImageResponse,
    ImageDetail,
    MessageResponse
)
from app.services.docker_client import (
    DockerNotFoundError,
    DockerBadRequestError
)
import structlog
import json

logger = structlog.get_logger()
router = APIRouter()


@router.get("", response_model=List[ImageResponse])
async def list_images(
    all: bool = Query(False, description="Include intermediate layers"),
    name: Optional[str] = Query(None, description="Filter by image name"),
    pagination: dict = Depends(get_pagination_params),
    current_user: User = Depends(get_current_active_user),
    docker_client = Depends(get_docker_client)
):
    """
    List images with optional filtering and pagination.
    
    - **all**: Include intermediate image layers
    - **name**: Filter by image name
    - **limit**: Maximum number of results
    - **offset**: Number of results to skip
    """
    filters = {}
    if name:
        filters["reference"] = [name]
    
    images = await docker_client.list_images(
        all=all,
        filters=filters if filters else None
    )
    
    # Apply offset manually
    if pagination["offset"] > 0:
        images = images[pagination["offset"]:]
    
    # Apply limit manually
    if pagination["limit"] < len(images):
        images = images[:pagination["limit"]]
    
    return images


@router.get("/{image_id}", response_model=ImageDetail)
async def get_image(
    image_id: str,
    current_user: User = Depends(get_current_active_user),
    docker_client = Depends(get_docker_client)
):
    """
    Get detailed information about an image.
    
    Docker API: GET /images/{id}/json
    """
    try:
        image = await docker_client.get_image(image_id)
        return image
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image {image_id} not found"
        )


@router.post("/pull", response_model=MessageResponse)
async def pull_image(
    pull_data: ImagePull,
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Pull an image from a registry.
    
    Docker API: POST /images/create
    """
    try:
        async def progress_generator():
            async for progress in docker_client.pull_image(
                pull_data.from_image,
                tag=pull_data.tag or "latest",
                platform=pull_data.platform
            ):
                yield f"data: {json.dumps(progress)}\n\n"
        
        logger.info(
            "Image pull started",
            image=pull_data.from_image,
            tag=pull_data.tag,
            user_id=current_user.id
        )
        
        return StreamingResponse(
            progress_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except DockerBadRequestError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/tag", response_model=MessageResponse)
async def tag_image(
    tag_data: ImageTag,
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Tag an image with a new tag.
    
    Docker API: POST /images/{name}/tag
    """
    try:
        await docker_client.tag_image(tag_data.source, tag_data.target)
        logger.info(
            "Image tagged",
            source=tag_data.source,
            target=tag_data.target,
            user_id=current_user.id
        )
        return {"message": f"Image {tag_data.source} tagged as {tag_data.target}"}
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image {tag_data.source} not found"
        )
    except DockerBadRequestError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{image_id}", response_model=MessageResponse)
async def remove_image(
    image_id: str,
    force: bool = Query(False, description="Force removal of image"),
    prune: bool = Query(False, description="Prune parent image if no longer used"),
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Remove an image.
    
    Docker API: DELETE /images/{id}
    """
    try:
        await docker_client.remove_image(image_id, force=force, prune=prune)
        logger.info("Image removed", image_id=image_id, user_id=current_user.id)
        return {"message": f"Image {image_id} removed"}
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image {image_id} not found"
        )
    except DockerBadRequestError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/prune", response_model=MessageResponse)
async def prune_images(
    dangling: bool = Query(True, description="Prune only dangling images"),
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Remove unused images.
    
    Docker API: POST /images/prune
    """
    result = await docker_client.prune_images(dangling=dangling)
    logger.info("Images pruned", user_id=current_user.id, result=result)
    return {
        "message": f"Pruned {len(result.get('ImagesDeleted', []))} images",
        "details": result
    }
