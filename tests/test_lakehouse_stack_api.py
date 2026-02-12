from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import governance, lakehouse, mlflow_api, rag
from app.db.client import InMemoryDB
from app.db.registry import set_db
from app.middleware.tenant import TenantMiddleware


def _headers(user_id: str = "alice", role: str = "admin", tenant_id: str = "t1"):
    return {
        "X-Preciso-User-Id": user_id,
        "X-Preciso-User-Role": role,
        "X-Tenant-Id": tenant_id,
    }


def _client_with_inmemory():
    db = InMemoryDB()
    set_db(db)
    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(lakehouse.router, prefix="/api/v1")
    app.include_router(mlflow_api.router, prefix="/api/v1")
    app.include_router(governance.router, prefix="/api/v1")
    app.include_router(rag.router, prefix="/api/v1")
    return TestClient(app), db


def test_lakehouse_mlflow_governance_api_smoke():
    client, _ = _client_with_inmemory()

    r = client.post(
        "/api/v1/lakehouse/jobs/submit",
        json={"job_type": "silver_transform", "priority": "high", "payload": {"table": "silver.fin_facts"}},
        headers=_headers(),
    )
    assert r.status_code == 200
    job_id = r.json()["job"]["id"]

    r = client.get(f"/api/v1/lakehouse/jobs/{job_id}", headers=_headers())
    assert r.status_code == 200
    assert r.json()["job"]["job_type"] == "silver_transform"

    r = client.get("/api/v1/mlflow/experiments", headers=_headers())
    assert r.status_code == 200
    assert "experiments" in r.json()

    r = client.post(
        "/api/v1/mlflow/runs/start",
        json={
            "dataset_version_id": None,
            "model_name": "preciso-fin",
            "params": {"lr": 0.001},
            "metrics": {"faithfulness": 0.82},
            "artifacts": {"report": "ok"},
        },
        headers=_headers(),
    )
    assert r.status_code == 200
    assert r.json()["run"]["model_name"] == "preciso-fin"

    r = client.post(
        "/api/v1/governance/policies/apply",
        json={"domain": "fundamental", "principal": "finance-team", "role": "analyst", "effect": "allow", "rules": {}},
        headers=_headers(),
    )
    assert r.status_code == 200

    r = client.get("/api/v1/governance/policies", headers=_headers())
    assert r.status_code == 200
    assert len(r.json()["policies"]) >= 1


def test_rag_query_returns_delta_source_version_field():
    client, db = _client_with_inmemory()
    db.raw_documents["doc_1"] = {
        "id": "doc_1",
        "raw_content": {"text": "FEDFUNDS increased and credit risk rose."},
        "metadata": {"delta_source_version": "silver.fin_facts@v12"},
        "tenant_id": "t1",
    }

    r = client.post(
        "/api/v1/rag/query",
        json={"query": "FEDFUNDS increased", "top_k": 3},
        headers=_headers(),
    )
    assert r.status_code == 200
    payload = r.json()
    assert "delta_source_version" in payload
