from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.api.v1.ingest import get_db
from app.core.auth import CurrentUser, get_current_user
from app.core.admin_auth import require_admin
from app.services.partner_registry import (
    create_partner_account,
    find_partner_account_by_partner_id,
    issue_partner_api_key,
    revoke_partner_api_key,
)


router = APIRouter(prefix="/admin/partners", tags=["Admin - Partners"])


def _require_admin(
    user: CurrentUser = Depends(get_current_user),
    x_admin_token: Optional[str] = Header(default=None),
) -> CurrentUser:
    return require_admin(user, x_admin_token)


class PartnerCreateRequest(BaseModel):
    partner_id: str = Field(..., description="Stable partner identifier (e.g., 'acme-inc')")
    name: str = Field(..., description="Partner display name")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    key_label: Optional[str] = Field(default="default", description="Label for the initial key")


class PartnerCreateResponse(BaseModel):
    partner_id: str
    partner_account_id: str
    api_key: str
    key_id: str
    key_prefix: str


@router.post("", response_model=PartnerCreateResponse)
async def create_partner(
    req: PartnerCreateRequest,
    _user: CurrentUser = Depends(_require_admin),
):
    db = get_db()

    existing = find_partner_account_by_partner_id(db=db, partner_id=req.partner_id)
    if existing:
        raise HTTPException(status_code=409, detail="partner_id already exists")

    acct = create_partner_account(db=db, partner_id=req.partner_id, name=req.name, metadata=req.metadata)
    issued = issue_partner_api_key(db=db, partner_account_id=acct["id"], label=req.key_label)

    key_record = issued["record"]
    return PartnerCreateResponse(
        partner_id=acct["partner_id"],
        partner_account_id=acct["id"],
        api_key=issued["api_key"],
        key_id=key_record["id"],
        key_prefix=key_record["key_prefix"],
    )


class KeyIssueRequest(BaseModel):
    label: Optional[str] = Field(default="rotation", description="Key label (e.g., 'rotation-2026-02')")


@router.post("/{partner_id}/keys")
async def issue_key(
    partner_id: str,
    req: KeyIssueRequest,
    _user: CurrentUser = Depends(_require_admin),
):
    db = get_db()
    acct = find_partner_account_by_partner_id(db=db, partner_id=partner_id)
    if not acct:
        raise HTTPException(status_code=404, detail="partner not found")
    issued = issue_partner_api_key(db=db, partner_account_id=acct["id"], label=req.label)
    key_record = issued["record"]
    return {
        "partner_id": partner_id,
        "partner_account_id": acct["id"],
        "api_key": issued["api_key"],  # one-time secret
        "key": {
            "id": key_record["id"],
            "key_prefix": key_record["key_prefix"],
            "label": key_record.get("label"),
            "created_at": key_record.get("created_at"),
        },
    }


@router.post("/{partner_id}/keys/{key_id}/revoke")
async def revoke_key(
    partner_id: str,
    key_id: str,
    _user: CurrentUser = Depends(_require_admin),
):
    db = get_db()
    acct = find_partner_account_by_partner_id(db=db, partner_id=partner_id)
    if not acct:
        raise HTTPException(status_code=404, detail="partner not found")
    revoke_partner_api_key(db=db, key_id=key_id)
    return {"partner_id": partner_id, "revoked": True, "key_id": key_id}


@router.get("")
async def list_partners(
    limit: int = 100,
    _user: CurrentUser = Depends(_require_admin),
):
    db = get_db()
    res = db.client.table("partner_accounts").select("id, partner_id, name, metadata, created_at, disabled_at").order("created_at", desc=True).limit(limit).execute()
    return {"partners": res.data or []}


@router.get("/{partner_id}/keys")
async def list_partner_keys(
    partner_id: str,
    limit: int = 200,
    _user: CurrentUser = Depends(_require_admin),
):
    db = get_db()
    acct = find_partner_account_by_partner_id(db=db, partner_id=partner_id)
    if not acct:
        raise HTTPException(status_code=404, detail="partner not found")
    res = (
        db.client.table("partner_api_keys")
        .select("id, key_prefix, label, created_at, revoked_at, last_used_at")
        .eq("partner_account_id", acct["id"])
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"partner_id": partner_id, "keys": res.data or []}
