from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.auth import CurrentUser, get_current_user
from app.core.admin_auth import require_admin
from app.db.registry import get_db


router = APIRouter(prefix="/admin/retention", tags=["Admin - Retention"])


def _require_admin(
    user: CurrentUser = Depends(get_current_user),
    x_admin_token: Optional[str] = Header(default=None),
) -> CurrentUser:
    return require_admin(user, x_admin_token)


@router.post("/run")
async def run_retention(_user: CurrentUser = Depends(_require_admin)):
    db = get_db()
    now = datetime.now(tz=timezone.utc)
    retention = {
        "audit_logs": int(os.getenv("RETENTION_DAYS_AUDIT", "365")),
        "audit_events": int(os.getenv("RETENTION_DAYS_AUDIT", "365")),
        "ops_audit_logs": int(os.getenv("RETENTION_DAYS_AUDIT", "365")),
        "documents": int(os.getenv("RETENTION_DAYS_DOCS", "0")),
        "raw_documents": int(os.getenv("RETENTION_DAYS_DOCS", "0")),
        "spoke_a_samples": int(os.getenv("RETENTION_DAYS_SPOKES", "0")),
        "spoke_b_artifacts": int(os.getenv("RETENTION_DAYS_SPOKES", "0")),
        "spoke_c_rag_context": int(os.getenv("RETENTION_DAYS_SPOKES", "0")),
        "spoke_d_graph": int(os.getenv("RETENTION_DAYS_SPOKES", "0")),
    }
    audit_immutable = os.getenv("AUDIT_IMMUTABLE", "0") == "1"
    upload_days = int(os.getenv("RETENTION_DAYS_UPLOAD_ARTIFACTS", "0") or "0")

    if not hasattr(db, "client"):
        return {"ok": False, "error": "retention not supported for this backend"}

    try:
        results = {}
        for table, days in retention.items():
            if days <= 0:
                results[table] = {"skipped": True, "reason": "retention disabled"}
                continue
            if audit_immutable and table in {"audit_logs", "audit_events", "ops_audit_logs"}:
                results[table] = {"skipped": True, "reason": "audit immutability enabled"}
                continue
            cutoff = now - timedelta(days=days)
            try:
                db.client.table(table).delete().lt("timestamp", cutoff.isoformat()).execute()
                results[table] = {"ok": True, "cutoff": cutoff.isoformat()}
            except Exception as exc:
                results[table] = {"ok": False, "error": str(exc)}
        if upload_days > 0:
            cutoff = now - timedelta(days=upload_days)
            results["upload_artifacts"] = _cleanup_upload_artifacts(cutoff)
        else:
            results["upload_artifacts"] = {"skipped": True, "reason": "retention disabled"}
        return {"ok": True, "results": results}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _cleanup_upload_artifacts(cutoff: datetime) -> dict:
    try:
        repo_root = Path(os.getenv("PRECISO_REPO_ROOT", "")).expanduser()
        if not repo_root:
            repo_root = Path(__file__).resolve().parents[3]
        uploads_dir = (repo_root / "artifacts" / "uploads").resolve()
        if not uploads_dir.exists():
            return {"ok": True, "deleted": 0, "skipped": True, "reason": "no uploads dir"}
        # Safety: only delete under `.../preciso/artifacts/uploads`.
        if "artifacts/uploads" not in str(uploads_dir).replace("\\", "/"):
            return {"ok": False, "error": f"refusing to delete outside uploads dir: {uploads_dir}"}

        deleted = 0
        kept = 0
        for p in uploads_dir.glob("**/*"):
            if not p.is_file():
                continue
            try:
                mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            except Exception:
                kept += 1
                continue
            if mtime < cutoff:
                try:
                    p.unlink()
                    deleted += 1
                except Exception:
                    kept += 1
            else:
                kept += 1
        return {"ok": True, "deleted": deleted, "kept": kept, "cutoff": cutoff.isoformat()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
