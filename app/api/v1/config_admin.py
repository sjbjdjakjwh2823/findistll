from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.core.admin_auth import require_admin
from app.services.feature_flags import list_flags, set_flag


router = APIRouter(prefix="/config", tags=["Config"])


def _require_admin(
    user: CurrentUser = Depends(get_current_user),
):
    return require_admin(user, None)


class FlagUpdate(BaseModel):
    name: str = Field(..., description="Flag name")
    enabled: bool = Field(..., description="Enable/disable")


@router.get("/flags")
def get_flags(_user: CurrentUser = Depends(_require_admin)):
    return {"flags": list_flags()}


@router.post("/flags")
def update_flag(payload: FlagUpdate, _user: CurrentUser = Depends(_require_admin)):
    set_flag(payload.name, payload.enabled)
    return {"flags": list_flags()}
