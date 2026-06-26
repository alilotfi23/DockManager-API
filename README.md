# Docker Management API

A production-ready CRUD API for managing Docker resources (containers, images, volumes, and networks) built with FastAPI. This API communicates directly with the Docker Engine REST API using raw HTTP requests via Unix socket, without using the Docker SDK.

## Features

- **Full Docker Resource Management**: CRUD operations for containers, images, volumes, and networks
- **JWT Authentication**: Secure token-based authentication with access and refresh tokens
- **Role-Based Access Control (RBAC)**: Admin (full access) and Viewer (read-only) roles
- **Real-time Logs Streaming**: Both HTTP (SSE) and WebSocket endpoints for container logs
- **Container Stats**: Live resource usage monitoring (CPU, memory, network I/O)
- **System Endpoints**: Docker daemon info, version, disk usage, and global prune
- **Pagination & Filtering**: All list endpoints support pagination and query filters
- **Rate Limiting**: Protection against brute-force attacks on auth endpoints
- **Structured Logging**: JSON logging with request IDs for tracing
- **API Versioning**: Clean versioning structure (`/api/v1`) for future compatibility
- **Docker Compose Ready**: Easy deployment with containerized setup

## Technology Stack

- **Python 3.11+**
- **FastAPI**: Modern, fast web framework
- **Pydantic v2**: Data validation and serialization
- **httpx**: Async HTTP client for Docker Engine API communication
- **SQLAlchemy 2.x (async)**: ORM with async support
- **SQLite + aiosqlite**: Lightweight database
- **Alembic**: Database migrations
- **python-jose**: JWT token handling
- **passlib[bcrypt]**: Password hashing
- **slowapi**: Rate limiting
- **structlog**: Structured logging

## Project Structure

```
.
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── api/
│   │   ├── deps.py             # API dependencies (auth, RBAC, pagination)
│   │   └── v1/
│   │       ├── api.py          # v1 API router aggregator
│   │       └── routes/
│   │           ├── auth.py      # Authentication endpoints
│   │           ├── containers.py # Container management
│   │           ├── images.py    # Image management
│   │           ├── volumes.py   # Volume management
│   │           ├── networks.py  # Network management
│   │           └── system.py    # System endpoints
│   ├── core/
│   │   ├── config.py           # Application configuration
│   │   └── security.py         # JWT and password hashing
│   ├── db/
│   │   ├── models.py           # SQLAlchemy models
│   │   └── session.py          # Database session management
│   ├── schemas/
│   │   ├── auth.py             # Auth Pydantic schemas
│   │   └── docker.py           # Docker resource schemas
│   └── services/
│       └── docker_client.py    # Docker Engine API client wrapper
├── alembic/                    # Database migrations
├── tests/                      # Pytest tests
├── Dockerfile                  # Container image definition
├── docker-compose.yml          # Docker Compose configuration
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── Makefile                    # Convenience commands
├── api.http                    # VS Code REST Client collection
└── README.md                   # This file
```

## Installation

### Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose (for containerized deployment)
- Docker daemon running (for API functionality)

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd python
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   make install
   # or
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Run the application**
   ```bash
   make dev
   # or
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

The API will be available at `http://localhost:8000`

### Docker Deployment

1. **Build and start with Docker Compose**
   ```bash
   make up
   # or
   docker-compose up -d
   ```

2. **View logs**
   ```bash
   make logs
   # or
   docker-compose logs -f
   ```

3. **Stop the application**
   ```bash
   make down
   # or
   docker-compose down
   ```

## Configuration

Environment variables are configured via `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key (change in production!) | `your-secret-key-change-this` |
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./app.db` |
| `DOCKER_HOST` | Docker daemon socket path | `http+unix://%2Fvar%2Frun%2Fdocker.sock` |
| `DOCKER_API_VERSION` | Docker Engine API version | `v1.45` |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000,http://localhost:8080` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `7` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Docker Host Configuration

