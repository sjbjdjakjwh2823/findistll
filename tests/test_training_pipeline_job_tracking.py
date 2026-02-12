from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import pipeline, training
from app.db.client import InMemoryDB
from app.db.registry import set_db
from app.middleware.tenant import TenantMiddleware


def _headers(user_id: str, role: str = "admin", tenant_id: str = "t1"):
    return {
        "X-Preciso-User-Id": user_id,
        "X-Preciso-User-Role": role,
        "X-Tenant-Id": tenant_id,
    }


def test_training_run_creates_pipeline_job(monkeypatch):
    set_db(InMemoryDB())
    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(training.router, prefix="/api/v1")
    app.include_router(pipeline.router, prefix="/api/v1")
    client = TestClient(app)

    # Allow admin endpoints using role-based admin.
    monkeypatch.setenv("RBAC_ENFORCED", "1")
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("TRAINING_PROVIDER", "none")

    r = client.post(
        "/api/v1/training/run",
        json={"dataset_version_id": "dv_1", "model_name": "m1"},
        headers=_headers("admin"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "skipped"
    job_id = body.get("pipeline_job_id")
    assert job_id

    j = client.get(f"/api/v1/pipeline/jobs/{job_id}", headers=_headers("admin"))
    assert j.status_code == 200
    job = j.json()
    assert job["status"] == "completed"
    out = job.get("output_ref") or {}
    assert out.get("status") == "skipped"

