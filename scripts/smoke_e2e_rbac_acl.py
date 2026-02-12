#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any, Dict, Optional

import httpx


def _wait_http(url: str, timeout_s: int = 20, headers: Optional[Dict[str, str]] = None) -> None:
    start = time.time()
    last = None
    while True:
        try:
            r = httpx.get(url, timeout=2.0, headers=headers)
            last = r.status_code
            if r.status_code == 200:
                return
        except Exception:
            pass
        if time.time() - start > timeout_s:
            raise RuntimeError(f"backend did not become ready: {url} (last_status={last})")
        time.sleep(0.25)


def _req(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    json: Optional[Dict[str, Any]] = None,
    tenant: str = "public",
    user_id: str = "alice",
    role: str = "auto",
    admin_token: Optional[str] = None,
) -> httpx.Response:
    headers = {
        "X-Tenant-Id": tenant,
        "X-Preciso-User-Id": user_id,
        "X-Preciso-User-Role": role,
    }
    if admin_token:
        headers["X-Admin-Token"] = admin_token
    return client.request(method, path, json=json, headers=headers)


def main() -> int:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backend_url = os.getenv("SMOKE_BACKEND_URL", "http://127.0.0.1:18080")
    admin_token = "dev-admin-token"

    # Prefer repo venv python so dependencies match runtime.
    venv_py = os.path.join(repo, "venv", "bin", "python")
    py = venv_py if os.path.exists(venv_py) else sys.executable

    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "dev",
            "DB_BACKEND": "memory",
            "RBAC_ENFORCED": "1",
            "TENANT_HEADER_REQUIRED": "1",
            "ADMIN_API_TOKEN": admin_token,
            "DEFAULT_TENANT_ID": "public",
            "METRICS_LOGGING_ENABLED": "0",
            # Ensure no accidental external calls during smoke.
            "SUPABASE_URL": "",
            "SUPABASE_SERVICE_ROLE_KEY": "",
        }
    )

    proc = subprocess.Popen(
        [
            py,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            backend_url.split(":")[-1],
            "--log-level",
            "warning",
        ],
        cwd=repo,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_http(
            f"{backend_url}/health",
            timeout_s=25,
            headers={
                "X-Tenant-Id": "public",
                "X-Preciso-User-Id": "smoke",
                "X-Preciso-User-Role": "admin",
                "X-Admin-Token": admin_token,
            },
        )

        with httpx.Client(base_url=backend_url, timeout=10.0) as c:
            # 1) Seed org roles (admin-only)
            for user_id, role in [
                ("alice", "analyst"),
                ("bob", "analyst"),
                ("rev", "reviewer"),
                ("aud", "auditor"),
                ("adm", "admin"),
            ]:
                r = _req(
                    c,
                    "POST",
                    "/api/v1/org/users",
                    json={"user_id": user_id, "role": role, "status": "active"},
                    user_id="adm",
                    role="admin",
                    admin_token=admin_token,
                )
                assert r.status_code == 200, r.text

            # 2) Ingest document as alice (should auto-register collab file in personal space)
            r = _req(
                c,
                "POST",
                "/api/v1/ingest/document",
                json={
                    "source": "upload",
                    "ticker": "ACME",
                    "document_type": "note",
                    "document_date": "2026-02-12",
                    "content": {"text": "ACME revenue grew 10% YoY. Debt ratio 3.2x."},
                    "metadata": {},
                },
                user_id="alice",
                role="auto",
            )
            assert r.status_code == 200, r.text
            doc_id = r.json()["document_id"]

            # 3) Bob cannot see alice docs by default
            r = _req(c, "GET", "/api/v1/ingest/documents?limit=50", user_id="bob", role="auto")
            assert r.status_code == 200, r.text
            docs = r.json().get("documents") or []
            assert all(str(d.get("id")) != str(doc_id) for d in docs), "bob saw alice doc"

            # 4) Bob cannot approve (must be reviewer/admin)
            r = _req(
                c,
                "POST",
                f"/api/v1/approvals/cases/{doc_id}/approve",
                json={"decision": {"decision": "ok"}},
                user_id="bob",
                role="auto",
            )
            assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"

            # 5) Reviewer passes role gate (may 404 because case doesn't exist, but must not be 403)
            r = _req(
                c,
                "POST",
                f"/api/v1/approvals/cases/{doc_id}/approve",
                json={"decision": {"decision": "ok"}},
                user_id="rev",
                role="auto",
            )
            assert r.status_code in (404, 409, 200), f"unexpected {r.status_code} {r.text}"

            # 6) Setup friendship + share collab file, then bob can see it via collab list
            # List alice spaces -> pick personal
            r = _req(c, "GET", "/api/v1/collab/spaces", user_id="alice", role="auto")
            assert r.status_code == 200, r.text
            spaces = r.json().get("items") or []
            assert spaces, "no spaces for alice"

            # List files visible to alice -> pick doc_id match
            r = _req(c, "GET", "/api/v1/collab/files?limit=200", user_id="alice", role="auto")
            assert r.status_code == 200, r.text
            files = r.json().get("items") or []
            fmatch = None
            for f in files:
                if str(f.get("doc_id")) == str(doc_id):
                    fmatch = f
                    break
            assert fmatch, "no collab file auto-registered for doc"
            file_id = fmatch["id"]

            # Friend request (alice->bob) then accept (bob)
            r = _req(c, "POST", "/api/v1/collab/contacts/request", json={"target_user_id": "bob"}, user_id="alice", role="auto")
            assert r.status_code == 200, r.text
            contact_id = r.json().get("id")
            assert contact_id
            r = _req(c, "POST", "/api/v1/collab/contacts/accept", json={"contact_id": contact_id}, user_id="bob", role="auto")
            assert r.status_code == 200, r.text

            # Share file directly to bob
            r = _req(
                c,
                "POST",
                f"/api/v1/collab/files/{file_id}/share",
                json={"principal_type": "user", "principal_id": "bob", "permission": "read"},
                user_id="alice",
                role="auto",
            )
            assert r.status_code == 200, r.text

            # Now bob sees shared file
            r = _req(c, "GET", "/api/v1/collab/files?limit=200", user_id="bob", role="auto")
            assert r.status_code == 200, r.text
            bfiles = r.json().get("items") or []
            assert any(str(f.get("doc_id")) == str(doc_id) for f in bfiles), "bob still cannot see shared file"

            # 7) RAG query: bob should only retrieve evidence from allowed docs
            r = _req(
                c,
                "POST",
                "/api/v1/rag/query",
                json={"query": "ACME revenue", "top_k": 5, "threshold": 0.1, "metadata_filter": {}},
                user_id="bob",
                role="auto",
            )
            assert r.status_code == 200, r.text
            ev = r.json().get("evidence") or []
            if ev:
                for e in ev:
                    md = e.get("metadata") or {}
                    assert str(md.get("doc_id") or "") == str(doc_id), f"unexpected doc_id in evidence: {md}"

        print("SMOKE OK: RBAC/ACL/RAG scoping")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        out = ""
        try:
            if proc.stdout:
                out = proc.stdout.read()[-4000:]
        except Exception:
            out = ""
        if out:
            print("\n[backend log tail]\n" + out)


if __name__ == "__main__":
    raise SystemExit(main())
