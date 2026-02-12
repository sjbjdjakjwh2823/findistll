from __future__ import annotations

import os
import logging
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.services.secret_store import encrypt_secret, try_decrypt, secret_store_enabled

logger = logging.getLogger(__name__)

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _local_store_path() -> Path:
    # Encrypted ciphertext is still stored; plaintext is never written.
    p = (os.getenv("INTEGRATION_KEYS_FILE") or "").strip()
    if p:
        return Path(p).expanduser()
    return Path(__file__).resolve().parents[2] / "artifacts" / "integration_secrets.json"


def _load_local_store() -> Dict[str, Any]:
    path = _local_store_path()
    if not path.exists():
        return {"keys": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"keys": []}


def _save_local_store(data: Dict[str, Any]) -> None:
    path = _local_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


PROVIDER_ENV_MAP: Dict[str, str] = {
    "finnhub": "FINNHUB_API_KEY",
    "fred": "FRED_API_KEY",
    "fmp": "FMP_API_KEY",
    "sec": "SEC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def normalize_provider(provider: str) -> str:
    p = (provider or "").strip().lower()
    aliases = {
        "sec-api": "sec",
        "sec_api": "sec",
        "financialmodelingprep": "fmp",
        "google": "gemini",
    }
    return aliases.get(p, p)


def get_env_key(provider: str) -> Optional[str]:
    env = PROVIDER_ENV_MAP.get(provider)
    if not env:
        return None
    return (os.getenv(env) or "").strip() or None


def get_registered_key(*, db: Optional[Any], provider: str) -> Optional[str]:
    if not secret_store_enabled():
        return None

    # Prefer DB when available.
    if db is not None:
        try:
            res = (
                db.client.table("integration_secrets")
                .select("ciphertext")
                .eq("provider", provider)
                .is_("revoked_at", None)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            row = (res.data or [None])[0]
            if row:
                return try_decrypt(row.get("ciphertext"))
        except Exception:
            # Fall back to local store when DB schema is missing/unreachable.
            logger.warning("integration_secrets lookup failed; falling back to local store", exc_info=True)

    # Local file fallback (enterprise on-prem / DB bootstrap not yet applied).
    store = _load_local_store()
    keys = store.get("keys") or []
    for item in keys:
        if item.get("provider") == provider and not item.get("revoked_at"):
            return try_decrypt(item.get("ciphertext"))
    return None


def resolve_integration_key(*, db: Optional[Any], provider: str) -> Optional[str]:
    provider = normalize_provider(provider)
    return get_env_key(provider) or get_registered_key(db=db, provider=provider)


def set_registered_key(*, db: Any, provider: str, api_key: str, label: Optional[str] = None) -> Dict[str, Any]:
    provider = normalize_provider(provider)
    cipher = encrypt_secret(api_key)
    payload: Dict[str, Any] = {
        "provider": provider,
        "ciphertext": cipher.ciphertext,
        "hint": cipher.hint,
        "label": label,
        "created_at": _utc_now_iso(),
    }
    # Prefer DB; fall back to local file if DB isn't ready.
    if db is not None:
        try:
            res = db.client.table("integration_secrets").insert(payload).execute()
            if res.data:
                row = res.data[0]
                return {
                    "provider": provider,
                    "id": row.get("id"),
                    "hint": row.get("hint"),
                    "label": row.get("label"),
                    "created_at": row.get("created_at"),
                }
        except Exception as exc:
            logger.warning("swallowed exception", exc_info=exc)

    store = _load_local_store()
    store.setdefault("keys", [])
    store["keys"].insert(
        0,
        {
            "id": f"local_{provider}_{int(datetime.now(timezone.utc).timestamp())}",
            **payload,
            "revoked_at": None,
            "last_tested_at": None,
            "last_test_status": None,
        },
    )
    _save_local_store(store)
    return {"provider": provider, "id": store["keys"][0]["id"], "hint": cipher.hint, "label": label, "created_at": payload["created_at"]}


def revoke_registered_key(*, db: Any, provider: str) -> None:
    provider = normalize_provider(provider)
    if db is not None:
        try:
            db.client.table("integration_secrets").update({"revoked_at": _utc_now_iso()}).eq("provider", provider).execute()
            return
        except Exception as exc:
            logger.warning("swallowed exception", exc_info=exc)
    store = _load_local_store()
    keys = store.get("keys") or []
    for item in keys:
        if item.get("provider") == provider and not item.get("revoked_at"):
            item["revoked_at"] = _utc_now_iso()
    _save_local_store(store)


def list_registered_keys(*, db: Any, limit: int = 50) -> list[dict]:
    if db is not None:
        try:
            res = (
                db.client.table("integration_secrets")
                .select("id, provider, hint, label, created_at, revoked_at, last_tested_at, last_test_status")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as exc:
            logger.warning("swallowed exception", exc_info=exc)

    store = _load_local_store()
    out = []
    for item in (store.get("keys") or [])[:limit]:
        out.append(
            {
                "id": item.get("id"),
                "provider": item.get("provider"),
                "hint": item.get("hint"),
                "label": item.get("label"),
                "created_at": item.get("created_at"),
                "revoked_at": item.get("revoked_at"),
                "last_tested_at": item.get("last_tested_at"),
                "last_test_status": item.get("last_test_status"),
            }
        )
    return out