The `DOCKER_HOST` variable depends on your platform:

- **Linux/Mac**: `http+unix://%2Fvar%2Frun%2Fdocker.sock` (URL-encoded `/var/run/docker.sock`)
- **Windows (named pipes)**: `npipe://./pipe/docker_engine`
- **TCP**: `http://localhost:2375` (if daemon configured for TCP)

## API Documentation

Once the application is running, visit:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## API Endpoints

### Authentication

All Docker management endpoints require authentication. Use the auth endpoints to obtain tokens.

#### Register User
```bash
POST /api/v1/auth/register
Content-Type: application/json

{
  "username": "testuser",
  "email": "test@example.com",
  "password": "password123",
  "role": "viewer"  // or "admin"
}
```

#### Login
```bash
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=testuser&password=password123
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

#### Refresh Token
```bash
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "your_refresh_token"
}
```

### Containers

#### List Containers
```bash
GET /api/v1/containers?all=true&limit=10&offset=0&status=running
Authorization: Bearer <access_token>
```

#### Create Container
```bash
POST /api/v1/containers
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "my-nginx",
  "image": "nginx:latest",
  "ports": {"80/tcp": "8080"},
  "restart_policy": "unless-stopped"
}
```

#### Start/Stop/Restart Container
```bash
POST /api/v1/containers/{id}/start
POST /api/v1/containers/{id}/stop
POST /api/v1/containers/{id}/restart
Authorization: Bearer <access_token>
```

#### Remove Container
```bash
DELETE /api/v1/containers/{id}?force=true&remove_volumes=true
Authorization: Bearer <access_token>
```

#### Execute Command in Container
```bash
POST /api/v1/containers/{id}/exec
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "command": ["ls", "-la"],
  "working_dir": "/app"
}
```

#### Get Container Logs
```bash
# Non-streaming
GET /api/v1/containers/{id}/logs?tail=100&since=1640995200
Authorization: Bearer <access_token>

# Streaming (SSE)
GET /api/v1/containers/{id}/logs/stream?tail=50
Authorization: Bearer <access_token>

# WebSocket
WS /api/v1/containers/{id}/logs/ws
```

#### Get Container Stats
```bash
# Single snapshot
GET /api/v1/containers/{id}/stats
Authorization: Bearer <access_token>

