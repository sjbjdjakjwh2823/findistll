"""
Auth helpers for RBAC enforcement (header-based).
"""

import os
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, status

from app.core.tenant_context import get_effective_tenant_id
from app.db.registry import get_db
from app.services.org_service import OrgService

@dataclass
class CurrentUser:
    user_id: str
    role: str


def get_current_user(
    x_preciso_user_id: Optional[str] = Header(default=None),
    x_preciso_user_role: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> CurrentUser:
    enforce = os.getenv("RBAC_ENFORCED", "0") == "1"
    oidc_enabled = os.getenv("OIDC_ENABLED", "0") == "1"

    if oidc_enabled and authorization:
        try:
            from app.core.oidc import OIDCError, decode_bearer_token
            claims = decode_bearer_token(authorization)
        except OIDCError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc

        user_id = claims.get("sub") or claims.get("email") or "oidc_user"
        role_claim = os.getenv("OIDC_ROLE_CLAIM", "role")
        role = claims.get(role_claim) or claims.get("roles") or "viewer"
        if isinstance(role, list):
            role = role[0] if role else "viewer"
        return CurrentUser(user_id=str(user_id), role=str(role))

    if enforce and not oidc_enabled:
        admin_token = (os.getenv("ADMIN_API_TOKEN") or "").strip()
        token_ok = bool(admin_token) and bool(x_admin_token) and x_admin_token == admin_token
        if token_ok:
            return CurrentUser(user_id="admin", role="admin")

        # In enforced mode, user headers are mandatory. Role may be "auto" (server-resolved).
        if not x_preciso_user_id or not x_preciso_user_role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="RBAC enforced: missing X-Preciso-User-Id/X-Preciso-User-Role",
            )

    if not x_preciso_user_id:
        x_preciso_user_id = "anonymous"
    if not x_preciso_user_role or x_preciso_user_role == "auto":
        # Resolve role from org directory if configured; fallback to viewer.
        try:
            db = get_db()
            svc = OrgService(db)
            tenant_id = get_effective_tenant_id()
            resolved = svc.resolve_role(x_preciso_user_id, tenant_id=tenant_id)
            if resolved:
                x_preciso_user_role = resolved
        except Exception:
            # Best-effort only; never block auth due to org lookup failure.
            x_preciso_user_role = x_preciso_user_role or "viewer"

        # Usability default: authenticated user without org entry gets analyst.
        if not x_preciso_user_role or x_preciso_user_role == "auto":
            x_preciso_user_role = "viewer" if x_preciso_user_id == "anonymous" else "analyst"

    if enforce and (not x_preciso_user_id or not x_preciso_user_role):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing RBAC identity")

    if not x_preciso_user_role:
        x_preciso_user_role = "viewer"

    return CurrentUser(user_id=x_preciso_user_id, role=x_preciso_user_role)
