#!/usr/bin/env python3
from __future__ import annotations

import os
import pathlib
import sys
from typing import Optional


def _get_env(name: str) -> Optional[str]:
    v = (os.getenv(name) or "").strip()
    return v or None


def main() -> int:
    # Ensure repo root is on sys.path when run as a script.
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))

    if len(sys.argv) != 2:
        print("Usage: register_external_key_from_env.py <provider>", file=sys.stderr)
        return 2

    provider = sys.argv[1].strip().lower()
    env_map = {
        "finnhub": "FINNHUB_API_KEY",
        "fred": "FRED_API_KEY",
        "fmp": "FMP_API_KEY",
        "sec": "SEC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
    }
    env_name = env_map.get(provider)
    if not env_name:
        print(f"Unsupported provider: {provider}", file=sys.stderr)
        return 2

    api_key = _get_env(env_name)
    if not api_key:
        print(f"Missing env var: {env_name}", file=sys.stderr)
        return 3

    from app.core.config import load_settings
    from app.db.supabase_db import SupabaseDB
    from app.services.integration_keys import set_registered_key

    settings = load_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        print("Supabase not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY).", file=sys.stderr)
        return 4

    db = SupabaseDB(settings.supabase_url, settings.supabase_service_role_key)
    stored = set_registered_key(db=db, provider=provider, api_key=api_key, label="from_env")
    # Never print plaintext. Only safe metadata.
    print(f"Stored provider key: provider={stored['provider']} id={stored.get('id')} hint={stored.get('hint')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