# Streaming (SSE)
GET /api/v1/containers/{id}/stats?stream=true
Authorization: Bearer <access_token>
```

#### Prune Stopped Containers
```bash
POST /api/v1/containers/prune
Authorization: Bearer <access_token>
```

### Images

#### List Images
```bash
GET /api/v1/images?all=true&name=nginx
Authorization: Bearer <access_token>
```

#### Pull Image
```bash
POST /api/v1/images/pull
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "from_image": "nginx",
  "tag": "latest",
  "platform": "linux/amd64"
}
```

#### Tag Image
```bash
POST /api/v1/images/tag
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "source": "nginx:latest",
  "target": "my-registry/nginx:v1.0"
}
```

#### Remove Image
```bash
DELETE /api/v1/images/{id}?force=true
Authorization: Bearer <access_token>
```

#### Prune Images
```bash
POST /api/v1/images/prune?dangling=false
Authorization: Bearer <access_token>
```

### Volumes

#### List Volumes
```bash
GET /api/v1/volumes
Authorization: Bearer <access_token>
```

#### Create Volume
```bash
POST /api/v1/volumes
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "my-volume",
  "driver": "local",
  "labels": {"env": "production"}
}
```

#### Remove Volume
```bash
DELETE /api/v1/volumes/{name}?force=true
Authorization: Bearer <access_token>
```

#### Prune Volumes
```bash
POST /api/v1/volumes/prune
Authorization: Bearer <access_token>
```

### Networks

#### List Networks
```bash
GET /api/v1/networks?name=my-network
Authorization: Bearer <access_token>
```

#### Create Network
```bash
POST /api/v1/networks
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "my-network",
  "driver": "bridge",
  "subnet": "172.20.0.0/16",
  "gateway": "172.20.0.1"
}
```

#### Connect Container to Network
```bash
POST /api/v1/networks/{id}/connect
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "container": "container_name_or_id"
}
```

#### Disconnect Container from Network
```bash
POST /api/v1/networks/{id}/disconnect
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "container": "container_name_or_id",
  "force": false
}
```

#### Prune Networks
```bash
POST /api/v1/networks/prune
Authorization: Bearer <access_token>
```

### System

#### Get Docker Info
```bash
GET /api/v1/system/info
Authorization: Bearer <access_token>
```

#### Get Docker Version
```bash
GET /api/v1/system/version
Authorization: Bearer <access_token>
```

#### Get Disk Usage
```bash
GET /api/v1/system/df
Authorization: Bearer <access_token>
```

#### Prune All Resources
```bash
POST /api/v1/system/prune
Authorization: Bearer <access_token>
```

### Health Check

```bash
GET /health
```

Returns API health and Docker daemon connectivity status.

## Role-Based Access Control

- **Admin Role**: Full access to all endpoints (CRUD operations)
- **Viewer Role**: Read-only access to GET endpoints only

All write operations (POST, PUT, DELETE) require admin role.

## Makefile Commands

```bash
make help          # Show all available commands
make install       # Install Python dependencies
make up            # Start with docker-compose
make down          # Stop with docker-compose
make restart       # Restart the application
make logs          # View application logs
make dev           # Run in development mode
make test          # Run tests
make test-coverage # Run tests with coverage
make migrate       # Run database migrations
make migrate-create MSG="description"  # Create new migration
make migrate-downgrade  # Rollback last migration
make lint          # Run linting
make format        # Format code
make clean         # Clean generated files
make build         # Build Docker image
make rebuild       # Rebuild without cache
make shell         # Open shell in container
```

## Testing

Run the test suite:

```bash
make test
```

Run tests with coverage:

```bash
make test-coverage
```

Tests use pytest with mocked Docker API calls to avoid requiring a running Docker daemon during testing.

## Database Migrations

### Create a new migration
```bash
make migrate-create MSG="add_new_field"
```

### Run migrations
```bash
make migrate
```

### Rollback last migration
```bash
make migrate-downgrade
```

## API Client Collection

The `api.http` file contains a comprehensive collection of HTTP requests for all endpoints. Use it with the VS Code REST Client extension or similar tools.

## Security Considerations

1. **Change the SECRET_KEY**: Never use the default secret key in production
2. **Use HTTPS**: Deploy behind a reverse proxy with SSL/TLS
3. **Docker Socket Access**: The container needs access to the Docker socket - ensure proper permissions
4. **Rate Limiting**: Auth endpoints are rate-limited to prevent brute-force attacks
5. **RBAC**: Use role-based access control to limit write operations
6. **CORS**: Configure allowed origins appropriately for your environment

## Troubleshooting

### Docker Daemon Unreachable

If the API returns 503 on health check:

1. Verify Docker daemon is running: `docker ps`
2. Check `DOCKER_HOST` configuration in `.env`
3. Ensure the Docker socket is mounted correctly in docker-compose.yml
4. Check permissions on `/var/run/docker.sock`

### Database Issues

If you encounter database errors:

1. Run migrations: `make migrate`
2. Check database file permissions
3. Verify `DATABASE_URL` in `.env`

### Container Creation Fails

If container creation fails:

1. Verify the image exists locally or can be pulled
2. Check port conflicts
3. Review container configuration (ports, volumes, etc.)
4. Check Docker daemon logs: `docker logs docker-api`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run tests: `make test`
6. Submit a pull request

## License

This project is provided as-is for educational and production use.

## Support

For issues and questions, please open an issue on the repository.
