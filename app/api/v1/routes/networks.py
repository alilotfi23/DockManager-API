"""
Network management routes: list, inspect, create, remove, connect/disconnect, prune.
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
    NetworkCreate,
    NetworkConnect,
    NetworkDisconnect,
    NetworkResponse,
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


@router.get("", response_model=List[NetworkResponse])
async def list_networks(
    name: str = None,
    current_user: User = Depends(get_current_active_user),
    docker_client = Depends(get_docker_client)
):
    """
    List all networks.
    
    Docker API: GET /networks
    """
    filters = {}
    if name:
        filters["name"] = [name]
    
    networks = await docker_client.list_networks(
        filters=filters if filters else None
    )
    return networks


@router.get("/{network_id}", response_model=NetworkResponse)
async def get_network(
    network_id: str,
    current_user: User = Depends(get_current_active_user),
    docker_client = Depends(get_docker_client)
):
    """
    Get detailed information about a network.
    
    Docker API: GET /networks/{id}
    """
    try:
        network = await docker_client.get_network(network_id)
        return network
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network {network_id} not found"
        )


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_network(
    network_data: NetworkCreate,
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Create a new network.
    
    Docker API: POST /networks/create
    """
    config = {
        "Name": network_data.name,
        "Driver": network_data.driver,
    }
    
    if network_data.internal:
        config["Internal"] = True
    
    if network_data.labels:
        config["Labels"] = network_data.labels
    
    # IPAM configuration
    if network_data.subnet or network_data.gateway or network_data.ip_range:
        config["IPAM"] = {
            "Config": []
        }
        ipam_config = {}
        if network_data.subnet:
            ipam_config["Subnet"] = network_data.subnet
        if network_data.gateway:
            ipam_config["Gateway"] = network_data.gateway
        if network_data.ip_range:
            ipam_config["IPRange"] = network_data.ip_range
        config["IPAM"]["Config"].append(ipam_config)
    
    try:
        network = await docker_client.create_network(config)
        logger.info("Network created", network_name=network_data.name, user_id=current_user.id)
        return {"message": f"Network {network_data.name} created", "network": network}
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


@router.delete("/{network_id}", response_model=MessageResponse)
async def remove_network(
    network_id: str,
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Remove a network.
    
    Docker API: DELETE /networks/{id}
    """
    try:
        await docker_client.remove_network(network_id)
        logger.info("Network removed", network_id=network_id, user_id=current_user.id)
        return {"message": f"Network {network_id} removed"}
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network {network_id} not found"
        )
    except DockerConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.post("/{network_id}/connect", response_model=MessageResponse)
async def connect_network(
    network_id: str,
    connect_data: NetworkConnect,
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Connect a container to a network.
    
    Docker API: POST /networks/{id}/connect
    """
    config = {
        "Container": connect_data.container
    }
    
    if connect_data.endpoint_config:
        config["EndpointConfig"] = connect_data.endpoint_config
    
    try:
        await docker_client.connect_network(network_id, config)
        logger.info(
            "Container connected to network",
            network_id=network_id,
            container=connect_data.container,
            user_id=current_user.id
        )
        return {"message": f"Container {connect_data.container} connected to network {network_id}"}
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network {network_id} or container {connect_data.container} not found"
        )
    except DockerConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.post("/{network_id}/disconnect", response_model=MessageResponse)
async def disconnect_network(
    network_id: str,
    disconnect_data: NetworkDisconnect,
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Disconnect a container from a network.
    
    Docker API: POST /networks/{id}/disconnect
    """
    config = {
        "Container": disconnect_data.container,
        "Force": disconnect_data.force
    }
    
    try:
        await docker_client.disconnect_network(network_id, config)
        logger.info(
            "Container disconnected from network",
            network_id=network_id,
            container=disconnect_data.container,
            user_id=current_user.id
        )
        return {"message": f"Container {disconnect_data.container} disconnected from network {network_id}"}
    except DockerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network {network_id} or container {disconnect_data.container} not found"
        )
    except DockerConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.post("/prune", response_model=MessageResponse)
async def prune_networks(
    current_user: User = Depends(require_admin),
    docker_client = Depends(get_docker_client)
):
    """
    Remove unused networks.
    
    Docker API: POST /networks/prune
    """
    result = await docker_client.prune_networks()
    logger.info("Networks pruned", user_id=current_user.id, result=result)
    return {
        "message": f"Pruned {len(result.get('NetworksDeleted', []))} networks",
        "details": result
    }
