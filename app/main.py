from pathlib import Path

import os
import sys
import subprocess
import logging
import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from app.core.config import load_settings
from app.core.preflight import collect_preflight
from app.api.v1 import dataforge
from app.api.v1 import extract
from app.api.v1 import ingest
from app.api.v1 import generate
from app.api.v1 import annotate
from app.api.v1 import approval
from app.api.v1 import opsgraph
from app.api.v1 import export
from app.api.v1 import metrics
from app.api.v1 import retrieval
from app.api.v1 import multi_agent
from app.api.v1 import datasets
from app.api.v1 import quant
from app.api.v1 import market
from app.api.v1 import partners
from app.api.v1 import admin_partners
from app.api.v1 import config_public
from app.api.v1 import config_admin
from app.api.v1 import admin_integrations
from app.api.v1 import admin_supabase
from app.api.v1 import admin_connectivity
from app.api.v1 import admin_retention
from app.api.v1 import causal
from app.api.v1 import admin_logs
from app.api.v1 import training
from app.api.v1 import collab
from app.api.v1 import pipeline
from app.api.v1 import rag
from app.api.v1 import policy
from app.api.v1 import console
from app.api.v1 import lakehouse
from app.api.v1 import mlflow_api
from app.api.v1 import governance
from app.api.v1 import org
from app.middleware.cache_control import CacheControlMiddleware
from app.middleware.audit import AuditMiddleware
from app.middleware.metrics import MetricsMiddleware
from app.services.audit_logger import AuditLogger
from app.middleware.tenant import TenantMiddleware
from app.middleware.trace import TraceMiddleware
from app.db.registry import set_db
from app.db.supabase_db import SupabaseDB
from app.db.postgres_db import PostgresDB
from app.db.client import InMemoryDB
from app.middleware.rate_limit import RateLimitMiddleware
from app.core.logging import configure_logging
from app.services.auto_scaler import PerformanceAutoScaler
from app.services.market_scheduler import MarketScheduler
from app.services.market_data import market_data_service

_settings = load_settings()
configure_logging("backend")
logger = logging.getLogger(__name__)
_db_backend = (_settings.db_backend or "").strip().lower()
if not _db_backend:
    _db_backend = "supabase" if _settings.supabase_url and _settings.supabase_service_role_key else "memory"

if _db_backend == "postgres" and _settings.database_url:
    _db = PostgresDB(_settings.database_url)
elif _db_backend == "supabase" and _settings.supabase_url and _settings.supabase_service_role_key:
    _db = SupabaseDB(_settings.supabase_url, _settings.supabase_service_role_key)
else:
    _db = InMemoryDB()
set_db(_db)

@asynccontextmanager
async def lifespan(app: FastAPI):
    _apply_unstructured_patch()
    report = collect_preflight(_settings, _db)
    if _settings.app_env.lower() == "prod" and report["blockers"]:
        blocker_keys = [c["key"] for c in report["blockers"]]
        raise RuntimeError(f"Enterprise preflight failed (blockers): {', '.join(blocker_keys)}")
    scaler = PerformanceAutoScaler()
    task = asyncio.create_task(scaler.run())
    scheduler = MarketScheduler()
    task_scheduler = asyncio.create_task(scheduler.run())
    yield
    task.cancel()
    task_scheduler.cancel()
    try:
        await market_data_service.close()
    except Exception:
        logger.warning("market data session close failed", exc_info=True)
    for t in (task, task_scheduler):
        try:
            await t
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.warning("background task shutdown error", exc_info=True)

app = FastAPI(lifespan=lifespan)

app.add_middleware(TenantMiddleware)
app.add_middleware(TraceMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CacheControlMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(AuditMiddleware, audit_logger=AuditLogger(_db))
app.add_middleware(RateLimitMiddleware)

_ui_path = Path(__file__).resolve().parent / "ui"
legacy_ui_enabled = os.getenv("LEGACY_UI_ENABLED", "0") == "1"
if _ui_path.exists() and (_settings.app_env.lower() != "prod" or legacy_ui_enabled):
    app.mount("/ui", StaticFiles(directory=str(_ui_path), html=True), name="ui")

app.include_router(dataforge.router, prefix="/api/v1")
app.include_router(extract.router, prefix="/api/v1")
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(generate.router, prefix="/api/v1")
app.include_router(annotate.router, prefix="/api/v1")
app.include_router(approval.router, prefix="/api/v1")
app.include_router(opsgraph.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(retrieval.router, prefix="/api/v1")
app.include_router(multi_agent.router, prefix="/api/v1")
app.include_router(datasets.router, prefix="/api/v1")
app.include_router(quant.router, prefix="/api/v1")
app.include_router(market.router, prefix="/api/v1")
app.include_router(partners.router, prefix="/api/v1")
app.include_router(admin_partners.router, prefix="/api/v1")
app.include_router(config_public.router, prefix="/api/v1")
app.include_router(config_admin.router, prefix="/api/v1")
app.include_router(admin_integrations.router, prefix="/api/v1")
app.include_router(admin_supabase.router, prefix="/api/v1")
app.include_router(admin_connectivity.router, prefix="/api/v1")
app.include_router(admin_retention.router, prefix="/api/v1")
app.include_router(causal.router, prefix="/api/v1")
app.include_router(admin_logs.router, prefix="/api/v1")
app.include_router(training.router, prefix="/api/v1")
app.include_router(collab.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")
app.include_router(rag.router, prefix="/api/v1")
app.include_router(policy.router, prefix="/api/v1")
app.include_router(console.router, prefix="/api/v1")
app.include_router(lakehouse.router, prefix="/api/v1")
app.include_router(mlflow_api.router, prefix="/api/v1")
app.include_router(governance.router, prefix="/api/v1")
app.include_router(org.router, prefix="/api/v1")

def _apply_unstructured_patch() -> None:
    repo_root = os.getenv("PRECISO_REPO_ROOT", str(Path(__file__).resolve().parents[1]))
    patch_script = Path(repo_root) / "scripts" / "patch_unstructured_api.py"
    if not patch_script.exists():
        return
    try:
        result = subprocess.run(
            [sys.executable, str(patch_script)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning("Unstructured patch script failed: %s", result.stderr.strip() or result.stdout.strip())
        else:
            logger.info("Unstructured patch script executed: %s", result.stdout.strip())
    except Exception as exc:
        logger.warning("Unstructured patch script execution error: %s", exc)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/v1/status")
async def get_status():
    report = collect_preflight(_settings, _db)
    report["status_message"] = "Preciso DataForge API running"
    report["runtime"]["python"] = os.getenv("PYTHON_VERSION") or None
    return report
