"""
DataForge Ingest API - Phase 1
File upload and Polars-based data processing pipeline.
"""

import hashlib
import os
import io
import json
import logging
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Header
from pydantic import BaseModel, Field
from app.core.tenant_context import get_effective_tenant_id
from app.core.auth import CurrentUser, get_current_user
from app.services.quality_monitor import record_quality_gate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["DataForge - Ingest"])


# =============================================================================
# Models
# =============================================================================

class IngestRequest(BaseModel):
    """Request model for programmatic ingestion."""
    source: str = Field(..., description="Data source: 'sec_10k', 'sec_8k', 'fred', 'finnhub', 'fmp', 'upload'")
    ticker: Optional[str] = Field(None, description="Stock ticker if applicable")
    document_type: Optional[str] = Field(None, description="Document type")
    document_date: Optional[str] = Field(None, description="Document date (YYYY-MM-DD)")
    content: Dict[str, Any] = Field(..., description="Raw content as JSON")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    """Response model for ingestion."""
    document_id: str
    status: str
    message: str
    file_hash: Optional[str] = None
    job_id: Optional[str] = None


class DocumentListResponse(BaseModel):
    """Response model for document listing."""
    documents: List[Dict[str, Any]]
    total: int
    offset: int
    limit: int


class DocumentStatsResponse(BaseModel):
    """Response model for document statistics."""
    total_documents: int
    by_source: Dict[str, int]
    by_status: Dict[str, int]
    by_type: Dict[str, int]


# =============================================================================
# Polars Processing Functions
# =============================================================================

