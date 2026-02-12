#!/usr/bin/env python3
from __future__ import annotations

import os
import time
from urllib.parse import urlencode

import requests


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _split_csv(v: str) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def ingest_fred_series(base_url: str, series_id: str, limit: int) -> dict:
    url = f"{base_url}/api/v1/market/fred/series?{urlencode({'series_id': series_id, 'limit': limit, 'ingest': 'true'})}"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.json()


def ingest_key_rates(base_url: str) -> dict:
    url = f"{base_url}/api/v1/market/fred/key-rates?ingest=true"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.json()


def run_once() -> int:
    base_url = _env("PRECISO_BASE_URL", "http://127.0.0.1:8011").rstrip("/")
    series = _split_csv(_env("MARKET_INGEST_FRED_SERIES", "FEDFUNDS,GS10,T10Y2Y"))
    limit = int(_env("MARKET_INGEST_FRED_LIMIT", "5") or "5")

    print("base_url:", base_url)
    print("fred_series:", ",".join(series))

    results = []
    for sid in series:
        out = ingest_fred_series(base_url, sid, limit=limit)
        results.append({"series_id": sid, "doc_id": out.get("doc_id"), "facts": len((out.get("data") or {}).get("facts") or [])})

    kr = ingest_key_rates(base_url)
    results.append({"series_id": "FRED_KEY_RATES", "doc_id": kr.get("doc_id"), "facts": len((kr.get("data") or {}).get("facts") or [])})

    print("results:", results)
    return 0


def main() -> int:
    mode = _env("MARKET_INGEST_MODE", "once")
    interval_s = int(_env("MARKET_INGEST_INTERVAL_S", "3600") or "3600")
    if mode == "once":
        return run_once()

    while True:
        try:
            run_once()
        except Exception as e:
            print("ingest loop error:", str(e)[:200])
        time.sleep(interval_s)


if __name__ == "__main__":
    raise SystemExit(main())

