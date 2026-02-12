from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import pipeline
from app.db.client import InMemoryDB
from app.db.registry import set_db
from app.middleware.tenant import TenantMiddleware


def _headers(user_id: str, role: str = "analyst", tenant_id: str = "t1"):
    return {
        "X-Preciso-User-Id": user_id,
        "X-Preciso-User-Role": role,
        "X-Tenant-Id": tenant_id,
    }


def test_pipeline_dlq_admin_only(monkeypatch):
    db = InMemoryDB()
    set_db(db)

    class _FakeQueue:
        mode = "list"

        def enabled(self) -> bool:
            return True

        def dlq_length(self) -> int:
            return 2

        def dlq_peek_for_tenant(self, *, tenant_id: str, limit: int = 50, scan_limit: int = 500):
            return {
                "items": [{"doc_id": "doc_1", "reason": "boom", "tenant_id": tenant_id}],
                "scanned": 1,
                "matched": 1,
            }

    monkeypatch.setattr(pipeline, "TaskQueue", lambda: _FakeQueue())

    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(pipeline.router, prefix="/api/v1")
    client = TestClient(app)

    r = client.get("/api/v1/pipeline/dlq", headers=_headers("alice", role="analyst"))
    assert r.status_code == 403

    r2 = client.get("/api/v1/pipeline/dlq", headers=_headers("admin", role="admin"))
    assert r2.status_code == 200
    data = r2.json()
    assert data["tenant_id"] == "t1"
    assert data["dlq_length_total"] == 2
    assert data["items"][0]["doc_id"] == "doc_1"


def test_pipeline_dlq_requeue_enqueues_extract(monkeypatch):
    db = InMemoryDB()
    db.raw_documents["doc_1"] = {"id": "doc_1", "processing_status": "dead_letter"}
    set_db(db)

    captured = {"enqueued": []}

    class _FakeQueue:
        mode = "list"

        def enabled(self) -> bool:
            return True

        def dlq_length(self) -> int:
            return 1

        def dlq_pop_for_tenant(self, *, tenant_id: str, count: int = 1, scan_limit: int = 1000):
            assert tenant_id == "t1"
            assert count == 1
            return [{"doc_id": "doc_1", "reason": "boom"}]

        def enqueue_extract(self, doc_id: str, extra=None) -> None:
            captured["enqueued"].append((doc_id, extra or {}))

    monkeypatch.setattr(pipeline, "TaskQueue", lambda: _FakeQueue())

    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(pipeline.router, prefix="/api/v1")
    client = TestClient(app)

    r = client.post("/api/v1/pipeline/dlq/requeue", json={"count": 1}, headers=_headers("admin", role="admin"))
    assert r.status_code == 200
    assert captured["enqueued"][0][0] == "doc_1"
    assert captured["enqueued"][0][1].get("from_dlq") is True
    # Best-effort doc status normalization.
    assert db.raw_documents["doc_1"]["processing_status"] == "queued"

