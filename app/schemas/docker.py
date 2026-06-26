"""
Pydantic schemas for Docker resources (containers, images, volumes, networks).
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime


# ==================== Container Schemas ====================

class ContainerCreate(BaseModel):
    """Schema for creating a container."""
    name: str
    image: str
    command: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    ports: Optional[Dict[str, Optional[str]]] = None  # {"80/tcp": None} or {"80/tcp": "8080"}
    volumes: Optional[List[Dict[str, str]]] = None  # [{"source": "/host/path", "target": "/container/path", "type": "bind"}]
    network: Optional[str] = None
    restart_policy: Optional[str] = "unless-stopped"
    labels: Optional[Dict[str, str]] = None


class ContainerUpdate(BaseModel):
    """Schema for updating a container."""
    name: Optional[str] = None
    restart_policy: Optional[str] = None


class ContainerExec(BaseModel):
    """Schema for executing commands in a container."""
    command: List[str]
    working_dir: Optional[str] = None


class ContainerResponse(BaseModel):
    """Schema for container response."""
    id: str
    name: str
    image: str
    status: str
    state: str
    created: datetime
    ports: Optional[Dict[str, Any]] = None
    labels: Optional[Dict[str, str]] = None

    class Config:
        from_attributes = True


class ContainerDetail(ContainerResponse):
    """Detailed container schema with full inspection data."""
    config: Optional[Dict[str, Any]] = None
    host_config: Optional[Dict[str, Any]] = None
    network_settings: Optional[Dict[str, Any]] = None
    mounts: Optional[List[Dict[str, Any]]] = None


# ==================== Image Schemas ====================

class ImagePull(BaseModel):
    """Schema for pulling an image."""
    from_image: str  # e.g., "nginx:latest" or "nginx"
    tag: Optional[str] = "latest"
    platform: Optional[str] = None  # e.g., "linux/amd64"


class ImageTag(BaseModel):
    """Schema for tagging an image."""
    source: str  # image ID or name
    target: str  # new tag (e.g., "nginx:mytag")


class ImageResponse(BaseModel):
    """Schema for image response."""
    id: str
    repository: Optional[str] = None
    tag: Optional[str] = None
    created: datetime
    size: int
    virtual_size: Optional[int] = None

    class Config:
        from_attributes = True


class ImageDetail(ImageResponse):
    """Detailed image schema with full inspection data."""
    architecture: Optional[str] = None
    os: Optional[str] = None
    author: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    repo_tags: Optional[List[str]] = None


# ==================== Volume Schemas ====================

class VolumeCreate(BaseModel):
    """Schema for creating a volume."""
    name: str
    driver: Optional[str] = "local"
    driver_opts: Optional[Dict[str, str]] = None
    labels: Optional[Dict[str, str]] = None


class VolumeResponse(BaseModel):
    """Schema for volume response."""
    name: str
    driver: str
    mountpoint: str
    created_at: Optional[datetime] = None
    status: Optional[Dict[str, Any]] = None
    labels: Optional[Dict[str, str]] = None
    usage_data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# ==================== Network Schemas ====================

class NetworkCreate(BaseModel):
    """Schema for creating a network."""
    name: str
    driver: Optional[str] = "bridge"
    subnet: Optional[str] = None  # e.g., "172.20.0.0/16"
    gateway: Optional[str] = None
    ip_range: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    internal: Optional[bool] = False


class NetworkConnect(BaseModel):
    """Schema for connecting a container to a network."""
    container: str  # container ID or name
    endpoint_config: Optional[Dict[str, Any]] = None  # IPAMConfig, Links, etc.


class NetworkDisconnect(BaseModel):
    """Schema for disconnecting a container from a network."""
    container: str  # container ID or name
    force: Optional[bool] = False


class NetworkResponse(BaseModel):
    """Schema for network response."""
    id: str
    name: str
    driver: str
    scope: str
    internal: bool
    ipam: Optional[Dict[str, Any]] = None
    created: Optional[datetime] = None
    labels: Optional[Dict[str, str]] = None

    class Config:
        from_attributes = True


# ==================== System Schemas ====================

class SystemInfo(BaseModel):
    """Schema for Docker daemon system info."""
    server_version: str
    os: str
    kernel_version: str
    architecture: str
    cpus: int
    memory: int
    containers: int
    containers_running: int
    containers_paused: int
    containers_stopped: int
    images: int
    ncpu: Optional[int] = None
    mem_total: Optional[int] = None


class SystemVersion(BaseModel):
    """Schema for Docker version info."""
    version: str
    api_version: str
    git_commit: str
    go_version: str
    os: str
    arch: str


class SystemDF(BaseModel):
    """Schema for disk usage info."""
    layers_size: int
    images: Optional[List[Dict[str, Any]]] = None
    containers: Optional[List[Dict[str, Any]]] = None
    volumes: Optional[List[Dict[str, Any]]] = None
    build_cache: Optional[List[Dict[str, Any]]] = None


class PruneResponse(BaseModel):
    """Schema for prune operation response."""
    containers_deleted: Optional[List[str]] = None
    space_reclaimed: Optional[int] = None
    images_deleted: Optional[List[str]] = None
    volumes_deleted: Optional[List[str]] = None
    networks_deleted: Optional[List[str]] = None


# ==================== Stats Schemas ====================

class ContainerStats(BaseModel):
    """Schema for container stats."""
    read: datetime
    preread: datetime
    pids_stats: Optional[Dict[str, Any]] = None
    cpu_stats: Optional[Dict[str, Any]] = None
    memory_stats: Optional[Dict[str, Any]] = None
    networks: Optional[Dict[str, Any]] = None


# ==================== Generic Schemas ====================

class MessageResponse(BaseModel):
    """Generic message response."""
    message: str


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper."""
    items: List[Any]
    total: int
    limit: int
    offset: int
