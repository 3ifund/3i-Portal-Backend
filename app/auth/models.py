"""
3i Fund Portal — Auth Request/Response Schemas
"""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    user_id: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    company_name: str
    user_id: str


class UserInfo(BaseModel):
    user_id: str
    role: str  # "user" or "admin"
    company_id: str | None = None
    company_name: str | None = None
