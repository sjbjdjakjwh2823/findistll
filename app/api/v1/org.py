from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.core.admin_auth import require_admin
from app.db.registry import get_db
from app.services.org_service import OrgService


router = APIRouter(prefix="/org", tags=["Org"])


def _require_admin(
    user: CurrentUser = Depends(get_current_user),
    x_admin_token: Optional[str] = Header(default=None),
) -> CurrentUser:
    return require_admin(user, x_admin_token)


@router.get("/me")
async def me(user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    svc = OrgService(db)
    org = svc.get_user(user.user_id)
    return {
        "user": {"user_id": user.user_id, "role": user.role},
        "org_user": org.__dict__ if org else None,
    }


class UpsertUserRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    email: Optional[str] = None
    display_name: Optional[str] = None
    status: str = Field(default="active")


@router.get("/users")
async def list_users(limit: int = 200, _admin: CurrentUser = Depends(_require_admin)):
    db = get_db()
    svc = OrgService(db)
    users = svc.list_users(limit=limit)
    return {"items": [u.__dict__ for u in users]}


@router.post("/users")
async def upsert_user(req: UpsertUserRequest, _admin: CurrentUser = Depends(_require_admin)):
    db = get_db()
    svc = OrgService(db)
    u = svc.upsert_user(
        user_id=req.user_id,
        role=req.role,
        email=req.email,
        display_name=req.display_name,
        status=req.status,
    )
    return {"user": u.__dict__}

