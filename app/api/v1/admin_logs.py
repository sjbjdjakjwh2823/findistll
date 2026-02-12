from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status, Query
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.core.admin_auth import require_admin
from app.db.registry import get_db
from app.services.log_reader import tail_file


router = APIRouter(prefix="/admin/logs", tags=["Admin - Logs"])


def _require_admin(
    user: CurrentUser = Depends(get_current_user),
    x_admin_token: Optional[str] = Header(default=None),
) -> CurrentUser:
    return require_admin(user, x_admin_token)


class TailResponse(BaseModel):
    path: str
    lines: int
    items: list[str]


@router.get("/tail", response_model=TailResponse)
async def tail_app_log(
    lines: int = Query(200, ge=1, le=5000),
    service: str = Query("backend", description="backend|worker|event_worker"),
    contains: Optional[str] = Query(None, description="Substring filter applied server-side (post-redaction)"),
    _user: CurrentUser = Depends(_require_admin),
) -> Dict[str, Any]:
    service = (service or "backend").strip().lower()
    env_key = {
        "backend": "LOG_FILE_BACKEND",
        "worker": "LOG_FILE_WORKER",
        "event_worker": "LOG_FILE_EVENT_WORKER",
    }.get(service, "LOG_FILE_BACKEND")
    default_path = {
        "backend": "/var/log/preciso/backend.log",
        "worker": "/var/log/preciso/worker.log",
        "event_worker": "/var/log/preciso/event_worker.log",
    }.get(service, "/var/log/preciso/backend.log")
    path = (os.getenv(env_key) or os.getenv("LOG_FILE_PATH") or default_path).strip()
    items = tail_file(path, lines=lines)
    if contains:
        needle = str(contains)
        items = [x for x in items if needle in x]
    return {"path": path, "lines": lines, "items": items}


@router.get("/audit")
async def list_audit_logs(
    limit: int = 200,
    _user: CurrentUser = Depends(_require_admin),
) -> Dict[str, Any]:
    db = get_db()
    try:
        rows = db.list_audit_logs(limit=limit)
    except Exception:
        rows = []
    return {"items": rows}


@router.get("/tenant")
async def list_tenant_audit_logs(
    tenant_id: Optional[str] = Query(None, description="Filter by tenant_id"),
    actor_id: Optional[str] = Query(None, description="Filter by actor/user id"),
    action: Optional[str] = Query(None, description="Filter by action/event"),
    limit: int = Query(500, ge=1, le=5000),
    _user: CurrentUser = Depends(_require_admin),
) -> Dict[str, Any]:
    """
    Enterprise log view for tenant-scoped operational events.
    Works with both audit middleware rows and explicit collab/pipeline audit payloads.
    """
    db = get_db()
    try:
        rows = db.list_audit_logs(limit=limit)
    except Exception:
        rows = []

    def _row_tenant(r: Dict[str, Any]) -> Optional[str]:
        if r.get("tenant_id"):
            return str(r.get("tenant_id"))
        payload = r.get("payload") or {}
        if isinstance(payload, dict):
            ctx = payload.get("context") or {}
            if isinstance(ctx, dict) and ctx.get("tenant_id"):
                return str(ctx.get("tenant_id"))
        ctx = r.get("context") or {}
        if isinstance(ctx, dict) and ctx.get("tenant_id"):
            return str(ctx.get("tenant_id"))
        return None

    def _row_action(r: Dict[str, Any]) -> str:
        payload = r.get("payload") or {}
        if isinstance(payload, dict) and payload.get("action"):
            return str(payload.get("action"))
        if r.get("action"):
            return str(r.get("action"))
        if r.get("event_type"):
            return str(r.get("event_type"))
        return ""

    filtered = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if tenant_id and _row_tenant(row) != str(tenant_id):
            continue
        if actor_id:
            actor = row.get("actor_id") or row.get("user_id")
            if str(actor or "") != str(actor_id):
                continue
        if action and action.lower() not in _row_action(row).lower():
            continue
        filtered.append(row)

    return {
        "total": len(filtered),
        "items": filtered,
    }


@router.get("/quality")
async def quality_gate_summary(
    limit: int = Query(2000, ge=50, le=20000),
    tenant_id: Optional[str] = Query(None),
    _user: CurrentUser = Depends(_require_admin),
) -> Dict[str, Any]:
    """
    Summarize quality gate results (needs_review + missing fields) from audit logs.
    This allows enterprise ops to spot regressions quickly.
    """
    db = get_db()
    try:
        rows = db.list_audit_logs(limit=limit)
    except Exception:
        rows = []

    total = 0
    needs_review = 0
    missing_unit = 0
    missing_period = 0
    missing_evidence = 0
    missing_currency = 0
    by_reason: Dict[str, int] = {}

    for r in rows or []:
        if not isinstance(r, dict):
            continue
        if (r.get("action") or "") != "quality_gate":
            continue
        ctx = r.get("context") or {}
        if not isinstance(ctx, dict):
            continue
        if tenant_id and str(ctx.get("tenant_id") or "") != str(tenant_id):
            continue
        total += 1
        if ctx.get("needs_review"):
            needs_review += 1
        gate = ctx.get("quality_gate") or {}
        if isinstance(gate, dict):
            missing_unit += int(gate.get("missing_unit_count", 0) or 0)
            missing_period += int(gate.get("missing_period_count", 0) or 0)
            missing_evidence += int(gate.get("missing_evidence_count", 0) or 0)
            # optional: may be absent in older rows
            missing_currency += int(gate.get("missing_currency_count", 0) or 0)
        meta = ctx.get("metadata") or {}
        if isinstance(meta, dict):
            for reason in meta.get("quality_reasons") or []:
                by_reason[str(reason)] = by_reason.get(str(reason), 0) + 1

    return {
        "total": total,
        "needs_review": needs_review,
        "missing_unit_count": missing_unit,
        "missing_period_count": missing_period,
        "missing_evidence_count": missing_evidence,
        "missing_currency_count": missing_currency,
        "by_reason": dict(sorted(by_reason.items(), key=lambda kv: kv[1], reverse=True)[:40]),
    }
