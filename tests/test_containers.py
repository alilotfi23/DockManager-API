"""
Tests for container endpoints.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_list_containers_unauthorized(client: AsyncClient):
    """Test listing containers without authentication."""
    response = await client.get("/api/v1/containers")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_containers_authorized(client: AsyncClient, auth_headers, mock_docker_client):
    """Test listing containers with authentication."""
    with patch("app.api.deps.get_docker_client", return_value=mock_docker_client):
        response = await client.get("/api/v1/containers", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_container(client: AsyncClient, auth_headers, mock_docker_client):
    """Test getting container details."""
    with patch("app.api.deps.get_docker_client", return_value=mock_docker_client):
        response = await client.get("/api/v1/containers/test123", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["Id"] == "test123"
        assert data["Name"] == "test-container"


@pytest.mark.asyncio
async def test_create_container_admin_only(client: AsyncClient, auth_headers, mock_docker_client):
    """Test creating a container requires admin role."""
    with patch("app.api.deps.get_docker_client", return_value=mock_docker_client):
        response = await client.post(
            "/api/v1/containers",
            headers=auth_headers,
            json={
                "name": "test-container",
                "image": "nginx:latest"
            }
        )
        # Viewer role should be denied
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_container_admin_success(client: AsyncClient, admin_headers, mock_docker_client):
    """Test creating a container with admin role."""
    with patch("app.api.deps.get_docker_client", return_value=mock_docker_client):
        response = await client.post(
            "/api/v1/containers",
            headers=admin_headers,
            json={
                "name": "test-container",
                "image": "nginx:latest"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert "message" in data


@pytest.mark.asyncio
async def test_start_container(client: AsyncClient, admin_headers, mock_docker_client):
    """Test starting a container."""
    with patch("app.api.deps.get_docker_client", return_value=mock_docker_client):
        response = await client.post(
            "/api/v1/containers/test123/start",
            headers=admin_headers
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_stop_container(client: AsyncClient, admin_headers, mock_docker_client):
    """Test stopping a container."""
    with patch("app.api.deps.get_docker_client", return_value=mock_docker_client):
        response = await client.post(
            "/api/v1/containers/test123/stop",
            headers=admin_headers
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_remove_container(client: AsyncClient, admin_headers, mock_docker_client):
    """Test removing a container."""
    with patch("app.api.deps.get_docker_client", return_value=mock_docker_client):
        response = await client.delete(
            "/api/v1/containers/test123",
            headers=admin_headers
        )
        assert response.status_code == 200
