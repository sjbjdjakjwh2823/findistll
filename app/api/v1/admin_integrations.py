from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.api.v1.ingest import get_db
from app.core.auth import CurrentUser, get_current_user
from app.core.admin_auth import require_admin
from app.services.integration_keys import (
    list_registered_keys,
    normalize_provider,
    revoke_registered_key,
    set_registered_key,
)
from app.services.market_data import market_data_service
from app.services.secret_store import secret_store_enabled


router = APIRouter(prefix="/admin/integrations", tags=["Admin - Integrations"])
logger = logging.getLogger(__name__)

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_admin(
    user: CurrentUser = Depends(get_current_user),
    x_admin_token: Optional[str] = Header(default=None),
) -> CurrentUser:
    return require_admin(user, x_admin_token)


class SetKeyRequest(BaseModel):
    provider: str = Field(..., description="finnhub|fred|fmp|sec|gemini|openai")
    api_key: str = Field(..., description="Provider API key/secret")
    label: Optional[str] = Field(default=None)


@router.get("/keys")
async def get_keys(
    limit: int = 50,
    _user: CurrentUser = Depends(_require_admin),
):
    db = None
    try:
        db = get_db()
    except Exception:
        # Allow local fallback when DB is not configured/bootstrapped.
        db = None
    return {"keys": list_registered_keys(db=db, limit=limit)}


@router.post("/keys")
async def set_key(
    req: SetKeyRequest,
    _user: CurrentUser = Depends(_require_admin),
):
    if not secret_store_enabled():
        raise HTTPException(status_code=500, detail="secret store disabled: set INTEGRATION_KEYS_MASTER_KEY")
    db = None
    try:
        db = get_db()
    except Exception:
        db = None
    stored = set_registered_key(db=db, provider=req.provider, api_key=req.api_key, label=req.label)
    return {"stored": stored}


@router.delete("/keys/{provider}")
async def revoke_key(
    provider: str,
    _user: CurrentUser = Depends(_require_admin),
):
    db = None
    try:
        db = get_db()
    except Exception:
        db = None
    revoke_registered_key(db=db, provider=provider)
    return {"provider": normalize_provider(provider), "revoked": True}


class TestRequest(BaseModel):
    symbol: Optional[str] = Field(default="AAPL", description="Used for finnhub/fmp/sec test")
    series_id: Optional[str] = Field(default="FEDFUNDS", description="Used for fred test")


@router.post("/test/{provider}")
async def test_provider(
    provider: str,
    req: TestRequest,
    _user: CurrentUser = Depends(_require_admin),
):
    db = None
    try:
        db = get_db()
    except Exception:
        db = None
    provider_n = normalize_provider(provider)

    svc = market_data_service
    ok = False
    detail = {}
    try:
        if provider_n == "finnhub":
            payload = await svc.fetch_finnhub_quote(req.symbol or "AAPL", api_key_override=None, db=db)
            ok = not bool(payload.get("error"))
            detail = payload
        elif provider_n == "fred":
            obs = await svc.fetch_fred_series(req.series_id or "FEDFUNDS", limit=1, api_key_override=None, db=db)
            ok = bool(obs)
            detail = {"observations": obs[:1]}
        elif provider_n == "fmp":
            data = await svc.fetch_fmp_financial_statement_growth(req.symbol or "AAPL", period="annual", limit=1, api_key_override=None, db=db)
            ok = bool(data)
            detail = {"rows": data[:1] if isinstance(data, list) else data}
        elif provider_n == "sec":
            data = await svc.fetch_sec_filings(req.symbol or "AAPL", form_type="10-K", limit=1, api_key_override=None, db=db)
            ok = bool(data)
            detail = {"submissions": data[:1]}
        else:
            raise HTTPException(status_code=400, detail="unsupported provider for test")
    finally:
        # Update test status in DB if available; local fallback is handled in list output.
        if db is not None:
            try:
                db.client.table("integration_secrets").update(
                    {"last_tested_at": _utc_now_iso(), "last_test_status": "ok" if ok else "error"}
                ).eq("provider", provider_n).is_("revoked_at", None).execute()
            except Exception as exc:
                logger.warning("swallowed exception", exc_info=exc)

    return {"provider": provider_n, "ok": ok, "detail": detail}
