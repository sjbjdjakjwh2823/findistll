from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.db.registry import get_db
from app.services.unity_catalog_service import UnityCatalogService


router = APIRouter(prefix="/governance", tags=["Governance"])


class ApplyPolicyIn(BaseModel):
    domain: str = Field(description="market|fundamental|event|alt|ml")
    principal: str
    role: str = Field(description="admin|analyst|reviewer|auditor")
    effect: str = Field(default="allow")
    rules: Dict[str, Any] = Field(default_factory=dict)


@router.get("/lineage")
def lineage(limit: int = 200, user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    return {"events": UnityCatalogService(db).list_lineage(limit=limit)}


@router.get("/policies")
def list_policies(user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    return {"policies": UnityCatalogService(db).list_policies()}


@router.post("/policies/apply")
def apply_policy(payload: ApplyPolicyIn, user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    row = UnityCatalogService(db).apply_policy(
        domain=payload.domain,
        principal=payload.principal,
        role=payload.role,
        effect=payload.effect,
        rules=payload.rules,
        requested_by=user.user_id,
    )
    return {"policy": row}
