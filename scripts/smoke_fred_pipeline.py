#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from urllib.parse import urljoin

import requests


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def main() -> int:
    base_url = _env("PRECISO_BASE_URL", "http://localhost:8000").rstrip("/") + "/"
    admin_token = _env("ADMIN_API_TOKEN", "")

    # RBAC headers are optional unless RBAC_ENFORCED=1.
    headers = {
        "Content-Type": "application/json",
        "X-Preciso-User-Id": _env("PRECISO_ADMIN_USER_ID", "smoke"),
        "X-Preciso-User-Role": _env("PRECISO_ADMIN_USER_ROLE", "admin"),
    }
    if admin_token:
        headers["X-Admin-Token"] = admin_token

    # 1) Ensure public config endpoint works
    cfg = requests.get(urljoin(base_url, "api/v1/config/public"), timeout=30).json()
    print("public_config.partner_auth.mode:", cfg.get("partner_auth", {}).get("mode"))
    print("public_config.external_keys.secret_store_enabled:", cfg.get("external_keys", {}).get("secret_store_enabled"))

    # 2) Test FRED provider via admin endpoint (requires key to be registered or env FRED_API_KEY set on server)
    test_url = urljoin(base_url, "api/v1/admin/integrations/test/fred")
    r = requests.post(test_url, json={"series_id": "FEDFUNDS", "symbol": "AAPL"}, headers=headers, timeout=60)
    if r.status_code != 200:
        print("FRED test failed:", r.status_code, r.text[:300])
        return 2
    test = r.json()
    print("fred_test.ok:", test.get("ok"))

    # 3) Fetch + ingest FRED series snapshot into raw_documents
    series_url = urljoin(base_url, "api/v1/market/fred/series")
    r2 = requests.get(series_url, params={"series_id": "FEDFUNDS", "limit": 5, "ingest": "true"}, timeout=60)
    if r2.status_code != 200:
        print("FRED series ingest failed:", r2.status_code, r2.text[:300])
        return 3
    out = r2.json()
    print("fred_series_ingest.doc_id:", out.get("doc_id"))
    facts = (out.get("data") or {}).get("facts") or []
    print("fred_series_ingest.facts_count:", len(facts))

    print("OK: FRED path can fetch, normalize, and ingest.")
    print("Next: run DataForge queue generation/annotation to validate HITL/WS8 end-to-end (requires LLM keys).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

