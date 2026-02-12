from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.db.registry import get_db
from app.services.enterprise_collab import TenantPipelineManager


router = APIRouter(prefix="/pipeline", tags=["Tenant Pipeline"])


class PipelineSubmitIn(BaseModel):
    job_type: str = Field(description="ingest|rag|approval|train|export|batch")
    flow: str = Field(default="interactive", description="interactive|approval|ingest|batch")
    input_ref: Optional[Dict[str, Any]] = None


@router.post("/jobs/submit")
def submit_job(payload: PipelineSubmitIn, user: CurrentUser = Depends(get_current_user)):
    manager = TenantPipelineManager(get_db())
    try:
        return manager.submit(
            user_id=user.user_id,
            job_type=payload.job_type,
            flow=payload.flow,
            input_ref=payload.input_ref or {},
        )
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: CurrentUser = Depends(get_current_user)):
    manager = TenantPipelineManager(get_db())
    row = manager.store.get_pipeline_job(job_id=job_id)
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    if row.get("user_id") != user.user_id and (user.role or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="access denied")
    return row


@router.get("/tenant-status")
def tenant_status(user: CurrentUser = Depends(get_current_user)):
    manager = TenantPipelineManager(get_db())
    try:
        return manager.status(user_id=user.user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
