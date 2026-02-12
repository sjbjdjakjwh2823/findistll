from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.db.registry import get_db

router = APIRouter(prefix="/datasets", tags=["WS8 - Datasets"])


class CreateDatasetVersionRequest(BaseModel):
    name: Optional[str] = Field(None, description="Optional name hint for the dataset version")


@router.get("/versions")
def list_versions(limit: int = Query(50, ge=1, le=200)):
    db = get_db()
    return {"versions": db.list_dataset_versions(limit=limit)}


@router.post("/versions")
def create_version(payload: CreateDatasetVersionRequest):
    db = get_db()
    version = db.get_or_create_active_dataset_version(name_hint=payload.name)
    return {"version": version}


@router.post("/versions/{dataset_version_id}/seal")
def seal_version(dataset_version_id: str):
    db = get_db()
    db.seal_dataset_version(dataset_version_id)
    return {"status": "sealed"}


@router.get("/versions/{dataset_version_id}/samples")
def list_samples(dataset_version_id: str, limit: int = Query(200, ge=1, le=1000)):
    db = get_db()
    return {"samples": db.list_spoke_a_samples(dataset_version_id, limit=limit)}


@router.get("/versions/{dataset_version_id}/download")
def download_jsonl(dataset_version_id: str):
    db = get_db()
    samples = db.list_spoke_a_samples(dataset_version_id, limit=20000)
    lines: List[str] = []
    for s in reversed(samples):  # chronological
        if s.get("status") != "candidate":
            continue
        if s.get("jsonl_line"):
            lines.append(str(s["jsonl_line"]).strip())
            continue
        sample_json = s.get("sample_json")
        if sample_json:
            lines.append(json.dumps(sample_json, ensure_ascii=False))
    data = "\n".join([ln for ln in lines if ln])
    return StreamingResponse(
        iter([data.encode("utf-8")]),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="spoke_a_sft_{dataset_version_id}.jsonl"'},
    )