def process_with_polars(content: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    Process raw content using Polars for high-performance data operations.
    """
    try:
        import polars as pl
    except ImportError:
        logger.warning("Polars not installed, using fallback processing")
        return content
    
    processed = content.copy()
    
    # Source-specific processing
    if source == "fred":
        processed = _process_fred_data(content)
    elif source in ("sec_10k", "sec_8k"):
        processed = _process_sec_data(content)
    elif source == "finnhub":
        processed = _process_finnhub_data(content)
    elif source == "fmp":
        processed = _process_fmp_data(content)
    
    return processed


def _process_fred_data(content: Dict[str, Any]) -> Dict[str, Any]:
    """Process FRED macroeconomic data with Polars."""
    try:
        import polars as pl
        
        observations = content.get("observations", [])
        if not observations:
            return content
        
        # Convert to Polars DataFrame
        df = pl.DataFrame(observations)
        
        # Clean and transform
        if "value" in df.columns:
            df = df.with_columns([
                pl.col("value").cast(pl.Float64, strict=False).alias("value_numeric"),
                pl.col("date").str.to_datetime("%Y-%m-%d", strict=False).alias("date_parsed")
            ])
            
            # Calculate statistics
            stats = {
                "mean": df["value_numeric"].mean(),
                "std": df["value_numeric"].std(),
                "min": df["value_numeric"].min(),
                "max": df["value_numeric"].max(),
                "count": len(df),
                "latest_date": str(df["date"].max()) if "date" in df.columns else None,
                "latest_value": df["value_numeric"].tail(1).to_list()[0] if len(df) > 0 else None
            }
            
            content["_polars_stats"] = stats
            content["_polars_processed"] = True
        
        return content
        
    except Exception as e:
        logger.warning(f"FRED Polars processing failed: {e}")
        return content


def _process_sec_data(content: Dict[str, Any]) -> Dict[str, Any]:
    """Process SEC filing data with Polars."""
    try:
        import polars as pl
        
        # Extract financial facts if present
        facts = content.get("facts", {}).get("us-gaap", {})
        if not facts:
            return content
        
        # Collect all metrics
        metrics_data = []
        for concept, data in facts.items():
            units = data.get("units", {})
            for unit_type, values in units.items():
                for entry in values:
                    metrics_data.append({
                        "concept": concept,
                        "unit": unit_type,
                        "value": entry.get("val"),
                        "period_end": entry.get("end"),
                        "period_start": entry.get("start"),
                        "form": entry.get("form"),
                        "fiscal_year": entry.get("fy"),
                        "fiscal_period": entry.get("fp")
                    })
        
        if metrics_data:
            df = pl.DataFrame(metrics_data)
            
            # Group and summarize
            summary = df.group_by("concept").agg([
                pl.col("value").last().alias("latest_value"),
                pl.col("period_end").max().alias("latest_period"),
                pl.count().alias("observation_count")
            ])
            
            content["_polars_metrics_summary"] = summary.to_dicts()
            content["_polars_processed"] = True
            content["_polars_total_metrics"] = len(metrics_data)
        
        return content
        
    except Exception as e:
        logger.warning(f"SEC Polars processing failed: {e}")
        return content


def _process_finnhub_data(content: Dict[str, Any]) -> Dict[str, Any]:
    """Process Finnhub market data with Polars."""
    try:
        import polars as pl
        
        # Handle quote data
        if "c" in content and "t" in content:  # Candle data
            df = pl.DataFrame({
                "close": content.get("c", []),
                "high": content.get("h", []),
                "low": content.get("l", []),
                "open": content.get("o", []),
                "volume": content.get("v", []),
                "timestamp": content.get("t", [])
            })
            
            if len(df) > 0:
                content["_polars_stats"] = {
                    "avg_close": df["close"].mean(),
                    "avg_volume": df["volume"].mean(),
                    "price_range": df["high"].max() - df["low"].min(),
                    "data_points": len(df)
                }
                content["_polars_processed"] = True
        
        return content
        
    except Exception as e:
        logger.warning(f"Finnhub Polars processing failed: {e}")
        return content


def _process_fmp_data(content: Dict[str, Any]) -> Dict[str, Any]:
    """Process FMP financial data with Polars."""
    try:
        import polars as pl
        
        # Handle income statement or balance sheet arrays
        if isinstance(content, list) and len(content) > 0:
            df = pl.DataFrame(content)
            content = {
                "data": content,
                "_polars_columns": df.columns,
                "_polars_row_count": len(df),
                "_polars_processed": True
            }
        
        return content
        
    except Exception as e:
        logger.warning(f"FMP Polars processing failed: {e}")
        return content


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash for deduplication."""
    tenant_id = get_effective_tenant_id()
    return hashlib.sha256(tenant_id.encode("utf-8") + b":" + content).hexdigest()


# =============================================================================
# Database Functions
# =============================================================================

def get_db():
    """Get database client."""
    # Use the global DB instance initialized in app.main via app.db.registry.
    # This keeps API/worker behavior consistent across Supabase and InMemory modes.
    from app.db.registry import get_db as _get_db
    return _get_db()


def insert_raw_document(db, doc_data: Dict[str, Any]) -> str:
    """Insert a raw document into the database."""
    doc_id = str(uuid4())
    owner_user_id = None
    try:
        owner_user_id = (doc_data.get("metadata") or {}).get("owner_user_id")
    except Exception:
        owner_user_id = None
    
    payload = {
        "id": doc_id,
        # Keep a stable text id for compatibility with downstream tooling/SQL that expects raw_documents.doc_id.
        # In Preciso, the UUID primary key is still the source of truth.
        "doc_id": doc_id,
        "source": doc_data["source"],
        "ticker": doc_data.get("ticker"),
        "document_type": doc_data.get("document_type"),
        "document_date": doc_data.get("document_date"),
        "raw_content": doc_data["content"],
        "file_hash": doc_data.get("file_hash"),
        "file_path": doc_data.get("file_path"),
        "processing_status": "pending",
        "metadata": {
            **(doc_data.get("metadata", {}) or {}),
            # Make doc_id/owner_user_id available as evidence metadata for safe filtering across stores.
            "doc_id": doc_id,
            "owner_user_id": owner_user_id,
            "tenant_id": get_effective_tenant_id(),
        }
    }

    if hasattr(db, "client"):
        db.client.table("raw_documents").insert(payload).execute()
        if os.getenv("RAG_INGEST_ASYNC", "0") == "1":
            try:
                from app.services.task_queue import TaskQueue
                queue = TaskQueue()
                if queue.enabled():
                    queue.enqueue_embed(doc_id)
            except Exception as exc:
                logger.warning("RAG async enqueue failed", exc_info=exc)
        return doc_id

    # InMemory fallback (dev/test mode)
    raw_docs = getattr(db, "raw_documents", None)
    if raw_docs is None:
        raw_docs = {}
        setattr(db, "raw_documents", raw_docs)
    raw_docs[doc_id] = payload
    if os.getenv("RAG_INGEST_ASYNC", "0") == "1":
        try:
            from app.services.task_queue import TaskQueue
            queue = TaskQueue()
            if queue.enabled():
                queue.enqueue_embed(doc_id)
        except Exception as exc:
            logger.warning("RAG async enqueue failed (in-memory)", exc_info=exc)
    return doc_id


def _auto_register_collab_file(db: Any, *, owner_user_id: Optional[str], doc_id: str) -> None:
    """
    Ensure an uploaded document becomes visible to its owner via Collaboration layer.
    This is required for role/ACL based RAG scoping.
    Best-effort: never blocks ingestion.
    """
    if not owner_user_id or owner_user_id == "anonymous":
        return
    try:
        from app.services.enterprise_collab import EnterpriseCollabStore

        store = EnterpriseCollabStore(db)
        space = store.ensure_personal_space(user_id=owner_user_id)
        space_id = str(space.get("id") or "")
        if not space_id:
            return
        store.register_file(actor_user_id=owner_user_id, space_id=space_id, doc_id=doc_id, visibility="private")
    except Exception:
        return


def get_documents(
    db,
    source: Optional[str] = None,
    ticker: Optional[str] = None,
    status: Optional[str] = None,
    offset: int = 0,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Query documents with filters."""
    if not hasattr(db, "client"):
        raw_docs = getattr(db, "raw_documents", {}) or {}
        items = list(raw_docs.values())
        if source:
            items = [d for d in items if d.get("source") == source]
        if ticker:
            items = [d for d in items if d.get("ticker") == ticker]
        if status:
            items = [d for d in items if d.get("processing_status") == status]
        items.sort(key=lambda d: d.get("ingested_at") or "", reverse=True)
        return items[offset : offset + limit]

    query = db.client.table("raw_documents").select("*")
    
    if source:
        query = query.eq("source", source)
    if ticker:
        query = query.eq("ticker", ticker)
    if status:
        query = query.eq("processing_status", status)
    
    query = query.order("ingested_at", desc=True)
    query = query.range(offset, offset + limit - 1)
    
    result = query.execute()
    return result.data or []


def get_document_by_id(db, doc_id: str) -> Optional[Dict[str, Any]]:
    """Get a single document by ID."""
    if not hasattr(db, "client"):
        raw_docs = getattr(db, "raw_documents", {}) or {}
        return raw_docs.get(doc_id)

    result = db.client.table("raw_documents").select("*").eq("id", doc_id).execute()
    return result.data[0] if result.data else None


def update_document_status(db, doc_id: str, status: str, error: Optional[str] = None):
    """Update document processing status."""
    payload = {"processing_status": status}
    if error:
        payload["processing_error"] = error
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    if hasattr(db, "client"):
        db.client.table("raw_documents").update(payload).eq("id", doc_id).execute()
        return

    raw_docs = getattr(db, "raw_documents", {}) or {}
    if doc_id in raw_docs:
        raw_docs[doc_id].update(payload)


def update_document_content(db, doc_id: str, content: Dict[str, Any]):
    """Update document content after background processing."""
    if hasattr(db, "client"):
        db.client.table("raw_documents").update({
            "raw_content": content,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", doc_id).execute()
        return

    raw_docs = getattr(db, "raw_documents", {}) or {}
    if doc_id in raw_docs:
        raw_docs[doc_id]["raw_content"] = content


def update_document_metadata(db, doc_id: str, metadata: Dict[str, Any]):
    """Update document metadata."""
    if hasattr(db, "client"):
        db.client.table("raw_documents").update({
            "metadata": metadata,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", doc_id).execute()
        return

    raw_docs = getattr(db, "raw_documents", {}) or {}
    if doc_id in raw_docs:
        raw_docs[doc_id]["metadata"] = metadata


def _maybe_record_quality_gate(db, doc_id: str, metadata: Dict[str, Any], content: Dict[str, Any]):
    try:
        distill_meta = content.get("metadata") if isinstance(content, dict) else {}
        metrics = content.get("metrics") if isinstance(content, dict) else {}
        merged_meta = {**(metadata or {}), **(distill_meta or {})}
        if "tenant_id" not in merged_meta:
            merged_meta["tenant_id"] = get_effective_tenant_id()
        record_quality_gate(
            db=db,
            doc_id=str(doc_id),
            metadata=merged_meta,
            metrics=metrics,
            source=str(metadata.get("source") or "upload"),
        )
    except Exception as exc:
        logger.warning("swallowed exception", exc_info=exc)


def _extract_plain_text(content: Any) -> str:
    """Build a searchable plain text from structured document payloads."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"]
        # Keep it deterministic for hashing/debugging.
        return json.dumps(content, ensure_ascii=False, sort_keys=True)
    if isinstance(content, list):
        return json.dumps(content, ensure_ascii=False)
    return str(content)


def _top_keywords(text: str, limit: int = 20) -> List[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_\\-]{2,}", (text or "").lower())
    stop = {
        "the", "and", "for", "with", "from", "that", "this", "have", "has", "were",
        "was", "are", "but", "not", "you", "your", "they", "their", "about", "into",
        "after", "before", "over", "under", "when", "where", "what", "which",
    }
    counts: Dict[str, int] = {}
    for t in tokens:
        if t in stop:
            continue
        counts[t] = counts.get(t, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return [k for k, _ in ranked[:limit]]


def _build_rag_seed_contexts(
    *,
    doc_id: str,
    source: str,
    text_content: str,
    metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Seed Spoke-C context at ingest time for immediate RAG usability."""
    text = (text_content or "").strip()
    if not text:
        return []
    try:
        chunk_size = int(os.getenv("RAG_SEED_CHUNK_SIZE", "1400"))
    except ValueError:
        chunk_size = 1400
    try:
        overlap = int(os.getenv("RAG_SEED_CHUNK_OVERLAP", "200"))
    except ValueError:
        overlap = 200
    chunk_size = max(300, min(chunk_size, 4000))
    overlap = max(0, min(overlap, max(0, chunk_size - 50)))
    chunks: List[Dict[str, Any]] = []
    idx = 0
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        snippet = text[start:end].strip()
        if snippet:
            chunk_id = f"{doc_id}:seed:{idx}"
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "entity": metadata.get("ticker") or metadata.get("entity") or "unknown",
                    "period": metadata.get("document_date") or metadata.get("period"),
                    "source": source,
                    "text_content": snippet,
                    "keywords": _top_keywords(snippet, limit=16),
                    "metadata": {**metadata, "doc_id": doc_id, "seeded_at_ingest": True, "chunk_index": idx},
                }
            )
            idx += 1
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _seed_rag_context(db: Any, doc_id: str, source: str, content: Any, metadata: Dict[str, Any]) -> int:
    try:
        text = _extract_plain_text(content)
        contexts = _build_rag_seed_contexts(
            doc_id=str(doc_id),
            source=str(source or "upload"),
            text_content=text,
            metadata=metadata or {},
        )
        if not contexts:
            return 0
        db.save_rag_context(str(doc_id), contexts)
        return len(contexts)
    except Exception as exc:
        logger.warning("RAG seed context generation failed", exc_info=exc)
        return 0


def check_duplicate(db, file_hash: str) -> Optional[str]:
    """Check if document with same hash already exists."""
    if not hasattr(db, "client"):
        raw_docs = getattr(db, "raw_documents", {}) or {}
        for doc_id, item in raw_docs.items():
            if item.get("file_hash") == file_hash:
                return doc_id
        return None

    result = db.client.table("raw_documents").select("id").eq("file_hash", file_hash).execute()
    return result.data[0]["id"] if result.data else None


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/document", response_model=IngestResponse)
async def ingest_document(
    request: IngestRequest,
    x_preciso_user_id: Optional[str] = Header(default=None, alias="X-Preciso-User-Id"),
):
    """
    Ingest a document from a data source.
    
    This endpoint accepts JSON content and processes it through the Polars pipeline.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # Compute hash for deduplication
    content_bytes = json.dumps(request.content, sort_keys=True).encode()
    file_hash = compute_file_hash(content_bytes)
    
    # Check for duplicates
    existing_id = check_duplicate(db, file_hash)
    if existing_id:
        return IngestResponse(
            document_id=existing_id,
            status="duplicate",
            message="Document already exists",
            file_hash=file_hash
        )
    
    # Process with Polars
    processed_content = process_with_polars(request.content, request.source)
    
    # Insert into database
    doc_data = {
        "source": request.source,
        "ticker": request.ticker,
        "document_type": request.document_type,
        "document_date": request.document_date,
        "content": processed_content,
        "file_hash": file_hash,
        "metadata": {
            **(request.metadata or {}),
            "tenant_id": get_effective_tenant_id(),
            "owner_user_id": x_preciso_user_id,
        },
    }
    
    try:
        doc_id = insert_raw_document(db, doc_data)
        update_document_status(db, doc_id, "completed")
        _auto_register_collab_file(db, owner_user_id=x_preciso_user_id, doc_id=doc_id)
        _seed_rag_context(
            db=db,
            doc_id=doc_id,
            source=request.source,
            content=processed_content,
            metadata={
                **(doc_data.get("metadata") or {}),
                "ticker": request.ticker,
                "document_date": request.document_date,
            },
        )
        _maybe_record_quality_gate(db, doc_id, doc_data.get("metadata") or {}, processed_content)

        return IngestResponse(
            document_id=doc_id,
            status="success",
            message="Document ingested successfully",
            file_hash=file_hash
        )
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.post("/upload", response_model=IngestResponse)
async def upload_file(
    file: UploadFile = File(...),
    source: str = Query("upload", description="Data source label"),
    ticker: Optional[str] = Query(None, description="Stock ticker"),
    document_type: Optional[str] = Query(None, description="Document type"),
    x_preciso_user_id: Optional[str] = Header(default=None, alias="X-Preciso-User-Id"),
):
    """
    Upload a file for ingestion.
    
    Supports JSON, CSV, and text files. Files are processed through Polars.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # Read file content
    content_bytes = await file.read()
    validation = _validate_upload(content_bytes, file.filename or "unknown")
    file_hash = compute_file_hash(content_bytes)
    
    # Check for duplicates
    existing_id = check_duplicate(db, file_hash)
    if existing_id:
        return IngestResponse(
            document_id=existing_id,
            status="duplicate",
            message="File already uploaded",
            file_hash=file_hash
        )
    
    # Parse file content
    filename = file.filename or "unknown"
    content_type = file.content_type or ""
    
    try:
        if filename.endswith(".json") or "json" in content_type:
            raw_content = json.loads(content_bytes.decode("utf-8"))
        elif filename.endswith(".csv") or "csv" in content_type:
            raw_content = _parse_csv_with_polars(content_bytes)
        else:
            # Treat as text
            raw_content = {
                "text": content_bytes.decode("utf-8", errors="replace"),
                "filename": filename
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")
    
    # Process with Polars
    processed_content = process_with_polars(raw_content, source)
    
    # Insert into database
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
            "size_bytes": validation.get("size_bytes"),
            "detected_mime": validation.get("detected_mime"),
            "tenant_id": get_effective_tenant_id(),
            "owner_user_id": x_preciso_user_id,
        },
    }
    
    try:
        doc_id = insert_raw_document(db, doc_data)
        update_document_status(db, doc_id, "completed")
        _auto_register_collab_file(db, owner_user_id=x_preciso_user_id, doc_id=doc_id)
        _seed_rag_context(
            db=db,
            doc_id=doc_id,
            source=source,
            content=processed_content,
            metadata={
                **(doc_data.get("metadata") or {}),
                "ticker": ticker,
                "document_type": doc_data.get("document_type"),
            },
        )
        _maybe_record_quality_gate(db, doc_id, doc_data.get("metadata") or {}, processed_content)

        return IngestResponse(
            document_id=doc_id,
            status="success",
            message=f"File '{filename}' uploaded successfully",
            file_hash=file_hash
        )
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload-async", response_model=IngestResponse)
async def upload_file_async(
    file: UploadFile = File(...),
    source: str = Query("upload", description="Data source label"),
    ticker: Optional[str] = Query(None, description="Stock ticker"),
    document_type: Optional[str] = Query(None, description="Document type"),
    x_preciso_user_id: Optional[str] = Header(default=None, alias="X-Preciso-User-Id"),
):
    """
    Upload a file for async ingestion.

    This enqueues the document for background processing (worker).
    Use this for large datasets to avoid UI bottlenecks.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    content_bytes = await file.read()
    validation = _validate_upload(content_bytes, file.filename or "unknown")
    file_hash = compute_file_hash(content_bytes)

    existing_id = check_duplicate(db, file_hash)
    if existing_id:
        return IngestResponse(
            document_id=existing_id,
            status="duplicate",
            message="File already uploaded",
            file_hash=file_hash
        )

    filename = file.filename or "unknown"
    upload_dir = Path(__file__).resolve().parents[3] / "artifacts" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    temp_doc_id = str(uuid4())
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", filename)
    stored_path = upload_dir / f"{temp_doc_id}_{safe_name}"
    stored_path.write_bytes(content_bytes)

    idempotency_key = f"{get_effective_tenant_id()}:{file_hash}"
    doc_data = {
        "source": source,
        "ticker": ticker,
        "document_type": document_type or _infer_document_type(filename),
        "content": {
            "file_path": str(stored_path),
            "filename": filename,
        },
        "file_hash": file_hash,
        "file_path": str(stored_path),
        "metadata": {
            "original_filename": filename,
            "content_type": file.content_type or "",
            "size_bytes": validation.get("size_bytes"),
            "detected_mime": validation.get("detected_mime"),
            "tenant_id": get_effective_tenant_id(),
            "queued_via": "upload_async",
            "idempotency_key": idempotency_key,
            "owner_user_id": x_preciso_user_id,
        },
    }

    doc_id = insert_raw_document(db, doc_data)
    update_document_status(db, doc_id, "queued")
    _auto_register_collab_file(db, owner_user_id=x_preciso_user_id, doc_id=doc_id)

    pipeline_job_id: Optional[str] = None
    if x_preciso_user_id and x_preciso_user_id != "anonymous":
        # Best-effort: track async ingest as a tenant pipeline job for UX + observability.
        try:
            from app.services.enterprise_collab import TenantPipelineManager

            manager = TenantPipelineManager(db)
            job = manager.submit(
                user_id=x_preciso_user_id,
                job_type="ingest",
                flow="ingest",
                input_ref={"doc_id": doc_id, "file_hash": file_hash, "source": source, "filename": filename},
            )
            pipeline_job_id = str(job.get("id") or "")
            if pipeline_job_id:
                doc_row = get_document_by_id(db, doc_id) or {}
                meta = (doc_row.get("metadata") or {}) if isinstance(doc_row, dict) else {}
                meta["pipeline_job_id"] = pipeline_job_id
                update_document_metadata(db, doc_id, meta)
        except Exception:
            pipeline_job_id = None

    try:
        from app.services.task_queue import TaskQueue
        queue = TaskQueue()
        if not queue.enabled():
            update_document_status(db, doc_id, "failed", "TaskQueue disabled")
            raise HTTPException(status_code=400, detail="TaskQueue disabled: set REDIS_URL to enable async processing")
        max_depth = int(os.getenv("DATAFORGE_MAX_QUEUE_DEPTH", "500"))
        if queue.length() >= max_depth:
            update_document_status(db, doc_id, "failed", "Queue overload")
            raise HTTPException(status_code=429, detail="Queue overloaded, try again later")
        queue.enqueue_extract(
            doc_id,
            extra={
                "job_id": pipeline_job_id,
                "owner_user_id": x_preciso_user_id,
                "idempotency_key": idempotency_key,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        update_document_status(db, doc_id, "failed", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to enqueue: {str(e)}")

    return IngestResponse(
        document_id=doc_id,
        status="queued",
        message=f"File '{filename}' queued successfully",
        file_hash=file_hash,
        job_id=pipeline_job_id,
    )


def _parse_csv_with_polars(content_bytes: bytes) -> Dict[str, Any]:
    """Parse CSV file using Polars."""
    try:
        import polars as pl
        
        df = pl.read_csv(io.BytesIO(content_bytes))
        return {
            "columns": df.columns,
            "row_count": len(df),
            "data": df.to_dicts(),
            "_polars_schema": {col: str(dtype) for col, dtype in df.schema.items()}
        }
    except ImportError:
        # Fallback to csv module
        import csv
        reader = csv.DictReader(io.StringIO(content_bytes.decode("utf-8")))
        rows = list(reader)
        return {
            "columns": reader.fieldnames,
            "row_count": len(rows),
            "data": rows
        }


def _infer_document_type(filename: str) -> str:
    """Infer document type from filename."""
    lower = filename.lower()
    if "10-k" in lower or "10k" in lower:
        return "annual_report"
    elif "10-q" in lower or "10q" in lower:
        return "quarterly_report"
    elif "8-k" in lower or "8k" in lower:
        return "current_report"
    elif "earnings" in lower:
        return "earnings"
    return "general"


def _detect_mime(content_bytes: bytes) -> str:
    head = content_bytes[:16]
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if head.startswith(b"PK\x03\x04"):
        return "application/zip"
    if head.startswith(b"\x1f\x8b"):
        return "application/gzip"
    return "application/octet-stream"


def _validate_upload(content_bytes: bytes, filename: str) -> Dict[str, Any]:
    max_bytes = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))
    if len(content_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large (max {max_bytes} bytes)")
    detected = _detect_mime(content_bytes)
    allow_archives = os.getenv("ALLOW_ARCHIVE_UPLOADS", "0") == "1"
    if detected in {"application/zip", "application/gzip"} and not allow_archives:
        raise HTTPException(status_code=400, detail="Archive uploads are disabled")
    return {"detected_mime": detected, "size_bytes": len(content_bytes)}


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    source: Optional[str] = Query(None, description="Filter by source"),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    status: Optional[str] = Query(None, description="Filter by processing status"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Max results per page"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    List ingested documents with optional filters.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    documents = get_documents(db, source, ticker, status, offset, limit)

    role = (user.role or "viewer").lower().strip()
    if role == "approver":
        role = "reviewer"
    allowed_doc_ids: Optional[set[str]] = None
    if role not in {"admin", "auditor"}:
        try:
            from app.services.enterprise_collab import EnterpriseCollabStore

            store = EnterpriseCollabStore(db)
            files = store.list_files(user_id=user.user_id, role=user.role, limit=500)
            allowed = {str(f.get("doc_id") or "") for f in files if f.get("doc_id")}
            allowed_doc_ids = {d for d in allowed if d}
        except Exception:
            allowed_doc_ids = set()

        filtered = []
        for d in documents:
            md = (d.get("metadata") or {}) if isinstance(d, dict) else {}
            owner = md.get("owner_user_id")
            if owner == user.user_id:
                filtered.append(d)
                continue
            if allowed_doc_ids and str(d.get("id") or "") in allowed_doc_ids:
                filtered.append(d)
        documents = filtered
    
    total = len(documents)
    if hasattr(db, "client"):
        # Get total count (server-side) only when DB supports it.
        query = db.client.table("raw_documents").select("id", count="exact")
        if source:
            query = query.eq("source", source)
        if ticker:
            query = query.eq("ticker", ticker)
        if status:
            query = query.eq("processing_status", status)
        result = query.execute()
        total = result.count or len(documents)
        if role not in {"admin", "auditor"}:
            total = len(documents)
    
    return DocumentListResponse(
        documents=documents,
        total=total,
        offset=offset,
        limit=limit
    )


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, user: CurrentUser = Depends(get_current_user)):
    """
    Get a specific document by ID.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    document = get_document_by_id(db, doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    role = (user.role or "viewer").lower().strip()
    if role == "approver":
        role = "reviewer"
    if role not in {"admin", "auditor"}:
        md = (document.get("metadata") or {}) if isinstance(document, dict) else {}
        owner = md.get("owner_user_id")
        if owner != user.user_id:
            try:
                from app.services.enterprise_collab import EnterpriseCollabStore

                store = EnterpriseCollabStore(db)
                files = store.list_files(user_id=user.user_id, role=user.role, limit=500)
                allowed = {str(f.get("doc_id") or "") for f in files if f.get("doc_id")}
                if str(doc_id) not in allowed:
                    raise HTTPException(status_code=403, detail="document access denied")
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=403, detail="document access denied")
    
    return document


@router.get("/stats", response_model=DocumentStatsResponse)
async def get_stats(user: CurrentUser = Depends(get_current_user)):
    """
    Get ingestion statistics.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    role = (user.role or "viewer").lower().strip()
    if role == "approver":
        role = "reviewer"

    documents: List[Dict[str, Any]] = []
    if hasattr(db, "client"):
        # Get all documents (aggregate in memory). Non-admin gets tenant-visible subset only.
        result = db.client.table("raw_documents").select("id, source, processing_status, document_type, metadata").execute()
        documents = result.data or []
    else:
        raw_docs = getattr(db, "raw_documents", {}) or {}
        documents = list(raw_docs.values())
    if role not in {"admin", "auditor"}:
        allowed_doc_ids: set[str] = set()
        try:
            from app.services.enterprise_collab import EnterpriseCollabStore

            store = EnterpriseCollabStore(db)
            files = store.list_files(user_id=user.user_id, role=user.role, limit=500)
            allowed_doc_ids = {str(f.get("doc_id") or "") for f in files if f.get("doc_id")}
            allowed_doc_ids = {d for d in allowed_doc_ids if d}
        except Exception:
            allowed_doc_ids = set()

        visible = []
        for doc in documents:
            md = doc.get("metadata") or {}
            if md.get("owner_user_id") == user.user_id:
                visible.append(doc)
                continue
            if allowed_doc_ids and str(doc.get("id") or "") in allowed_doc_ids:
                visible.append(doc)
        documents = visible
    
    by_source: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    
    for doc in documents:
        source = doc.get("source", "unknown")
        status = doc.get("processing_status", "unknown")
        doc_type = doc.get("document_type", "unknown")
        
        by_source[source] = by_source.get(source, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
        by_type[doc_type] = by_type.get(doc_type, 0) + 1
    
    return DocumentStatsResponse(total_documents=len(documents), by_source=by_source, by_status=by_status, by_type=by_type)


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, user: CurrentUser = Depends(get_current_user)):
    """
    Delete a document.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    role = (user.role or "viewer").lower().strip()
    if role not in {"admin"}:
        raise HTTPException(status_code=403, detail="admin role required")
    
    # Check if exists
    document = get_document_by_id(db, doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete (cascade will handle related records)
    if hasattr(db, "client"):
        db.client.table("raw_documents").delete().eq("id", doc_id).execute()
    else:
        raw_docs = getattr(db, "raw_documents", {}) or {}
        raw_docs.pop(doc_id, None)
    
    return {"status": "deleted", "document_id": doc_id}
