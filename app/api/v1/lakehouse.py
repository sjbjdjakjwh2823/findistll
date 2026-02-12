from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.db.registry import get_db
from app.services.lakehouse_client import LakehouseClient
from app.services.spark_job_service import SparkJobService


router = APIRouter(prefix="/lakehouse", tags=["Lakehouse"])


class SubmitJobIn(BaseModel):
    job_type: str = Field(description="bronze_ingest|silver_transform|gold_feature|rag_sync")
    priority: str = Field(default="normal")
    payload: Dict[str, Any] = Field(default_factory=dict)


class TimeTravelIn(BaseModel):
    delta_version: Optional[str] = None
    sql: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=2000)


@router.post("/jobs/submit")
def submit_job(payload: SubmitJobIn, user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    job = SparkJobService(db).submit(
        job_type=payload.job_type,
        payload=payload.payload,
        priority=payload.priority,
        requested_by=user.user_id,
    )
    return {"job": job}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    row = SparkJobService(db).get(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job": row}


@router.get("/tables/{layer}/{table}/history")
def table_history(layer: str, table: str, user: CurrentUser = Depends(get_current_user)):
    db = get_db()
    rows = LakehouseClient(db).table_history(layer, table)
    return {"layer": layer, "table": table, "history": rows}


@router.post("/tables/{layer}/{table}/time-travel-query")
def time_travel_query(
    layer: str,
    table: str,
    payload: TimeTravelIn,
    user: CurrentUser = Depends(get_current_user),
):
    db = get_db()
    result = LakehouseClient(db).time_travel_query(
        layer,
        table,
        delta_version=payload.delta_version,
        sql=payload.sql,
        limit=payload.limit,
    )
    return result
