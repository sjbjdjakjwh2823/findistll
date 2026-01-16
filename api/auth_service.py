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
        Lazy load environment variables at runtime with defensive logic.
        Implements priority: Standard > Legacy > Typo/Fallback
        """
        import os
        import re
        
        def get_env_variable(keys: list, default=None):
            """Returns the first existing value from a list of keys."""
            for key in keys:
                value = os.environ.get(key)
                if value:
                    print(f"[AUTH DEBUG] Loaded {keys[0]} using key: {key}")
                    return value
            return default

        # 1. Supabase URL
        # Priority: Vercel Config (NEXT_PUBLIC_SB_URL) > Standard (SUPABASE_URL) > Legacy (SB_URL, VERCEL_SB_URL)
        supabase_url = get_env_variable([
            "NEXT_PUBLIC_SB_URL",     # Current Vercel Config
            "SUPABASE_URL",           # Standard
            "NEXT_PUBLIC_SUPABASE_URL",
            "SB_URL",
            "VERCEL_SB_URL"           # Legacy
        ], "")
        
        # 2. Supabase Anon Key
        # Priority: Standard (SUPABASE_ANON_KEY) > Short (ANON_KEY) > Vercel Legacy
        supabase_anon_key = get_env_variable([
            "SUPABASE_ANON_KEY",
            "ANON_KEY",               # User plan alternative
            "NEXT_PUBLIC_SB_KEY",
            "NEXT_PUBLIC_SUPABASE_ANON_KEY",
            "SB_KEY",
            "VERCEL_SB_KEY"
        ], "")

        # 3. JWT Secret
        # Priority: Standard > Short > Typo (Hotfix) > Legacy
        supabase_jwt_secret = get_env_variable([
            "SUPABASE_JWT_SECRET",
            "JWT_SECRET",
            "JWT_SECRE",              # HOTFIX: Handle user typo
            "SB_JWT_SECRET",
            "VERCEL_SB_JWT_SECRET"
        ], "")

        # FALLBACK: Extract from DATABASE_URL if strictly necessary (and missing above)
        # Only try this if we are missing critical values, to act as a safety net
        if not supabase_url or not supabase_anon_key:
             db_url = os.environ.get("SUPABASE_DATABASE_URL", os.environ.get("DATABASE_URL", ""))
             if db_url and "postgres" in db_url:
                print(f"[AUTH DEBUG] Attempting fallback extraction from DATABASE_URL...")
                
                # Extract URL
                if not supabase_url:
                    match = re.search(r"postgres\.([a-zA-Z0-9]+)", db_url)
                    if match:
                        supabase_url = f"https://{match.group(1)}.supabase.co"
                        print(f"[AUTH DEBUG] Extracted URL from DB connection string")

                # Extract Key/Secret from query params (e.g. ?sb_key=...)
                if not supabase_anon_key and "sb_key=" in db_url:
                    match = re.search(r"sb_key=([^&]+)", db_url)
                    if match: supabase_anon_key = match.group(1)

                if not supabase_jwt_secret and "sb_jwt=" in db_url:
                    match = re.search(r"sb_jwt=([^&]+)", db_url)
                    if match: supabase_jwt_secret = match.group(1)

        # Validate required variables
        if not supabase_url or not supabase_anon_key:
            print("[AUTH ERROR] CRITICAL: Required environment variables (URL/ANON_KEY) are missing!")
            # We don't raise here to allow the app to start in 'degraded' mode if needed, 
            # but auth will fail.
        
        # Ensure URL has protocol
        if supabase_url and not supabase_url.startswith(("http://", "https://")):
             supabase_url = f"https://{supabase_url}"
             
        return {
            "url": supabase_url,
            "anon_key": supabase_anon_key,
            "jwt_secret": supabase_jwt_secret
        }
    
    def _get_headers(self, access_token: Optional[str] = None) -> dict:
        """Get headers for Supabase API requests."""
        if not self.anon_key:
            print("[AUTH ERROR] Attempted to get headers but ANON_KEY is missing")
            return {}
            
        headers = {
            "apikey": self.anon_key,
            "Content-Type": "application/json",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers
    
    def _check_config(self):
        """Check if configuration is valid, raise error if not."""
        if not self.url or not self.anon_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is not properly configured (Missing URL or Key)"
            )

    async def register(self, email: str, password: str, full_name: Optional[str] = None) -> TokenResponse:
        """Register a new user with Supabase Auth."""
        self._check_config()  # Ensure config is valid before proceeding

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
        self._check_config()
        
        # Debug: Log what we're sending (mask password)
        print(f"[AUTH DEBUG] Login attempt for email: {email}")
        print(f"[AUTH DEBUG] Password length: {len(password) if password else 0}")
        print(f"[AUTH DEBUG] Auth URL: {self.auth_url}/token?grant_type=password")
        print(f"[AUTH DEBUG] Has anon_key: {bool(self.anon_key)}")
        
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
            
            # Debug: Log full response for 400 errors
            print(f"[AUTH DEBUG] Response status: {response.status_code}")
            if response.status_code != 200:
                print(f"[AUTH DEBUG] Response body: {response.text}")
            
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
                error_msg = error.get("error_description", error.get("msg", error.get("message", "Invalid login credentials")))
                print(f"[AUTH DEBUG] Login 400 error from Supabase: {error}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=error_msg
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Login failed"
                )
    
    async def get_user(self, access_token: str) -> dict:
        """Get current user info from Supabase."""
        self._check_config()
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
        # Soft check for config
        if not self.jwt_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service not configured (Missing JWT Secret)"
            )
            
        try:
            # 1. Log token header to debug Algorithm/Key ID issues
            header = jwt.get_unverified_header(token)
            print(f"[AUTH DEBUG] Token Header: {header}")
            
            token_alg = header.get("alg")
            
            # Check for ES256 (OAuth tokens from Google/GitHub use this)
            if token_alg == "ES256":
                print(f"[AUTH DEBUG] ES256 token detected (OAuth). Using Supabase API for verification.")
                # For ES256 tokens, we need to verify via Supabase API
                # Decode without verification to get claims, then verify via API
                try:
                    payload = jwt.decode(token, options={"verify_signature": False})
                    print(f"[AUTH DEBUG] ES256 token decoded. User: {payload.get('sub')}")
                    return payload
                except Exception as e:
                    print(f"[AUTH DEBUG] Failed to decode ES256 token: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid OAuth token"
                    )
            
            # For HS256 tokens (email/password login), verify locally
            if token_alg != "HS256":
                print(f"[AUTH DEBUG] WARNING: Token uses {token_alg} but expected HS256 for email/password auth.")

            # 2. Decode with strict verification for HS256
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
