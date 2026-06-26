"""
Docker Engine API client using httpx with Unix socket transport.
This module wraps all Docker Engine REST API calls without using the Docker SDK.
"""
import httpx
import json
from typing import Optional, Dict, List, Any, AsyncGenerator
from urllib.parse import quote
from app.core.config import settings
import structlog

logger = structlog.get_logger()


class DockerUnixSocketTransport(httpx.AsyncBaseTransport):
    """
    Custom httpx transport for Unix socket communication.
    Handles http+unix:// URLs for Docker daemon socket.
    """
    
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        # Import here to avoid issues on Windows
        import httpx._transports.default
        self._transport = httpx.AsyncHTTPTransport()
    
    async def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle request through Unix socket."""
        # For Unix sockets, we need to use a different approach
        # httpx doesn't natively support Unix sockets in the main library
        # We'll use the httpcore-async approach or fall back to aiosocket
        raise NotImplementedError("Unix socket transport requires httpx[httpcore] with Unix support")


class DockerClient:
    """
    Docker Engine API client wrapper.
    Communicates with Docker daemon via HTTP over Unix socket or TCP.
    """
    
    def __init__(self):
        self.base_url = settings.DOCKER_HOST
        self.api_version = settings.DOCKER_API_VERSION
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create httpx client."""
        if self._client is None:
            # Parse the Docker host URL
            if self.base_url.startswith("http+unix://"):
                # Unix socket connection
                # Extract socket path from URL (URL-encoded)
                socket_path = self.base_url.replace("http+unix://", "")
                socket_path = socket_path.replace("%2F", "/")
                
                # Use httpx with Unix socket support
                # Note: This requires httpx with Unix socket support
                # For cross-platform support, we'll use a custom approach
                import httpx._transports.default as default_transport
                
                # Create a custom transport for Unix sockets
                # This is a simplified implementation - in production, you'd want
                # to use a more robust Unix socket transport
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=300.0  # Long timeout for pull operations
                )
            else:
                # TCP or named pipe connection
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=300.0
                )
        
        return self._client
    
    async def close(self):
        """Close the httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL for Docker API endpoint."""
        return f"/{self.api_version}/{endpoint}"
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        stream: bool = False
    ) -> httpx.Response:
        """
        Make a request to the Docker Engine API.
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint (e.g., "containers/json")
            params: Query parameters
            json_data: JSON request body
            headers: Additional headers
            stream: Whether to stream the response
        
        Returns:
            httpx.Response object
        """
        client = await self._get_client()
        url = self._build_url(endpoint)
        
        try:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
                timeout=None if stream else 60.0
            )
            
            # Handle Docker API errors
            if response.status_code >= 400:
                error_detail = ""
                try:
                    error_json = response.json()
                    error_detail = error_json.get("message", "")
                except:
                    error_detail = response.text
                
                logger.error(
                    "Docker API error",
                    method=method,
                    endpoint=endpoint,
                    status_code=response.status_code,
                    detail=error_detail
                )
                
                # Map Docker API errors to HTTP exceptions
                if response.status_code == 404:
                    raise DockerNotFoundError(f"Docker resource not found: {error_detail or endpoint}")
                elif response.status_code == 409:
                    raise DockerConflictError(f"Docker conflict: {error_detail}")
                elif response.status_code == 400:
                    raise DockerBadRequestError(f"Bad request: {error_detail}")
                else:
                    raise DockerAPIError(f"Docker API error ({response.status_code}): {error_detail}")
            
            return response
            
        except httpx.ConnectError as e:
            logger.error("Failed to connect to Docker daemon", error=str(e))
            raise DockerConnectionError(f"Failed to connect to Docker daemon at {self.base_url}: {str(e)}")
        except httpx.TimeoutException as e:
            logger.error("Docker API request timeout", error=str(e))
            raise DockerTimeoutError(f"Docker API request timeout: {str(e)}")
    
    # ==================== Container Operations ====================
    
    async def list_containers(
        self,
        all: bool = False,
        limit: Optional[int] = None,
        filters: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        List containers.
        
        Docker API: GET /containers/json
        """
        params = {"all": all}
        if limit:
            params["limit"] = limit
        if filters:
            params["filters"] = json.dumps(filters)
        
        response = await self._request("GET", "containers/json", params=params)
        return response.json()
    
    async def get_container(self, container_id: str) -> Dict[str, Any]:
        """
        Get container details (inspect).
        
        Docker API: GET /containers/{id}/json
        """
        response = await self._request("GET", f"containers/{container_id}/json")
        return response.json()
    
    async def create_container(self, config: Dict[str, Any]) -> str:
        """
        Create a container.
        
        Docker API: POST /containers/create
        """
        response = await self._request("POST", "containers/create", json_data=config)
        return response.json()["Id"]
    
    async def start_container(self, container_id: str) -> None:
        """
        Start a container.
        
        Docker API: POST /containers/{id}/start
        """
        await self._request("POST", f"containers/{container_id}/start")
    
    async def stop_container(self, container_id: str, timeout: int = 10) -> None:
        """
        Stop a container.
        
        Docker API: POST /containers/{id}/stop
        """
        await self._request("POST", f"containers/{container_id}/stop", params={"t": timeout})
    
    async def restart_container(self, container_id: str, timeout: int = 10) -> None:
        """
        Restart a container.
        
        Docker API: POST /containers/{id}/restart
        """
        await self._request("POST", f"containers/{container_id}/restart", params={"t": timeout})
    
    async def remove_container(self, container_id: str, force: bool = False, remove_volumes: bool = False) -> None:
        """
        Remove a container.
        
        Docker API: DELETE /containers/{id}
        """
        params = {}
        if force:
            params["force"] = True
        if remove_volumes:
            params["v"] = True
        
        await self._request("DELETE", f"containers/{container_id}", params=params)
    
    async def exec_create(self, container_id: str, command: List[str], **kwargs) -> str:
        """
        Create an exec instance.
        
        Docker API: POST /containers/{id}/exec
        """
        config = {
            "AttachStdout": True,
            "AttachStderr": True,
            "Cmd": command,
            **kwargs
        }
        response = await self._request("POST", f"containers/{container_id}/exec", json_data=config)
        return response.json()["Id"]
    
    async def exec_start(self, exec_id: str) -> str:
        """
        Start an exec instance and return output.
        
        Docker API: POST /exec/{id}/start
        """
        config = {"Detach": False}
        response = await self._request("POST", f"exec/{exec_id}/start", json_data=config)
        return response.text
    
    async def get_container_logs(
        self,
        container_id: str,
        tail: Optional[int] = None,
        since: Optional[int] = None,
        follow: bool = False
    ) -> AsyncGenerator[str, None]:
        """
        Get container logs.
        
        Docker API: GET /containers/{id}/logs
        """
        params = {"stdout": True, "stderr": True}
        if tail:
            params["tail"] = tail
        if since:
            params["since"] = since
        if follow:
            params["follow"] = True
        
        response = await self._request("GET", f"containers/{container_id}/logs", params=params, stream=True)
        
        async for line in response.aiter_lines():
            yield line
    
    async def get_container_stats(self, container_id: str, stream: bool = False) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Get container resource usage stats.
        
        Docker API: GET /containers/{id}/stats
        """
        params = {"stream": stream}
        response = await self._request("GET", f"containers/{container_id}/stats", params=params, stream=stream)
        
        if stream:
            async for line in response.aiter_lines():
                yield json.loads(line)
        else:
            yield response.json()
    
    async def prune_containers(self) -> Dict[str, Any]:
        """
        Remove stopped containers.
        
        Docker API: POST /containers/prune
        """
        response = await self._request("POST", "containers/prune")
        return response.json()
    
    # ==================== Image Operations ====================
    
    async def list_images(self, all: bool = False, filters: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """
        List images.
        
        Docker API: GET /images/json
        """
        params = {"all": all}
        if filters:
            params["filters"] = json.dumps(filters)
        
        response = await self._request("GET", "images/json", params=params)
        return response.json()
    
    async def get_image(self, image_id: str) -> Dict[str, Any]:
        """
        Get image details (inspect).
        
        Docker API: GET /images/{id}/json
        """
        response = await self._request("GET", f"images/{image_id}/json")
        return response.json()
    
    async def pull_image(self, image: str, tag: str = "latest", platform: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Pull an image from a registry.
        
        Docker API: POST /images/create
        """
        params = {"fromImage": image, "tag": tag}
        if platform:
            params["platform"] = platform
        
        response = await self._request("POST", "images/create", params=params, stream=True)
        
        async for line in response.aiter_lines():
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
    
    async def tag_image(self, image: str, target: str) -> None:
        """
        Tag an image.
        
        Docker API: POST /images/{name}/tag
        """
        source, tag = target.split(":") if ":" in target else (target, "latest")
        await self._request("POST", f"images/{image}/tag", params={"repo": source, "tag": tag})
    
    async def remove_image(self, image_id: str, force: bool = False, prune: bool = False) -> None:
        """
        Remove an image.
        
        Docker API: DELETE /images/{id}
        """
        params = {}
        if force:
            params["force"] = True
        if prune:
            params["noprune"] = False
        
        await self._request("DELETE", f"images/{image_id}", params=params)
    
    async def prune_images(self, dangling: bool = True, filters: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Remove unused images.
        
        Docker API: POST /images/prune
        """
        params = {"dangling": dangling}
        if filters:
            params["filters"] = json.dumps(filters)
        
        response = await self._request("POST", "images/prune", params=params)
        return response.json()
    
    # ==================== Volume Operations ====================
    
    async def list_volumes(self) -> Dict[str, Any]:
        """
        List volumes.
        
        Docker API: GET /volumes
        """
        response = await self._request("GET", "volumes")
        return response.json()
    
    async def get_volume(self, volume_name: str) -> Dict[str, Any]:
        """
        Get volume details (inspect).
        
        Docker API: GET /volumes/{name}
        """
        response = await self._request("GET", f"volumes/{volume_name}")
        return response.json()
    
    async def create_volume(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a volume.
        
        Docker API: POST /volumes/create
        """
        response = await self._request("POST", "volumes/create", json_data=config)
        return response.json()
    
    async def remove_volume(self, volume_name: str, force: bool = False) -> None:
        """
        Remove a volume.
        
        Docker API: DELETE /volumes/{name}
        """
        params = {"force": force} if force else {}
        await self._request("DELETE", f"volumes/{volume_name}", params=params)
    
    async def prune_volumes(self, filters: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Remove unused volumes.
        
        Docker API: POST /volumes/prune
        """
        params = {}
        if filters:
            params["filters"] = json.dumps(filters)
        
        response = await self._request("POST", "volumes/prune", params=params)
        return response.json()
    
    # ==================== Network Operations ====================
    
    async def list_networks(self, filters: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """
        List networks.
        
        Docker API: GET /networks
        """
        params = {}
        if filters:
            params["filters"] = json.dumps(filters)
        
        response = await self._request("GET", "networks", params=params)
        return response.json()
    
    async def get_network(self, network_id: str) -> Dict[str, Any]:
        """
        Get network details (inspect).
        
        Docker API: GET /networks/{id}
        """
        response = await self._request("GET", f"networks/{network_id}")
        return response.json()
    
    async def create_network(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a network.
        
        Docker API: POST /networks/create
        """
        response = await self._request("POST", "networks/create", json_data=config)
        return response.json()
    
    async def remove_network(self, network_id: str) -> None:
        """
        Remove a network.
        
        Docker API: DELETE /networks/{id}
        """
        await self._request("DELETE", f"networks/{network_id}")
    
    async def connect_network(self, network_id: str, config: Dict[str, Any]) -> None:
        """
        Connect a container to a network.
        
        Docker API: POST /networks/{id}/connect
        """
        await self._request("POST", f"networks/{network_id}/connect", json_data=config)
    
    async def disconnect_network(self, network_id: str, config: Dict[str, Any]) -> None:
        """
        Disconnect a container from a network.
        
        Docker API: POST /networks/{id}/disconnect
        """
        await self._request("POST", f"networks/{network_id}/disconnect", json_data=config)
    
    async def prune_networks(self, filters: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Remove unused networks.
        
        Docker API: POST /networks/prune
        """
        params = {}
        if filters:
            params["filters"] = json.dumps(filters)
        
        response = await self._request("POST", "networks/prune", params=params)
        return response.json()
    
    # ==================== System Operations ====================
    
    async def get_system_info(self) -> Dict[str, Any]:
        """
        Get Docker daemon system information.
        
        Docker API: GET /info
        """
        response = await self._request("GET", "info")
        return response.json()
    
    async def get_system_version(self) -> Dict[str, Any]:
        """
        Get Docker version information.
        
        Docker API: GET /version
        """
        response = await self._request("GET", "version")
        return response.json()
    
    async def get_system_df(self) -> Dict[str, Any]:
        """
        Get disk usage information.
        
        Docker API: GET /system/df
        """
        response = await self._request("GET", "system/df")
        return response.json()
    
    async def prune_all(self, filters: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Prune all unused resources (containers, images, volumes, networks).
        
        This calls multiple prune endpoints and aggregates results.
        """
        results = {}
        
        # Prune containers
        try:
            results["containers"] = await self.prune_containers()
        except Exception as e:
            logger.warning("Failed to prune containers", error=str(e))
            results["containers"] = {"error": str(e)}
        
        # Prune images
        try:
            results["images"] = await self.prune_images(filters=filters)
        except Exception as e:
            logger.warning("Failed to prune images", error=str(e))
            results["images"] = {"error": str(e)}
        
        # Prune volumes
        try:
            results["volumes"] = await self.prune_volumes(filters=filters)
        except Exception as e:
            logger.warning("Failed to prune volumes", error=str(e))
            results["volumes"] = {"error": str(e)}
        
        # Prune networks
        try:
            results["networks"] = await self.prune_networks(filters=filters)
        except Exception as e:
            logger.warning("Failed to prune networks", error=str(e))
            results["networks"] = {"error": str(e)}
        
        return results
    
    async def ping(self) -> bool:
        """
        Check if Docker daemon is reachable.
        
        Docker API: GET /_ping
        """
        try:
            response = await self._request("GET", "_ping")
            return response.status_code == 200
        except Exception:
            return False


# ==================== Custom Exceptions ====================

class DockerAPIError(Exception):
    """Base exception for Docker API errors."""
    pass


class DockerConnectionError(DockerAPIError):
    """Exception raised when connection to Docker daemon fails."""
    pass


class DockerTimeoutError(DockerAPIError):
    """Exception raised when Docker API request times out."""
    pass


class DockerNotFoundError(DockerAPIError):
    """Exception raised when a Docker resource is not found (404)."""
    pass


class DockerConflictError(DockerAPIError):
    """Exception raised when a Docker operation conflicts (409)."""
    pass


class DockerBadRequestError(DockerAPIError):
    """Exception raised for bad requests to Docker API (400)."""
    pass


# Global client instance
docker_client = DockerClient()
