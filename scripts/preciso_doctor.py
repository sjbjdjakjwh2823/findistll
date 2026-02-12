#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

import httpx


def _get(url: str) -> Dict[str, Any]:
    with httpx.Client(timeout=10) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.json()


def main() -> int:
    base_url = os.getenv("PRECISO_BASE_URL", "http://localhost:8000")
    status_url = f"{base_url}/api/v1/status"

    try:
        payload = _get(status_url)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "fix": "Check PRECISO_BASE_URL"}))
        return 2

    blockers = payload.get("blockers", [])
    warnings = payload.get("warnings", [])
    warnings.extend(_check_unstructured_patch())

    report = {
        "ok": len(blockers) == 0,
        "blockers": blockers,
        "warnings": warnings,
        "runtime": payload.get("runtime", {}),
    }
    print(json.dumps(report, indent=2))
    return 0 if len(blockers) == 0 else 2


def _check_unstructured_patch() -> list[dict]:
    warnings: list[dict] = []
    repo_root = os.getenv("PRECISO_REPO_ROOT", "/Users/leesangmin/Desktop/preciso")
    section_file = os.path.join(
        repo_root,
        "vendor/finrobot/data_source/filings_src/prepline_sec_filings/api/section.py",
    )
    if not os.path.exists(section_file):
        return warnings
    try:
        with open(section_file, "r", encoding="utf-8") as handle:
            content = handle.read()
    except Exception as exc:
        warnings.append(
            {
                "check": "unstructured_api_patch",
                "status": "warn",
                "reason": f"Failed to read section.py: {exc}",
            }
        )
        return warnings

    if "logger = logging.getLogger(__name__)" not in content:
        warnings.append(
            {
                "check": "unstructured_api_patch",
                "status": "warn",
                "reason": "Generated section.py missing logging patch",
                "fix": "Run: /Users/leesangmin/Desktop/preciso/venv/bin/python /Users/leesangmin/Desktop/preciso/scripts/patch_unstructured_api.py",
            }
        )
    return warnings


if __name__ == "__main__":
    sys.exit(main())
