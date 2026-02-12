from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.core.admin_auth import require_admin
from app.db.supabase_rest_client import create_client as create_supabase_rest_client


router = APIRouter(prefix="/admin/supabase", tags=["Admin - Supabase"])


class SupabaseValidateRequest(BaseModel):
    url: str = Field(..., description="Supabase project URL")
    service_role_key: str = Field(..., description="Supabase service role key")


def _require_admin(
    user: CurrentUser = Depends(get_current_user),
    x_admin_token: Optional[str] = Header(default=None),
) -> CurrentUser:
    return require_admin(user, x_admin_token)


@router.post("/validate")
async def validate_supabase(
    payload: SupabaseValidateRequest,
    _user: CurrentUser = Depends(_require_admin),
):
    required = [
        "cases",
        "documents",
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
        "lakehouse_jobs",
        "lakehouse_table_versions",
        "dataset_mlflow_links",
        "governance_policies",
        "governance_lineage_events",
        "ai_training_sets",
        "partner_accounts",
        "partner_api_keys",
        "integration_secrets",
        "ops_entities",
        "kg_relationships",
    ]
    try:
        client = create_supabase_rest_client(payload.url, payload.service_role_key)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"failed to create client: {exc}")

    missing = []
    for table in required:
        try:
            client.table(table).select("*").limit(1).execute()
        except Exception:
            missing.append(table)

    return {
        "ok": len(missing) == 0,
        "missing_tables": missing,
        "required_tables": required,
    }
