"""
Container management routes: CRUD, exec, logs, stats, WebSocket logs.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect
from typing import Optional, List
from app.api.deps import (
    get_current_active_user,
    require_admin,
    get_pagination_params,
    get_docker_client
)
from app.db.models import User
from app.schemas.docker import (
    ContainerCreate,
    ContainerUpdate,
    ContainerExec,
    ContainerResponse,
    ContainerDetail,
    ContainerStats,
    MessageResponse
)
from app.services.docker_client import (
    DockerNotFoundError,
    DockerConflictError,
    DockerBadRequestError
)
import structlog
import json

logger = structlog.get_logger()
router = APIRouter()


@router.get("", response_model=List[ContainerResponse])
async def list_containers(
    all: bool = Query(False, description="Include stopped containers"),
    status: Optional[str] = Query(None, description="Filter by status (running, exited, etc.)"),
    name: Optional[str] = Query(None, description="Filter by container name"),
    pagination: dict = Depends(get_pagination_params),
    current_user: User = Depends(get_current_active_user),
    docker_client = Depends(get_docker_client)
):
    """
    List containers with optional filtering and pagination.
    
    - **all**: Include stopped containers
    - **status**: Filter by container status
    - **name**: Filter by container name (partial match)
    - **limit**: Maximum number of results
    - **offset**: Number of results to skip
    """
    filters = {}
    if status:
        filters["status"] = [status]
    if name:
        filters["name"] = [name]
    
    containers = await docker_client.list_containers(
        all=all,
        limit=pagination["limit"],
        filters=filters if filters else None
    )
    
    # Apply offset manually since Docker API doesn't support it
    if pagination["offset"] > 0:
        containers = containers[pagination["offset"]:]
    
    return containers


@router.get("/{container_id}", response_model=ContainerDetail)
async def get_container(
    container_id: str,
    current_user: User = Depends(get_current_active_user),
    docker_client = Depends(get_docker_client)
):
    """
    Get detailed information about a container.
    
    Docker API: GET /containers/{id}/json
    """
    try:
        container = await docker_client.get_container(container_id)
        return container
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found"
        )


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_container(
    container_data: ContainerCreate,
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Create a new container.
    
    Docker API: POST /containers/create
    """
    # Build container config for Docker API
    config = {
        "name": container_data.name,
        "Image": container_data.image,
    }
    
    if container_data.command:
        config["Cmd"] = container_data.command
    
    if container_data.env:
        config["Env"] = [f"{k}={v}" for k, v in container_data.env.items()]
    
    if container_data.ports:
        config["ExposedPorts"] = {port: {} for port in container_data.ports.keys()}
        config["PortBindings"] = {
            port: [{"HostPort": str(host_port)}] if host_port else [{}]
            for port, host_port in container_data.ports.items()
        }
    
    if container_data.volumes:
        config["HostConfig"] = {
            "Binds": [
                f"{vol['source']}:{vol['target']}:{vol.get('type', 'rw')}"
                for vol in container_data.volumes
            ]
        }
    
    if container_data.network:
        config["NetworkingConfig"] = {
            "EndpointsConfig": {
                container_data.network: {}
            }
        }
    
    if container_data.restart_policy:
        if "HostConfig" not in config:
            config["HostConfig"] = {}
        config["HostConfig"]["RestartPolicy"] = {
            "Name": container_data.restart_policy
        }
    
    if container_data.labels:
        config["Labels"] = container_data.labels
    
    try:
        container_id = await docker_client.create_container(config)
        logger.info("Container created", container_id=container_id, user_id=current_user.id)
        return {"message": f"Container created with ID: {container_id}"}
    except DockerBadRequestError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except DockerConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.post("/{container_id}/start", response_model=MessageResponse)
async def start_container(
    container_id: str,
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Start a container.
    
    Docker API: POST /containers/{id}/start
    """
    try:
        await docker_client.start_container(container_id)
        logger.info("Container started", container_id=container_id, user_id=current_user.id)
        return {"message": f"Container {container_id} started"}
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found"
        )
    except DockerConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.post("/{container_id}/stop", response_model=MessageResponse)
async def stop_container(
    container_id: str,
    timeout: int = Query(10, ge=0, le=120, description="Timeout in seconds"),
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Stop a container.
    
    Docker API: POST /containers/{id}/stop
    """
    try:
        await docker_client.stop_container(container_id, timeout=timeout)
        logger.info("Container stopped", container_id=container_id, user_id=current_user.id)
        return {"message": f"Container {container_id} stopped"}
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found"
        )


