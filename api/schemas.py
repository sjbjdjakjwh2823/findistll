"""
Pydantic Schemas for FinDistill API

Request/Response models for authentication and API endpoints.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# ============== Auth Schemas ==============

class UserRegister(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Authentication token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    user: Optional[dict] = None


class UserProfile(BaseModel):
    """User profile data."""
    id: str
    email: str
    full_name: Optional[str] = None
    api_quota: int = 100
    created_at: Optional[datetime] = None


class AuthError(BaseModel):
    """Authentication error response."""
    detail: str
    error_code: Optional[str] = None
