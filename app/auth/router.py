"""
3i Fund Portal — Auth Router
Handles login and user info endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
import bcrypt

from app.auth.jwt import create_access_token
from app.auth.models import LoginRequest, LoginResponse, UserInfo
from app.auth.dependencies import get_current_user
from app.database.mongo import get_db

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user and return JWT token."""
    db = get_db()
    user = await db["users"].find_one({"user_id": request.user_id})

    if not user or not bcrypt.checkpw(
        request.password.encode(), user.get("password_hash", "").encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid User ID or password",
        )

    token_data = {
        "user_id": user["user_id"],
        "role": user.get("role", "user"),
        "company_id": user.get("company_id", ""),
        "company_name": user.get("company_name", ""),
    }

    access_token = create_access_token(token_data)

    return LoginResponse(
        access_token=access_token,
        role=user.get("role", "user"),
        company_name=user.get("company_name", ""),
        user_id=user["user_id"],
    )


@router.get("/me", response_model=UserInfo)
async def me(user: UserInfo = Depends(get_current_user)):
    """Return current authenticated user info."""
    return user
