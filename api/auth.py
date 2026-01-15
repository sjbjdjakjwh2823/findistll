"""
Supabase Authentication Module for FinDistill

Provides JWT verification and user authentication for FastAPI endpoints.
Uses Supabase GoTrue for authentication backend.
"""

import os
import httpx
import jwt
from datetime import datetime
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .schemas import UserRegister, UserLogin, TokenResponse, UserProfile

# Security scheme for Bearer token
security = HTTPBearer(auto_error=False)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")


class SupabaseAuth:
    """Supabase Authentication client."""
    
    def __init__(self):
        self.url = SUPABASE_URL
        self.anon_key = SUPABASE_ANON_KEY
        self.jwt_secret = SUPABASE_JWT_SECRET
        self.auth_url = f"{self.url}/auth/v1"
    
    def _get_headers(self, access_token: Optional[str] = None) -> dict:
        """Get headers for Supabase API requests."""
        headers = {
            "apikey": self.anon_key,
            "Content-Type": "application/json",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers
    
    async def register(self, email: str, password: str, full_name: Optional[str] = None) -> TokenResponse:
        """Register a new user with Supabase Auth."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.auth_url}/signup",
                headers=self._get_headers(),
                json={
                    "email": email,
                    "password": password,
                    "data": {"full_name": full_name} if full_name else {}
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return TokenResponse(
                    access_token=data.get("access_token", ""),
                    expires_in=data.get("expires_in", 3600),
                    refresh_token=data.get("refresh_token"),
                    user=data.get("user")
                )
            elif response.status_code == 400:
                error = response.json()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error.get("msg", "Registration failed")
                )
            elif response.status_code == 422:
                error = response.json()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=error.get("msg", "Invalid email or password format")
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Registration failed: {response.text}"
                )
    
    async def login(self, email: str, password: str) -> TokenResponse:
        """Login user with Supabase Auth."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.auth_url}/token?grant_type=password",
                headers=self._get_headers(),
                json={
                    "email": email,
                    "password": password
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return TokenResponse(
                    access_token=data.get("access_token", ""),
                    expires_in=data.get("expires_in", 3600),
                    refresh_token=data.get("refresh_token"),
                    user=data.get("user")
                )
            elif response.status_code == 400:
                error = response.json()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=error.get("error_description", "Invalid login credentials")
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Login failed"
                )
    
    async def get_user(self, access_token: str) -> dict:
        """Get current user info from Supabase."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.auth_url}/user",
                headers=self._get_headers(access_token),
                timeout=10.0
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )
    
    def verify_token(self, token: str) -> dict:
        """Verify JWT token locally using Supabase JWT secret."""
        try:
            # Decode without verification first to check structure
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                audience="authenticated"
            )
            
            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.utcnow().timestamp() > exp:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired"
                )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )


# Singleton instance
supabase_auth = SupabaseAuth()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    Get current authenticated user from JWT token.
    Returns None if no token provided (for optional auth).
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    
    # Verify token locally
    payload = supabase_auth.verify_token(token)
    
    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role", "authenticated"),
        "user_metadata": payload.get("user_metadata", {})
    }


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
) -> dict:
    """
    Require authentication for protected routes.
    Raises 401 if no valid token provided.
    """
    token = credentials.credentials
    
    # Verify token locally
    payload = supabase_auth.verify_token(token)
    
    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role", "authenticated"),
        "user_metadata": payload.get("user_metadata", {})
    }
