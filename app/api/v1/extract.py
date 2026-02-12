"""
DataForge Extract API - Phase 1
Alias endpoints for planned /api/v1/extract and /api/v1/export/{job_id}.
"""

import json
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.api.v1.ingest import (
    check_duplicate,
    compute_file_hash,
    get_db,
    get_document_by_id,
    insert_raw_document,
    process_with_polars,
    update_document_status,
    update_document_content,
    _infer_document_type,
    _parse_csv_with_polars,
)
from app.services.task_queue import TaskQueue
from app.services.unified_engine import UnifiedConversionEngine

router = APIRouter(prefix="/extract", tags=["DataForge - Extract"])


@router.post("")
async def extract_document(
    file: UploadFile = File(...),
    source: str = Query("upload", description="Data source label"),
    ticker: Optional[str] = Query(None, description="Stock ticker"),
    document_type: Optional[str] = Query(None, description="Document type"),
    async_process: bool = Query(False, alias="async", description="Queue extraction in background"),
):
    """
    Start extraction job and return job_id.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    content_bytes = await file.read()
    file_hash = compute_file_hash(content_bytes)

    existing_id = check_duplicate(db, file_hash)
    if existing_id:
        return {"job_id": existing_id, "status": "duplicate"}

    filename = file.filename or "unknown"
    content_type = file.content_type or ""

    try:
        if filename.endswith(".json") or "json" in content_type:
            raw_content = json.loads(content_bytes.decode("utf-8"))
        elif filename.endswith(".csv") or "csv" in content_type:
            raw_content = _parse_csv_with_polars(content_bytes)
        else:
            raw_content = {
                "text": content_bytes.decode("utf-8", errors="replace"),
                "filename": filename,
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    processed_content = raw_content
    unified_summary = {}
    if not async_process:
        try:
            engine = UnifiedConversionEngine()
            unified = await engine.convert_document(
                file_bytes=content_bytes,
                filename=filename,
                mime_type=content_type or "application/octet-stream",
                source=source,
                run_snorkel=False,
            )
            processed_content = unified.normalized or raw_content
            unified_summary = {
                "fact_count": len(unified.distill.facts),
                "table_count": len((unified.normalized or {}).get("tables", []) or []),
                "exports": [k for k in unified.exports.keys() if not k.endswith("_error")],
            }
        except Exception:
            processed_content = process_with_polars(raw_content, source)

    doc_data = {
        "source": source,
        "ticker": ticker,
        "document_type": document_type or _infer_document_type(filename),
        "content": processed_content,
        "file_hash": file_hash,
        "file_path": filename,
        "metadata": {
            "original_filename": filename,
            "content_type": content_type,
            "size_bytes": len(content_bytes),
            "unified_summary": unified_summary,
        },
    }

    try:
        doc_id = insert_raw_document(db, doc_data)
        if async_process:
            queue = TaskQueue()
            if not queue.enabled():
                update_document_status(db, doc_id, "failed", "TaskQueue disabled")
                raise HTTPException(status_code=503, detail="Task queue not configured")
            update_document_status(db, doc_id, "queued")
            queue.enqueue_extract(doc_id)
            return {"job_id": doc_id, "status": "queued"}

        update_document_status(db, doc_id, "completed")
        return {"job_id": doc_id, "status": "completed", "unified_summary": unified_summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.get("/export/{job_id}")
async def export_extraction(job_id: str):
    """
    Export extracted content for a job_id.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    doc = get_document_by_id(db, job_id)
    if not doc:
        raise HTTPException(status_code=404, detail="job not found")

    payload = doc.get("raw_content") or {}
    data = json.dumps({"job_id": job_id, "data": payload}, ensure_ascii=False)
    return StreamingResponse(
        iter([data.encode("utf-8")]),
        media_type="application/json",
    )
