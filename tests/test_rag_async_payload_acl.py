from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import collab, pipeline, rag
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


def test_rag_async_overrides_doc_ids_from_acl(monkeypatch):
    db = InMemoryDB()
    set_db(db)

    # Seed collab file ACL in the same tenant.
    set_tenant_id("t1")
    try:
        store = EnterpriseCollabStore(db)
        space = store.ensure_personal_space(user_id="alice")
        store.register_file(actor_user_id="alice", space_id=space["id"], doc_id="doc_1", visibility="private")
    finally:
        clear_tenant_id()

    captured = {}

    class _FakeQueue:
        def enabled(self) -> bool:
            return True

        def enqueue_rag_query(self, **kwargs):
            captured.update(kwargs)

    # Patch the symbol used by rag API module.
    monkeypatch.setattr(rag, "TaskQueue", lambda: _FakeQueue())
    monkeypatch.setenv("RAG_ASYNC_ENABLED", "1")

    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(collab.router, prefix="/api/v1")
    app.include_router(pipeline.router, prefix="/api/v1")
    app.include_router(rag.router, prefix="/api/v1")
    client = TestClient(app)

    r = client.post(
        "/api/v1/rag/query",
        json={"query": "rates", "mode": "async", "metadata_filter": {"doc_ids": ["evil_doc"]}},
        headers=_headers("alice"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("mode") == "async"
    assert body.get("job_id")

    mf = captured.get("metadata_filter") or {}
    assert isinstance(mf, dict)
    assert mf.get("doc_ids") == ["doc_1"]

