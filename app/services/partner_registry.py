from __future__ import annotations

import hashlib
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pepper() -> str:
    # Optional; improves hash security if set.
    return os.getenv("PARTNER_API_KEY_PEPPER", "")


def generate_partner_api_key() -> str:
    # Human-friendly prefix; treat as secret.
    # Example: pre_live_<32bytes-url-safe>
    return "pre_live_" + secrets.token_urlsafe(32)


def key_prefix(api_key: str) -> str:
    # Used for safe display/log correlation.
    return api_key[:8]


def hash_partner_api_key(api_key: str) -> str:
    payload = (_pepper() + api_key).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass
class PartnerAuthResult:
    ok: bool
    mode: str
    partner_id: Optional[str] = None
    partner_account_id: Optional[str] = None
    key_id: Optional[str] = None


def _parse_env_keys() -> Optional[set[str]]:
    raw = (os.getenv("PARTNER_API_KEYS") or "").strip()
    if not raw:
        return None
    keys = {k.strip() for k in raw.split(",") if k.strip()}
    return keys or None


def _auth_mode(db_present: bool) -> str:
    """
    Partner auth modes:
    - open: allow without key (dev only)
    - env: require PARTNER_API_KEYS
    - db: require partner_api_keys table match
    - env_or_db: accept either
    """
    mode = (os.getenv("PARTNER_AUTH_MODE") or "").strip().lower()
    if mode in {"open", "env", "db", "env_or_db"}:
        return mode

    # Default behavior:
    # - if env keys configured: enforce env keys
    # - else if DB is present: enforce DB keys (production-safe default)
    # - else: open (dev)
    if _parse_env_keys() is not None:
        return "env"
    if db_present:
        return "db"
    return "open"


def current_partner_auth_mode(*, db_present: bool) -> str:
    return _auth_mode(db_present=db_present)


def verify_partner_api_key(
    *,
    db: Optional[Any],
    api_key: Optional[str],
    partner_id: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> PartnerAuthResult:
    """
    Verify partner API key via env list and/or DB-backed registry.
    Returns auth context (partner_id) when DB-backed.
    """
    env_keys = _parse_env_keys()
    db_present = db is not None
    mode = _auth_mode(db_present=db_present)

    if mode == "open":
        return PartnerAuthResult(ok=True, mode=mode, partner_id=partner_id)

    if not api_key:
        return PartnerAuthResult(ok=False, mode=mode)

    # ENV mode: legacy allow-list keys (no partner binding).
    if mode in {"env", "env_or_db"} and env_keys is not None and api_key in env_keys:
        return PartnerAuthResult(ok=True, mode="env", partner_id=partner_id)

    # DB mode: key hash lookup and partner binding.
    if mode in {"db", "env_or_db"} and db is not None:
        try:
            h = hash_partner_api_key(api_key)
            # Join partner_accounts to get stable partner_id for authorization.
            res = (
                db.client.table("partner_api_keys")
                .select(
                    "id, partner_account_id, revoked_at, partner_accounts(partner_id, disabled_at)"
                )
                .eq("key_hash", h)
                .limit(1)
                .execute()
            )
            row = (res.data or [None])[0]
            if not row or row.get("revoked_at"):
                return PartnerAuthResult(ok=False, mode="db")
            acct_raw = row.get("partner_accounts")
            if isinstance(acct_raw, list) and acct_raw:
                acct = acct_raw[0] if isinstance(acct_raw[0], dict) else {}
            elif isinstance(acct_raw, dict):
                acct = acct_raw
            else:
                acct = {}
            acct_partner_id = acct.get("partner_id")
            if acct.get("disabled_at"):
                return PartnerAuthResult(ok=False, mode="db")
            if partner_id and acct_partner_id and partner_id != acct_partner_id:
                return PartnerAuthResult(ok=False, mode="db")

            # best-effort usage tracking
            try:
                db.client.table("partner_api_keys").update(
                    {"last_used_at": _utc_now(), "last_used_user_agent": user_agent}
                ).eq("id", row["id"]).execute()
            except Exception as exc:
                logger.warning("swallowed exception", exc_info=exc)

            return PartnerAuthResult(
                ok=True,
                mode="db",
                partner_id=acct_partner_id,
                partner_account_id=row.get("partner_account_id"),
                key_id=row.get("id"),
            )
        except Exception:
            # Fail closed if DB mode is in effect.
            return PartnerAuthResult(ok=False, mode="db")

    return PartnerAuthResult(ok=False, mode=mode)


def create_partner_account(
    *,
    db: Any,
    partner_id: str,
    name: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "partner_id": partner_id,
        "name": name,
        "metadata": metadata or {},
    }
    res = db.client.table("partner_accounts").insert(payload).execute()
    if not res.data:
        raise RuntimeError("failed to create partner account")
    return res.data[0]


def issue_partner_api_key(
    *,
    db: Any,
    partner_account_id: str,
    label: Optional[str] = None,
) -> Dict[str, Any]:
    api_key = generate_partner_api_key()
    payload: Dict[str, Any] = {
        "partner_account_id": partner_account_id,
        "key_prefix": key_prefix(api_key),
        "key_hash": hash_partner_api_key(api_key),
        "label": label,
    }
    res = db.client.table("partner_api_keys").insert(payload).execute()
    if not res.data:
        raise RuntimeError("failed to issue partner api key")
    created = res.data[0]
    return {"api_key": api_key, "record": created}


def revoke_partner_api_key(*, db: Any, key_id: str) -> None:
    db.client.table("partner_api_keys").update({"revoked_at": _utc_now()}).eq("id", key_id).execute()


def find_partner_account_by_partner_id(*, db: Any, partner_id: str) -> Optional[Dict[str, Any]]:
    res = db.client.table("partner_accounts").select("*").eq("partner_id", partner_id).limit(1).execute()
    row = (res.data or [None])[0]
    return row if isinstance(row, dict) else None
