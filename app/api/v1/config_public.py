from __future__ import annotations

import os

from fastapi import APIRouter

from app.core.config import load_settings
from app.services.partner_registry import current_partner_auth_mode
from app.services.secret_store import secret_store_enabled
from app.services.feature_flags import list_flags


router = APIRouter(prefix="/config", tags=["Config"])


@router.get("/public")
async def get_public_config():
    settings = load_settings()
    db_present = bool(settings.supabase_url and settings.supabase_service_role_key)

    return {
        "app_env": settings.app_env,
        "db_backend": settings.db_backend or ("supabase" if db_present else "memory"),
        "tenant_header_required": settings.tenant_header_required == "1",
        "rbac_enforced": os.getenv("RBAC_ENFORCED", "0") == "1",
        "oidc_enabled": os.getenv("OIDC_ENABLED", "0") == "1",
        "partner_auth": {
            "mode": current_partner_auth_mode(db_present=db_present),
            "env_allowlist_configured": bool((os.getenv("PARTNER_API_KEYS") or "").strip()),
            "registry_available": db_present,
            "pepper_configured": bool((os.getenv("PARTNER_API_KEY_PEPPER") or "").strip()),
        },
        "integrations": {
            "finnhub": bool((os.getenv("FINNHUB_API_KEY") or "").strip()),
            "fred": bool((os.getenv("FRED_API_KEY") or "").strip()),
            "fmp": bool((os.getenv("FMP_API_KEY") or "").strip()),
            "gemini": bool((os.getenv("GEMINI_API_KEY") or "").strip()),
            "openai": bool((os.getenv("OPENAI_API_KEY") or "").strip()),
        },
        "training": {
            "auto_on_approval": os.getenv("AUTO_TRAIN_ON_APPROVAL", "0") == "1",
            "provider": os.getenv("TRAINING_PROVIDER", "none"),
            "local_command_configured": bool((os.getenv("LOCAL_TRAINING_COMMAND") or "").strip()),
        },
        "external_keys": {
            "secret_store_enabled": secret_store_enabled(),
        },
        "lakehouse": {
            "enabled": settings.lakehouse_enabled == "1",
            "delta_root_uri": settings.delta_root_uri,
            "spark_api_configured": bool((settings.spark_api_url or "").strip()),
            "airflow_api_configured": bool((settings.airflow_api_url or "").strip()),
            "mlflow_configured": bool((settings.mlflow_tracking_uri or "").strip()),
            "unity_catalog_configured": bool((settings.unity_catalog_api_url or "").strip()),
        },
        "feature_flags": list_flags(),
        "endpoints": {
            "partner_ingest": "/api/v1/partners/financials",
            "partner_docs": "/api/v1/partners/documents",
            "partner_admin": "/api/v1/admin/partners",
            "integrations_admin": "/api/v1/admin/integrations",
            "market": "/api/v1/market",
            "dataforge": "/api/v1/ingest",
            "collab": "/api/v1/collab",
            "collab_files": "/api/v1/collab/files",
            "pipeline": "/api/v1/pipeline",
            "rag_query": "/api/v1/rag/query",
            "console": "/api/v1/console",
            "policy_check": "/api/v1/policy/check",
            "lakehouse": "/api/v1/lakehouse",
            "mlflow": "/api/v1/mlflow",
            "governance": "/api/v1/governance",
        },
    }
