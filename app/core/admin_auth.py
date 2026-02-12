from __future__ import annotations

import os
from typing import Optional

from fastapi import Header, HTTPException, status

from app.core.auth import CurrentUser, get_current_user


def require_admin(
    user: Optional[CurrentUser],
    x_admin_token: Optional[str],
) -> CurrentUser:
    admin_token = (os.getenv("ADMIN_API_TOKEN") or "").strip()
    token_ok = bool(admin_token) and bool(x_admin_token) and x_admin_token == admin_token
    role_ok = (user.role or "").lower() == "admin"

    if not admin_token and os.getenv("RBAC_ENFORCED", "0") != "1":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin endpoints disabled: set ADMIN_API_TOKEN or RBAC_ENFORCED=1",
        )
    if not (token_ok or role_ok):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin required")
    return user


def admin_dep(
    x_admin_token: Optional[str] = Header(default=None),
    user: CurrentUser = Header(default=None),
) -> CurrentUser:
    return require_admin(user, x_admin_token)
