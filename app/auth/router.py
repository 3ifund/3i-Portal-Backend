"""
3i Fund Portal — Auth Router
Handles login and user info endpoints.

Login convention: user_id = {symbol}123 (e.g., caps123, bgl123, agig123).
The symbol is extracted, uppercased, and looked up in the PostgreSQL company table.
All users share the same password.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
import bcrypt

from app.auth.jwt import create_access_token
from app.auth.models import LoginRequest, LoginResponse, UserInfo
from app.auth.dependencies import get_current_user
from app.dealterms import repository as dealterms

logger = logging.getLogger("portal.auth")
router = APIRouter()

# Universal password hash (test123)
_UNIVERSAL_HASH = b"$2b$12$2uFjOIipv9ahAYvCatquqOT.bSB6E5Vj5tKbnflR4guf9gRvO1.wS"


def _extract_symbol(user_id: str) -> str | None:
    """
    Extract ticker symbol from user_id.
    Convention: everything before '123' is the symbol.
    Returns uppercase symbol or None if pattern doesn't match.
    """
    user_id_lower = user_id.strip().lower()
    if not user_id_lower.endswith("123"):
        return None
    symbol = user_id_lower[:-3]
    if not symbol:
        return None
    return symbol.upper()


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user and return JWT token."""
    logger.info("Login attempt for user_id=%s", request.user_id)

    # Extract symbol from user_id
    symbol = _extract_symbol(request.user_id)
    if not symbol:
        logger.warning("Login FAILED for user_id=%s (invalid format — must be {symbol}123)", request.user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid User ID",
        )

    # Look up symbol in company table
    company = await dealterms.get_company_by_symbol(symbol)
    if not company:
        logger.warning("Login FAILED for user_id=%s (symbol=%s not found in company table)", request.user_id, symbol)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid User ID",
        )

    # Verify password
    if not bcrypt.checkpw(request.password.encode(), _UNIVERSAL_HASH):
        logger.warning("Login FAILED for user_id=%s (wrong password)", request.user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid User ID or password",
        )

    token_data = {
        "user_id": request.user_id.strip().lower(),
        "role": "user",
        "company_id": str(company["company_id"]),
        "company_name": company["name"],
    }

    access_token = create_access_token(token_data)

    logger.info(
        "Login OK: user_id=%s symbol=%s company_id=%s company_name=%s",
        request.user_id, symbol, company["company_id"], company["name"],
    )

    return LoginResponse(
        access_token=access_token,
        role="user",
        company_name=company["name"],
        user_id=request.user_id.strip().lower(),
    )


@router.get("/me", response_model=UserInfo)
async def me(user: UserInfo = Depends(get_current_user)):
    """Return current authenticated user info."""
    logger.debug("GET /me user_id=%s", user.user_id)
    return user
