import importlib

import pytest
from fastapi.testclient import TestClient


def _load_app():
    pytest.importorskip("python_multipart")
    import app.main as main

    importlib.reload(main)
    return main.app


def test_tenant_header_required_prod(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("TENANT_HEADER_REQUIRED", "1")
    monkeypatch.setenv("RBAC_ENFORCED", "1")
    monkeypatch.setenv("PUBLIC_DOMAIN", "example.com")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("DB_BACKEND", "memory")
    app = _load_app()

    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 401

    res_ok = client.get("/health", headers={"X-Tenant-Id": "tenant_a"})
    assert res_ok.status_code == 200
