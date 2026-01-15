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
    """Supabase Authentication client with lazy loading for Vercel compatibility."""
    
    def __init__(self):
        """Initialize with lazy-loaded environment variables."""
        # Lazy load settings at runtime
        settings = self._get_settings()
        
        self.url = settings["url"]
        self.anon_key = settings["anon_key"]
        self.jwt_secret = settings["jwt_secret"]
        self.auth_url = f"{self.url}/auth/v1"
    
    def _get_settings(self) -> dict:
        """
        Lazy load environment variables at runtime.
        Uses new variable names (SB_*) to avoid Vercel caching issues.
        Falls back to legacy names and SUPABASE_DATABASE_URL extraction.
        """
        import os
        import re
        from urllib.parse import urlparse, parse_qs
        
        # Debug: List all environment variable names containing our prefixes
        all_env_keys = list(os.environ.keys())
        sb_keys = [k for k in all_env_keys if k.startswith("SB_") or "SUPABASE" in k.upper()]
        print(f"[AUTH DEBUG] Environment variables with SB_/SUPABASE prefix: {sb_keys}")
        
        # Try new names first (SB_*), then fall back to legacy names
        supabase_url = (
            os.environ.get("SB_URL") or
            os.environ.get("SUPABASE_URL") or
            ""
        )
        supabase_anon_key = (
            os.environ.get("SB_KEY") or
            os.environ.get("SUPABASE_ANON_KEY") or
            ""
        )
        supabase_jwt_secret = (
            os.environ.get("SB_JWT_SECRET") or
            os.environ.get("SUPABASE_JWT_SECRET") or
            ""
        )
        
        # FALLBACK: Extract from SUPABASE_DATABASE_URL if needed
        db_url = os.environ.get("SUPABASE_DATABASE_URL", os.environ.get("DATABASE_URL", ""))
        if db_url and (not supabase_url or not supabase_anon_key):
            print(f"[AUTH DEBUG] Attempting extraction from DATABASE_URL...")
            
            # Extract project ID for URL: postgresql+asyncpg://postgres.PROJECT_ID:...
            if not supabase_url:
                match = re.search(r"postgres\.([a-zA-Z0-9]+)", db_url)
                if match:
                    project_id = match.group(1)
                    supabase_url = f"https://{project_id}.supabase.co"
                    print(f"[AUTH DEBUG] Extracted URL from DATABASE_URL: {supabase_url}")
            
            # Extract anon_key and jwt_secret from query parameters if present
            if "?" in db_url:
                query_string = db_url.split("?", 1)[1]
                params = parse_qs(query_string)
                
                if not supabase_anon_key and "sb_key" in params:
                    supabase_anon_key = params["sb_key"][0]
                    print(f"[AUTH DEBUG] Extracted SB_KEY from DATABASE_URL")
                
                if not supabase_jwt_secret and "sb_jwt" in params:
                    supabase_jwt_secret = params["sb_jwt"][0]
                    print(f"[AUTH DEBUG] Extracted SB_JWT_SECRET from DATABASE_URL")
        
        # Debug logging (values hidden for security)
        print(f"[AUTH DEBUG] SB_URL loaded: {bool(supabase_url)} (len={len(supabase_url) if supabase_url else 0})")
        print(f"[AUTH DEBUG] SB_KEY loaded: {bool(supabase_anon_key)} (len={len(supabase_anon_key) if supabase_anon_key else 0})")
        print(f"[AUTH DEBUG] SB_JWT_SECRET loaded: {bool(supabase_jwt_secret)}")
        
        # Validate required variables
        if not supabase_url:
            print("[AUTH ERROR] SB_URL (or SUPABASE_URL) is not set!")
            print(f"[AUTH ERROR] Available env keys: {all_env_keys[:20]}...")
            raise ValueError("SB_URL or SUPABASE_URL environment variable is required")
        
        if not supabase_anon_key:
            print("[AUTH ERROR] SB_KEY (or SUPABASE_ANON_KEY) is not set!")
            print("[AUTH HINT] Add sb_key=YOUR_KEY to SUPABASE_DATABASE_URL query string")
            raise ValueError("SB_KEY or SUPABASE_ANON_KEY environment variable is required")
        
        # Ensure URL has protocol
        url = supabase_url.rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        
        print(f"[AUTH DEBUG] Final URL: '{url}'")
        
        return {
            "url": url,
            "anon_key": supabase_anon_key,
            "jwt_secret": supabase_jwt_secret
        }
    
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
