import json
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional

import requests


class OIDCError(Exception):
    pass


@dataclass
class JwksCache:
    jwks: Optional[Dict] = None
    fetched_at: float = 0.0
    jwks_uri: Optional[str] = None


_JWKS_CACHE = JwksCache()


def _fetch_openid_config(issuer_url: str) -> Dict:
    url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        raise OIDCError(f"OIDC discovery failed ({resp.status_code})")
    return resp.json()


def _get_jwks_uri() -> str:
    explicit = os.getenv("OIDC_JWKS_URL", "").strip()
    if explicit:
        return explicit
    issuer = os.getenv("OIDC_ISSUER_URL", "").strip()
    if not issuer:
        raise OIDCError("OIDC_ISSUER_URL or OIDC_JWKS_URL is required")
    config = _fetch_openid_config(issuer)
    jwks_uri = config.get("jwks_uri")
    if not jwks_uri:
        raise OIDCError("OIDC discovery missing jwks_uri")
    return jwks_uri


def _get_jwks() -> Dict:
    cache_s = int(os.getenv("OIDC_JWKS_CACHE_S", "3600"))
    now = time.time()
    if _JWKS_CACHE.jwks and (now - _JWKS_CACHE.fetched_at) < cache_s:
        return _JWKS_CACHE.jwks

    jwks_uri = _get_jwks_uri()
    resp = requests.get(jwks_uri, timeout=10)
    if resp.status_code != 200:
        raise OIDCError(f"JWKS fetch failed ({resp.status_code})")
    jwks = resp.json()
    _JWKS_CACHE.jwks = jwks
    _JWKS_CACHE.fetched_at = now
    _JWKS_CACHE.jwks_uri = jwks_uri
    return jwks


def decode_bearer_token(authorization: str) -> Dict:
    try:
        from jose import jwt  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise OIDCError("OIDC requires python-jose to be installed") from exc
    if not authorization.startswith("Bearer "):
        raise OIDCError("Invalid Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise OIDCError("Empty bearer token")

    jwks = _get_jwks()
    issuer = os.getenv("OIDC_ISSUER_URL", "").strip()
    audience = os.getenv("OIDC_AUDIENCE", "").strip()

    try:
        return jwt.decode(
            token,
            jwks,
            algorithms=["RS256", "RS384", "RS512"],
            issuer=issuer or None,
            audience=audience or None,
            options={
                "verify_aud": bool(audience),
                "verify_iss": bool(issuer),
            },
        )
    except Exception as exc:
        raise OIDCError("OIDC token validation failed") from exc
