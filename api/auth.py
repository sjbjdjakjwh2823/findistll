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

# Note: Environment variables are loaded inside SupabaseAuth.__init__ for Vercel compatibility


class SupabaseAuth:
    """Supabase Authentication client."""
    
    def __init__(self):
        # Load environment variables at runtime for Vercel compatibility
        supabase_url = os.getenv("SUPABASE_URL", "")
        supabase_anon_key = os.getenv("SUPABASE_ANON_KEY", "")
        supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")
        
        # DEBUG: Log environment variables
        print(f"[AUTH DEBUG] SUPABASE_URL from env: '{supabase_url}'")
        print(f"[AUTH DEBUG] SUPABASE_ANON_KEY present: {bool(supabase_anon_key)}")
        
        if not supabase_url:
            print("[AUTH ERROR] SUPABASE_URL is not set!")
            raise ValueError("SUPABASE_URL environment variable is required")
        
        self.url = supabase_url.rstrip("/")
        if not self.url.startswith(("http://", "https://")):
            self.url = f"https://{self.url}"
        
        print(f"[AUTH DEBUG] Final URL: '{self.url}'")

        self.anon_key = supabase_anon_key
        self.jwt_secret = supabase_jwt_secret
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
                # Capture the original status code from Supabase
                print(f"[AUTH ERROR] Register failed with status {response.status_code}: {response.text}")
                try:
                    detail = response.json()
                except:
                    detail = {"msg": response.text}
                    
                raise HTTPException(
                    status_code=response.status_code,
                    detail=detail.get("msg", detail.get("error_description", f"Registration failed: {response.text}"))
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
            # 1. Log token header to debug Algorithm/Key ID issues
            try:
                header = jwt.get_unverified_header(token)
                print(f"[AUTH DEBUG] Token Header: {header}")
                
                # Check for algorithm mismatch
                if header.get("alg") != "HS256":
                     print(f"[AUTH DEBUG] WARNING: Token passes {header.get('alg')} but strict enforcement usually expects HS256 for Supabase default.")
            except Exception as e:
                print(f"[AUTH DEBUG] Failed to parse token header: {e}")

            # 2. Decode with strict verification
            # Note: Supabase defaults to HS256. If you rotated to RS256, you need to use the Public Key.
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                audience="authenticated"
            )
            
            # 3. Check expiration manually if library didn't (just in case)
            exp = payload.get("exp")
            if exp:
                exp_dt = datetime.fromtimestamp(exp)
                if datetime.utcnow().timestamp() > exp:
                    print(f"[AUTH DEBUG] Token expired at {exp_dt}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Token expired at {exp_dt}"
                    )
            
            print(f"[AUTH DEBUG] Token verified successfully for user: {payload.get('sub')}")
            return payload
            
        except jwt.ExpiredSignatureError as e:
            print(f"[AUTH DEBUG] Verification Failed: Expired Signature - {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidAudienceError as e:
            print(f"[AUTH DEBUG] Verification Failed: Invalid Audience - {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid audience. Expected 'authenticated', got error: {e}"
            )
        except jwt.InvalidSignatureError as e:
            print("[AUTH DEBUG] Verification Failed: Invalid Signature. Key mismatch? Logic: HS256 with provided Secret.")
            print(f"[AUTH DEBUG] Secret used (first 5 chars): {self.jwt_secret[:5]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature. Please check SUPABASE_JWT_SECRET configuration."
            )
        except jwt.DecodeError as e:
            print(f"[AUTH DEBUG] Verification Failed: Decode Error - {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is invalid or malformed"
            )
        except Exception as e:
            print(f"[AUTH DEBUG] data validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {str(e)}"
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
