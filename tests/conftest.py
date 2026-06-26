"""
Pytest configuration and fixtures.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.main import app
from app.db.models import User
from app.core.security import get_password_hash
from app.core.config import settings

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True
)

# Create test session factory
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


@pytest.fixture(scope="function")
async def db_session():
    """Create a fresh database session for each test."""
    from app.db.session import Base
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session):
    """Create a test client with database session override."""
    from app.api.deps import get_db
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session):
    """Create a test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpass123"),
        role="viewer"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def admin_user(db_session):
    """Create an admin user."""
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("adminpass123"),
        role="admin"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def auth_headers(client, test_user):
    """Get authentication headers for a test user."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "testpass123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_headers(client, admin_user):
    """Get authentication headers for an admin user."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "adminpass123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_docker_client():
    """Mock Docker client for testing."""
    from unittest.mock import AsyncMock
    from app.services.docker_client import DockerClient
    
    mock_client = AsyncMock(spec=DockerClient)
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.list_containers = AsyncMock(return_value=[])
    mock_client.get_container = AsyncMock(return_value={
        "Id": "test123",
        "Name": "test-container",
        "Image": "nginx:latest",
        "Status": "running",
        "State": "running",
        "Created": "2024-01-01T00:00:00Z"
    })
    mock_client.create_container = AsyncMock(return_value="new123")
    mock_client.start_container = AsyncMock()
    mock_client.stop_container = AsyncMock()
    mock_client.remove_container = AsyncMock()
    
    return mock_client
