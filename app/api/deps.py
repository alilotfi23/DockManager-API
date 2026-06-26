"""
FastAPI dependencies for authentication, authorization, and common utilities.
"""
from typing import Optional, Generator
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db.models import User, UserRole
from app.core.security import decode_token
from app.schemas.auth import TokenPayload
import structlog

logger = structlog.get_logger()

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"/api/v1/auth/login")


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    Args:
        db: Database session
        token: JWT access token
    
    Returns:
        User object
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Decode token
    payload = decode_token(token)
    if payload is None:
        logger.warning("Invalid token provided")
        raise credentials_exception
    
    # Check token type
    if payload.get("type") != "access":
        logger.warning("Wrong token type", token_type=payload.get("type"))
        raise credentials_exception
    
    # Get user ID from token
    user_id: Optional[int] = payload.get("sub")
    if user_id is None:
        logger.warning("Token missing user ID")
        raise credentials_exception
    
    # Fetch user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        logger.warning("User not found", user_id=user_id)
        raise credentials_exception
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get the current active user.
    
    This dependency can be extended to check for user activation status.
    """
    return current_user


def require_role(required_role: UserRole):
    """
    Dependency factory to require a specific user role.
    
    Args:
        required_role: The minimum role required (admin > viewer)
    
    Returns:
        Dependency function that checks user role
    
    Usage:
        @router.get("/admin-endpoint")
        async def admin_endpoint(user: User = Depends(require_role(UserRole.ADMIN))):
            ...
    """
    async def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role != UserRole.ADMIN and required_role == UserRole.ADMIN:
            logger.warning(
                "Insufficient permissions",
                user_id=current_user.id,
                user_role=current_user.role,
                required_role=required_role
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions. Admin role required."
            )
        return current_user
    
    return role_checker


def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Dependency to require admin role.
    
    Convenience function for require_role(UserRole.ADMIN).
    """
    if current_user.role != UserRole.ADMIN:
        logger.warning(
            "Admin access denied",
            user_id=current_user.id,
            user_role=current_user.role
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_read_only(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Dependency that allows both admin and viewer roles (read-only access).
    
    This is used for GET endpoints that both roles can access.
    """
    # Both admin and viewer can access read-only endpoints
    return current_user


def get_pagination_params(
    limit: int = 100,
    offset: int = 0
) -> dict:
    """
    Get pagination parameters from query string.
    
    Args:
        limit: Maximum number of items to return (default: 100)
        offset: Number of items to skip (default: 0)
    
    Returns:
        Dictionary with limit and offset
    """
    # Validate limit
    if limit < 1 or limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 1000"
        )
    
    # Validate offset
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Offset must be non-negative"
        )
    
    return {"limit": limit, "offset": offset}


def get_request_id(request: Request) -> str:
    """
    Get or generate a request ID for tracing.
    
    The request ID is set by middleware and stored in request.state.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    return request_id


class DockerClientDep:
    """
    Dependency for Docker client that ensures proper cleanup.
    """
    
    async def __call__(self) -> Generator:
        from app.services.docker_client import docker_client
        try:
            yield docker_client
        except Exception as e:
            logger.error("Docker client error", error=str(e))
            raise


# Instance of Docker client dependency
get_docker_client = DockerClientDep()
