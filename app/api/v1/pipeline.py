from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.db.registry import get_db
from app.services.enterprise_collab import TenantPipelineManager
from app.services.task_queue import TaskQueue


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


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str, user: CurrentUser = Depends(get_current_user)):
    """
    Best-effort retry for failed/dead_letter jobs.
    Currently supports: ingest (re-enqueue extract), rag (re-enqueue rag query).
    """
    manager = TenantPipelineManager(get_db())
    row = manager.store.get_pipeline_job(job_id=job_id)
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    if row.get("user_id") != user.user_id and (user.role or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="access denied")

    status = str(row.get("status") or "")
    if status not in {"failed", "dead_letter"}:
        raise HTTPException(status_code=400, detail=f"job not retryable from status={status}")

    job_type = str(row.get("job_type") or "")
    input_ref = row.get("input_ref") or {}
    if not isinstance(input_ref, dict):
        input_ref = {}

    queue = TaskQueue()
    if not queue.enabled():
        raise HTTPException(status_code=503, detail="TaskQueue disabled: set REDIS_URL")

    # Reset job to pending and clear output/error prior to requeue.
    manager.store.update_pipeline_job_status(
        actor_user_id=user.user_id,
        job_id=job_id,
        status="pending",
        output_ref={},
        error=None,
    )

    if job_type == "ingest":
        doc_id = str(input_ref.get("doc_id") or "").strip()
        if not doc_id:
            raise HTTPException(status_code=400, detail="missing input_ref.doc_id for ingest retry")
        queue.enqueue_extract(
            doc_id,
            extra={"job_id": job_id, "owner_user_id": row.get("user_id"), "retry": True},
        )
    elif job_type == "rag":
        query = str(input_ref.get("query") or "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="missing input_ref.query for rag retry")
        top_k = int(input_ref.get("top_k") or 5)
        threshold = float(input_ref.get("threshold") or 0.6)
        metadata_filter = input_ref.get("metadata_filter") or {}
        if not isinstance(metadata_filter, dict):
            metadata_filter = {}
        queue.enqueue_rag_query(
            job_id=job_id,
            tenant_id=str(row.get("tenant_id") or "public"),
            user_id=str(row.get("user_id") or user.user_id),
            role=str(input_ref.get("role") or user.role or "viewer"),
            query=query,
            top_k=top_k,
            threshold=threshold,
            metadata_filter=metadata_filter,
        )
    else:
        raise HTTPException(status_code=400, detail=f"job_type not supported for retry: {job_type}")

    return manager.store.get_pipeline_job(job_id=job_id) or {}
