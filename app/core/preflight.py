from __future__ import annotations

import os
import logging
from typing import Any, Dict, List

from app.core.config import Settings
from app.db.supabase_db import SupabaseDB
from app.services.lakehouse_client import LakehouseClient

logger = logging.getLogger(__name__)


def _has(module: str) -> bool:
    try:
        __import__(module)
        return True
    except Exception:
        return False


def _check_required(value: str) -> bool:
    return bool(value and value.strip())


def collect_preflight(settings: Settings, db: Any) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add_check(key: str, ok: bool, severity: str, message: str, fix: str) -> None:
        checks.append(
            {
                "key": key,
                "ok": bool(ok),
                "severity": severity,
                "message": message,
                "fix": fix,
            }
        )

    is_prod = settings.app_env.lower() == "prod"
    db_backend = (settings.db_backend or "").strip().lower() or "supabase"

    add_check(
        "rbac_enforced",
        settings.rbac_enforced == "1" if is_prod else True,
        "blocker" if is_prod else "warn",
        "RBAC must be enforced in production" if is_prod else "RBAC is recommended for enterprise use",
        "Set RBAC_ENFORCED=1 in production.",
    )
    add_check(
        "tenant_header_required",
        settings.tenant_header_required == "1" if is_prod else True,
        "blocker" if is_prod else "warn",
        "Tenant header must be required in production" if is_prod else "Tenant header enforcement is recommended",
        "Set TENANT_HEADER_REQUIRED=1 in production.",
    )
    add_check(
        "public_domain",
        _check_required(settings.public_domain),
        "blocker" if is_prod else "warn",
        "PUBLIC_DOMAIN is required for enterprise deployments" if is_prod else "PUBLIC_DOMAIN is recommended",
        "Set PUBLIC_DOMAIN to your external domain.",
    )
    add_check(
        "redis_url",
        _check_required(settings.redis_url) if is_prod else True,
        "blocker" if is_prod else "warn",
        "REDIS_URL is required for worker/rate-limit in production" if is_prod else "REDIS_URL is recommended",
        "Set REDIS_URL=redis://host:6379",
    )
    add_check(
        "admin_auth",
        _check_required(settings.admin_api_token) or settings.rbac_enforced == "1" or not is_prod,
        "blocker" if is_prod else "warn",
        "Admin endpoints must be protected in production",
        "Set ADMIN_API_TOKEN or enable RBAC for admin roles.",
    )
    add_check(
        "db_backend",
        db_backend in {"supabase", "postgres", "memory"},
        "blocker" if is_prod else "warn",
        f"DB_BACKEND must be one of supabase/postgres/memory (current: {db_backend})",
        "Set DB_BACKEND=supabase or DB_BACKEND=postgres.",
    )

    if db_backend == "supabase":
        add_check(
            "supabase_url",
            _check_required(settings.supabase_url),
            "blocker" if is_prod else "warn",
            "SUPABASE_URL is required for supabase backend",
            "Set SUPABASE_URL to your Supabase instance.",
        )
        add_check(
            "supabase_service_role_key",
            _check_required(settings.supabase_service_role_key),
            "blocker" if is_prod else "warn",
            "SUPABASE_SERVICE_ROLE_KEY is required for supabase backend",
            "Set SUPABASE_SERVICE_ROLE_KEY in server env.",
        )
    if db_backend == "postgres":
        add_check(
            "database_url",
            _check_required(settings.database_url),
            "blocker" if is_prod else "warn",
            "DATABASE_URL is required for postgres backend",
            "Set DATABASE_URL=postgresql://user:pass@host:5432/db",
        )
        add_check(
            "psycopg2_driver",
            _has("psycopg2"),
            "blocker" if is_prod else "warn",
            "psycopg2 driver is required for postgres backend",
            "Install psycopg2-binary.",
        )

    pdf_deps = {
        "pypdf": _has("pypdf"),
        "pdfplumber": _has("pdfplumber"),
        "pypdfium2": _has("pypdfium2"),
        "pdf2image": _has("pdf2image"),
    }
    add_check(
        "pdf_deps",
        any(pdf_deps.values()),
        "warn",
        "PDF extraction dependencies are missing",
        "Install at least one PDF parser (pypdf/pdfplumber/pypdfium2).",
    )

    # Render dependency check: pdf2image requires poppler (pdftoppm). If pypdfium2 is present we can render without poppler.
    try:
        import shutil

        pdftoppm = shutil.which("pdftoppm")
        ok_render = bool(pdf_deps.get("pypdfium2") or pdftoppm)
        add_check(
            "pdf_renderer",
            ok_render,
            "warn",
            "PDF rendering backend may be missing (OCR/table recovery can fail on scanned PDFs)",
            "Install pypdfium2 (preferred) or install poppler (pdftoppm) for pdf2image.",
        )
    except Exception:
        logger.warning("pdf renderer preflight failed", exc_info=True)

    vision_configured = bool(os.getenv("GOOGLE_VISION_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    add_check(
        "vision_api",
        vision_configured or not is_prod,
        "warn",
        "Vision API key missing (OCR will fall back to local parsers)",
        "Set GOOGLE_VISION_API_KEY if you want cloud OCR.",
    )

    lakehouse_enabled = (settings.lakehouse_enabled or "0") == "1"
    if lakehouse_enabled:
        add_check(
            "delta_root_uri",
            _check_required(settings.delta_root_uri),
            "blocker" if is_prod else "warn",
            "DELTA_ROOT_URI is required when LAKEHOUSE_ENABLED=1",
            "Set DELTA_ROOT_URI (for example s3a://preciso-lakehouse).",
        )
        add_check(
            "spark_or_airflow_configured",
            _check_required(settings.spark_api_url) or _check_required(settings.airflow_api_url),
            "warn",
            "Spark/Airflow endpoint not configured; lakehouse jobs will run in local-stub mode",
            "Set SPARK_API_URL or AIRFLOW_API_URL.",
        )
        add_check(
            "mlflow_tracking_uri",
            _check_required(settings.mlflow_tracking_uri),
            "warn",
            "MLFLOW_TRACKING_URI is not configured; MLflow API will use stub mode",
            "Set MLFLOW_TRACKING_URI.",
        )
        add_check(
            "unity_catalog_api_url",
            _check_required(settings.unity_catalog_api_url),
            "warn",
            "UNITY_CATALOG_API_URL is not configured; governance API will use DB-only mode",
            "Set UNITY_CATALOG_API_URL.",
        )

    missing_tables: List[str] = []
    if isinstance(db, SupabaseDB):
        required = [
            "cases",
            "documents",
            "raw_documents",
            "spoke_c_rag_context",
            "spoke_d_graph",
            "case_embeddings",
            "audit_logs",
            "audit_events",
            "dataset_versions",
            "spoke_a_samples",
            "spoke_b_artifacts",
            "model_registry",
            "llm_runs",
            "rag_runs",
            "rag_run_chunks",
            "ai_training_sets",
            "partner_accounts",
            "partner_api_keys",
            "integration_secrets",
            "ops_entities",
            "ops_relationships",
            "ops_cases",
            "kg_relationships",
        ]
        if lakehouse_enabled:
            required.extend(
                [
                    "lakehouse_jobs",
                    "lakehouse_table_versions",
                    "dataset_mlflow_links",
                    "governance_policies",
                    "governance_lineage_events",
                ]
            )
        for table in required:
            try:
                db.client.table(table).select("*").limit(1).execute()
            except Exception:
                missing_tables.append(table)
        add_check(
            "supabase_tables",
            len(missing_tables) == 0,
            "blocker" if is_prod else "warn",
            "Required tables missing in supabase",
            "Apply supabase_bootstrap_preciso.sql and related SQL files.",
        )

        # OpsGraph autofill requires ops_* + kg_* in order to make 3-hop reasoning meaningful.
        if (settings.opsgraph_autofill_enabled or "0") == "1":
            add_check(
                "opsgraph_autofill_tables",
                all(t not in missing_tables for t in ["ops_entities", "ops_relationships", "ops_cases", "kg_relationships"]),
                "blocker" if is_prod else "warn",
                "OpsGraph autofill is enabled but required ops/kg tables are missing",
                "Apply supabase_bootstrap_preciso.sql (ops graph + kg tables) and supabase_phase8_multitenant.sql.",
            )

    blockers = [c for c in checks if c["severity"] == "blocker" and not c["ok"]]
    warnings = [c for c in checks if c["severity"] == "warn" and not c["ok"]]

    return {
        "status": "ok" if not blockers else "blockers",
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "runtime": {
            "app_env": settings.app_env,
            "db_backend": db_backend,
            "vision_configured": vision_configured,
            "pdf_deps": pdf_deps,
            "missing_tables": missing_tables,
            "lakehouse": LakehouseClient(db).health() if lakehouse_enabled else {"enabled": False},
        },
    }
