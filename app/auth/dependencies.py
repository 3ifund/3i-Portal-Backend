"""
3i Fund Portal — Auth Dependencies
FastAPI dependency injection for authenticated and admin-only routes.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt import decode_access_token
from app.auth.models import UserInfo

_bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> UserInfo:
    """Extract and validate the current user from the JWT token."""
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    return UserInfo(
        user_id=payload.get("user_id", ""),
        role=payload.get("role", "user"),
        company_id=payload.get("company_id"),
        company_name=payload.get("company_name"),
    )


async def require_admin(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """Ensure the current user has admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
