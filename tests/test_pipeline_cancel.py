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


def test_pipeline_job_cancel_by_owner():
    db = InMemoryDB()
    set_db(db)

    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(pipeline.router, prefix="/api/v1")
    client = TestClient(app)

    res = client.post(
        "/api/v1/pipeline/jobs/submit",
        json={"job_type": "rag", "flow": "interactive", "input_ref": {"query": "q"}},
        headers=_headers("alice"),
    )
    assert res.status_code == 200
    job_id = res.json()["id"]

    r2 = client.post(f"/api/v1/pipeline/jobs/{job_id}/cancel", headers=_headers("alice"))
    assert r2.status_code == 200
    assert r2.json()["status"] == "canceled"


def test_pipeline_job_cancel_denied_for_other_user():
    db = InMemoryDB()
    set_db(db)

    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(pipeline.router, prefix="/api/v1")
    client = TestClient(app)

    res = client.post(
        "/api/v1/pipeline/jobs/submit",
        json={"job_type": "rag", "flow": "interactive", "input_ref": {"query": "q"}},
        headers=_headers("alice"),
    )
    assert res.status_code == 200
    job_id = res.json()["id"]

    r2 = client.post(f"/api/v1/pipeline/jobs/{job_id}/cancel", headers=_headers("bob"))
    assert r2.status_code == 403

