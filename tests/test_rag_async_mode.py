from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import pipeline, rag
from app.db.client import InMemoryDB
from app.db.registry import set_db
from app.middleware.tenant import TenantMiddleware


def _headers(user_id: str, role: str = "analyst", tenant_id: str = "t1"):
    return {
        "X-Preciso-User-Id": user_id,
        "X-Preciso-User-Role": role,
        "X-Tenant-Id": tenant_id,
    }


def test_rag_async_requires_queue(monkeypatch):
    set_db(InMemoryDB())
    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(rag.router, prefix="/api/v1")
    app.include_router(pipeline.router, prefix="/api/v1")
    client = TestClient(app)

    monkeypatch.setenv("RAG_ASYNC_ENABLED", "1")
    monkeypatch.delenv("REDIS_URL", raising=False)

    r = client.post(
        "/api/v1/rag/query",
        json={"query": "rates", "mode": "async"},
        headers=_headers("alice"),
    )
    assert r.status_code == 503
    detail = r.json().get("detail") or {}
    assert isinstance(detail, dict)
    job_id = detail.get("job_id")
    assert job_id

    j = client.get(f"/api/v1/pipeline/jobs/{job_id}", headers=_headers("alice"))
    assert j.status_code == 200
    assert j.json()["status"] == "failed"

