import logging
import hashlib
import json
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

class IngestDocumentRequest(BaseModel):
    source: str
    document_type: str
    content: dict # Using dict for content as it's JSONB in schema
    metadata: dict | None = None

class IngestDocumentResponse(BaseModel):
    document_id: str
    status: str
    file_hash: str | None = None
    duplicate: bool = False

@router.post("/ingest", response_model=IngestDocumentResponse)
async def ingest_document(request: IngestDocumentRequest):
    logger.info("Ingesting from %s: %s", request.source, request.document_type)
    try:
        from app.api.v1.ingest import get_db, insert_raw_document, check_duplicate
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ingest_dependencies_unavailable: {exc}")

    try:
        db = get_db()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"db_unavailable: {exc}")

    content_bytes = json.dumps(request.content, ensure_ascii=False, sort_keys=True).encode("utf-8")
    file_hash = hashlib.sha256(content_bytes).hexdigest()
    existing = check_duplicate(db, file_hash)
    if existing:
        return {
            "document_id": existing,
            "status": "duplicate",
            "file_hash": file_hash,
            "duplicate": True,
        }

    doc_id = insert_raw_document(
        db,
        {
            "source": request.source,
            "document_type": request.document_type,
            "content": request.content,
            "metadata": request.metadata or {},
            "file_hash": file_hash,
        },
    )

    return {"document_id": doc_id, "status": "received", "file_hash": file_hash, "duplicate": False}