@router.post("/{container_id}/restart", response_model=MessageResponse)
async def restart_container(
    container_id: str,
    timeout: int = Query(10, ge=0, le=120, description="Timeout in seconds"),
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Restart a container.
    
    Docker API: POST /containers/{id}/restart
    """
    try:
        await docker_client.restart_container(container_id, timeout=timeout)
        logger.info("Container restarted", container_id=container_id, user_id=current_user.id)
        return {"message": f"Container {container_id} restarted"}
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found"
        )


@router.delete("/{container_id}", response_model=MessageResponse)
async def remove_container(
    container_id: str,
    force: bool = Query(False, description="Force removal of running container"),
    remove_volumes: bool = Query(False, description="Remove associated volumes"),
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Remove a container.
    
    Docker API: DELETE /containers/{id}
    """
    try:
        await docker_client.remove_container(
            container_id,
            force=force,
            remove_volumes=remove_volumes
        )
        logger.info("Container removed", container_id=container_id, user_id=current_user.id)
        return {"message": f"Container {container_id} removed"}
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found"
        )
    except DockerConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.post("/{container_id}/exec", response_model=MessageResponse)
async def exec_container(
    container_id: str,
    exec_data: ContainerExec,
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Execute a command inside a running container.
    
    Docker API: POST /containers/{id}/exec, POST /exec/{id}/start
    """
    try:
        # Create exec instance
        exec_id = await docker_client.exec_create(
            container_id,
            exec_data.command,
            working_dir=exec_data.working_dir
        )
        
        # Start exec and get output
        output = await docker_client.exec_start(exec_id)
        
        logger.info("Command executed in container", container_id=container_id, user_id=current_user.id)
        return {"message": f"Command executed. Output: {output}"}
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found"
        )
    except DockerBadRequestError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{container_id}/logs")
async def get_container_logs(
    container_id: str,
    tail: Optional[int] = Query(None, ge=0, description="Number of lines to show from end"),
    since: Optional[int] = Query(None, ge=0, description="Unix timestamp to show logs since"),
    current_user: User = Depends(get_current_active_user),
    docker_client = Depends(get_docker_client)
):
    """
    Get container logs (non-streaming).
    
    Docker API: GET /containers/{id}/logs
    """
    try:
        logs = []
        async for line in docker_client.get_container_logs(
            container_id,
            tail=tail,
            since=since,
            follow=False
        ):
            logs.append(line)
        
        return {"logs": logs}
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found"
        )


@router.get("/{container_id}/logs/stream")
async def stream_container_logs(
    container_id: str,
    tail: Optional[int] = Query(None, ge=0, description="Number of lines to show from end"),
    since: Optional[int] = Query(None, ge=0, description="Unix timestamp to show logs since"),
    current_user: User = Depends(get_current_active_user),
    docker_client = Depends(get_docker_client)
):
    """
    Stream container logs in real-time using Server-Sent Events.
    
    Docker API: GET /containers/{id}/logs?follow=true
    """
    try:
        async def log_generator():
            async for line in docker_client.get_container_logs(
                container_id,
                tail=tail,
                since=since,
                follow=True
            ):
                yield f"data: {line}\n\n"
        
        return StreamingResponse(
            log_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found"
        )


@router.websocket("/{container_id}/logs/ws")
async def websocket_container_logs(
    websocket: WebSocket,
    container_id: str,
    docker_client = Depends(get_docker_client)
):
    """
    WebSocket endpoint for streaming container logs.
    
    Alternative to HTTP streaming for clients that prefer WebSocket.
    """
    await websocket.accept()
    
    try:
        async for line in docker_client.get_container_logs(
            container_id,
            follow=True
        ):
            await websocket.send_text(line)
    except DockerNotFoundError:
        await websocket.send_json({"error": f"Container {container_id} not found"})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", container_id=container_id)
    except Exception as e:
        logger.error("WebSocket error", container_id=container_id, error=str(e))
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()


@router.get("/{container_id}/stats")
async def get_container_stats(
    container_id: str,
    stream: bool = Query(False, description="Stream stats continuously"),
    current_user: User = Depends(get_current_active_user),
    docker_client = Depends(get_docker_client)
):
    """
    Get container resource usage stats (CPU, memory, network I/O).
    
    Docker API: GET /containers/{id}/stats
    """
    try:
        if stream:
            async def stats_generator():
                async for stats in docker_client.get_container_stats(container_id, stream=True):
                    yield f"data: {json.dumps(stats)}\n\n"
            
            return StreamingResponse(
                stats_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        else:
            # Get single snapshot
            stats_list = []
            async for stats in docker_client.get_container_stats(container_id, stream=False):
                stats_list.append(stats)
            
            return stats_list[0] if stats_list else {}
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found"
        )


@router.post("/prune", response_model=MessageResponse)
async def prune_containers(
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Remove all stopped containers.
    
    Docker API: POST /containers/prune
    """
    result = await docker_client.prune_containers()
    logger.info("Containers pruned", user_id=current_user.id, result=result)
    return {
        "message": f"Pruned {len(result.get('ContainersDeleted', []))} containers",
        "details": result
    }
