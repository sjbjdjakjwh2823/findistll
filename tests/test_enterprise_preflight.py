import os

from app.core.config import load_settings
from app.core.preflight import collect_preflight
from app.db.client import InMemoryDB


def test_preflight_blocks_missing_prod_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("RBAC_ENFORCED", "0")
    monkeypatch.setenv("TENANT_HEADER_REQUIRED", "0")
    settings = load_settings()
    report = collect_preflight(settings, InMemoryDB())
    assert len(report["blockers"]) > 0


def test_preflight_dev_allows_missing(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.delenv("REDIS_URL", raising=False)
    settings = load_settings()
    report = collect_preflight(settings, InMemoryDB())
    assert "checks" in report
