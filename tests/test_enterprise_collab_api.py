from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.client import InMemoryDB
from app.db.registry import set_db
from app.middleware.tenant import TenantMiddleware
from app.api.v1 import collab, pipeline, rag


def _headers(user_id: str, role: str = "analyst", tenant_id: str = "t1"):
    return {
        "X-Preciso-User-Id": user_id,
        "X-Preciso-User-Role": role,
        "X-Tenant-Id": tenant_id,
    }


def test_collab_pipeline_happy_path():
    set_db(InMemoryDB())
    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(collab.router, prefix="/api/v1")
    app.include_router(pipeline.router, prefix="/api/v1")
    app.include_router(rag.router, prefix="/api/v1")
    client = TestClient(app)

    # 1) friend request / accept
    r = client.post(
        "/api/v1/collab/contacts/request",
        json={"target_user_id": "bob"},
        headers=_headers("alice"),
    )
    assert r.status_code == 200
    contact_id = r.json()["id"]

    r = client.post(
        "/api/v1/collab/contacts/accept",
        json={"contact_id": contact_id},
        headers=_headers("bob"),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"

    # 2) team + membership
    r = client.post("/api/v1/collab/teams", json={"name": "Risk Team"}, headers=_headers("alice"))
    assert r.status_code == 200
    team_id = r.json()["id"]

    r = client.post(
        f"/api/v1/collab/teams/{team_id}/members",
        json={"user_id": "bob", "role": "member"},
        headers=_headers("alice"),
    )
    assert r.status_code == 200

    # 3) team space + file register
    r = client.post(
        "/api/v1/collab/spaces",
        json={"type": "team", "name": "Risk Shared", "team_id": team_id},
        headers=_headers("alice"),
    )
    assert r.status_code == 200
    space_id = r.json()["id"]

    r = client.post(
        "/api/v1/collab/files/upload",
        json={"space_id": space_id, "doc_id": "doc_1", "visibility": "team"},
        headers=_headers("alice"),
    )
    assert r.status_code == 200
    file_id = r.json()["id"]

    # 4) bob can read shared team file
    r = client.get(f"/api/v1/collab/files/{file_id}", headers=_headers("bob"))
    assert r.status_code == 200
    assert r.json()["item"]["doc_id"] == "doc_1"

    r = client.get("/api/v1/collab/files?limit=20", headers=_headers("bob"))
    assert r.status_code == 200
    assert any(str(it.get("id")) == str(file_id) for it in r.json().get("items", []))

    # 5) direct transfer (friend-required) and inbox ack
    r = client.post(
        "/api/v1/collab/transfers/send",
        json={"receiver_user_id": "bob", "file_id": file_id, "message": "please review"},
        headers=_headers("alice"),
    )
    assert r.status_code == 200
    transfer_id = r.json()["id"]

    r = client.get("/api/v1/collab/transfers/inbox", headers=_headers("bob"))
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1

    r = client.post(
        f"/api/v1/collab/transfers/{transfer_id}/ack",
        json={"status": "accepted"},
        headers=_headers("bob"),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"

    # 6) tenant pipeline submit + status
    r = client.post(
        "/api/v1/pipeline/jobs/submit",
        json={"job_type": "rag", "flow": "interactive", "input_ref": {"query": "rates"}},
        headers=_headers("alice"),
    )
    assert r.status_code == 200
    job_id = r.json()["id"]

    r = client.get(f"/api/v1/pipeline/jobs/{job_id}", headers=_headers("alice"))
    assert r.status_code == 200
    assert r.json()["status"] == "pending"

    r = client.get("/api/v1/pipeline/tenant-status", headers=_headers("alice"))
    assert r.status_code == 200
    assert "queue_depth" in r.json()


def test_collab_isolation_cross_tenant():
    set_db(InMemoryDB())
    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(collab.router, prefix="/api/v1")
    app.include_router(pipeline.router, prefix="/api/v1")
    app.include_router(rag.router, prefix="/api/v1")
    client = TestClient(app)

    # t1 request
    r = client.post(
        "/api/v1/collab/contacts/request",
        json={"target_user_id": "bob"},
        headers=_headers("alice", tenant_id="t1"),
    )
    assert r.status_code == 200
    contact_id = r.json()["id"]

    # t2 cannot accept t1 contact
    r = client.post(
        "/api/v1/collab/contacts/accept",
        json={"contact_id": contact_id},
        headers=_headers("bob", tenant_id="t2"),
    )
    assert r.status_code in {403, 404}


def test_rag_query_schema_compat():
    set_db(InMemoryDB())
    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(collab.router, prefix="/api/v1")
    app.include_router(pipeline.router, prefix="/api/v1")
    app.include_router(rag.router, prefix="/api/v1")
    client = TestClient(app)
    r = client.post(
        "/api/v1/rag/query",
        json={"query": "interest rate shock", "top_k": 3},
        headers=_headers("alice"),
    )
    assert r.status_code == 200
    payload = r.json()
    assert "evidence" in payload
    assert "cause_chain" in payload
    assert "effect_chain" in payload
    assert "prediction" in payload
    assert "legacy_summary" in payload
