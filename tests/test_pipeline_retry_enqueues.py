from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import pipeline
from app.core.tenant_context import clear_tenant_id, set_tenant_id
from app.db.client import InMemoryDB
from app.db.registry import set_db
from app.middleware.tenant import TenantMiddleware
from app.services.enterprise_collab import EnterpriseCollabStore


def _headers(user_id: str, role: str = "analyst", tenant_id: str = "t1"):
    return {
        "X-Preciso-User-Id": user_id,
        "X-Preciso-User-Role": role,
        "X-Tenant-Id": tenant_id,
    }


def test_pipeline_retry_enqueues_rag(monkeypatch):
    db = InMemoryDB()
    set_db(db)

    captured = {}

    class _FakeQueue:
        def enabled(self) -> bool:
            return True

        def enqueue_rag_query(self, **kwargs):
            captured.update(kwargs)

        def enqueue_extract(self, *_args, **_kwargs):
            raise AssertionError("unexpected extract enqueue")

    monkeypatch.setattr(pipeline, "TaskQueue", lambda: _FakeQueue())

    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(pipeline.router, prefix="/api/v1")
    client = TestClient(app)

    # Create a RAG job.
    res = client.post(
        "/api/v1/pipeline/jobs/submit",
        json={
            "job_type": "rag",
            "flow": "interactive",
            "input_ref": {
                "query": "rates",
                "top_k": 5,
                "threshold": 0.6,
                "metadata_filter": {"doc_ids": ["doc_1"]},
                "role": "analyst",
            },
        },
        headers=_headers("alice"),
    )
    assert res.status_code == 200
    job_id = res.json()["id"]

    # Mark failed so it becomes retryable.
    set_tenant_id("t1")
    try:
        store = EnterpriseCollabStore(db)
        store.update_pipeline_job_status(actor_user_id="alice", job_id=job_id, status="failed", error="boom")
    finally:
        clear_tenant_id()

    r2 = client.post(f"/api/v1/pipeline/jobs/{job_id}/retry", headers=_headers("alice"))
    assert r2.status_code == 200
    assert captured.get("job_id") == job_id
    assert captured.get("query") == "rates"
    mf = captured.get("metadata_filter") or {}
    assert mf.get("doc_ids") == ["doc_1"]


def test_pipeline_retry_enqueues_ingest(monkeypatch):
    db = InMemoryDB()
    set_db(db)

    captured = {}

    class _FakeQueue:
        def enabled(self) -> bool:
            return True

        def enqueue_extract(self, doc_id, extra=None):
            captured["doc_id"] = doc_id
            captured["extra"] = extra or {}

        def enqueue_rag_query(self, *_args, **_kwargs):
            raise AssertionError("unexpected rag enqueue")

    monkeypatch.setattr(pipeline, "TaskQueue", lambda: _FakeQueue())

    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(pipeline.router, prefix="/api/v1")
    client = TestClient(app)

    res = client.post(
        "/api/v1/pipeline/jobs/submit",
        json={
            "job_type": "ingest",
            "flow": "interactive",
            "input_ref": {"doc_id": "doc_123"},
        },
        headers=_headers("alice"),
    )
    assert res.status_code == 200
    job_id = res.json()["id"]

    set_tenant_id("t1")
    try:
        store = EnterpriseCollabStore(db)
        store.update_pipeline_job_status(actor_user_id="alice", job_id=job_id, status="failed", error="boom")
    finally:
        clear_tenant_id()

    r2 = client.post(f"/api/v1/pipeline/jobs/{job_id}/retry", headers=_headers("alice"))
    assert r2.status_code == 200
    assert captured.get("doc_id") == "doc_123"
    assert captured.get("extra", {}).get("job_id") == job_id

