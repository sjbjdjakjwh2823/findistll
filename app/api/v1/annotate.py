"""
DataForge Annotate API - Phase 1
Human-in-the-Loop (HITL) annotation and feedback pipeline.
"""

import logging
import json
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/annotate", tags=["DataForge - Annotate"])


# =============================================================================
# Models
# =============================================================================

class AnnotationRequest(BaseModel):
    """Request model for submitting an annotation."""
    sample_id: str = Field(..., description="Generated sample ID")
    annotator_id: str = Field(..., description="Annotator identifier (email or ID)")
    annotator_name: Optional[str] = Field(None, description="Annotator display name")
    action: str = Field(..., description="Action: 'approved', 'corrected', 'rejected'")
    corrections: Optional[Dict[str, Any]] = Field(None, description="Corrected content (if action is 'corrected')")
    reasoning: Optional[str] = Field(None, description="Explanation for the decision")
    time_spent_seconds: Optional[int] = Field(None, description="Time spent on annotation")


class AnnotationResponse(BaseModel):
    """Response model for annotation submission."""
    annotation_id: str
    status: str
    message: str


class NextSampleResponse(BaseModel):
    """Response for getting next sample to review."""
    sample_id: Optional[str] = None
    template_type: Optional[str] = None
    generated_content: Optional[Dict[str, Any]] = None
    source: Optional[str] = None
    ticker: Optional[str] = None
    raw_content: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None
    has_sample: bool = False
    message: Optional[str] = None


class AnnotationListResponse(BaseModel):
    """Response for listing annotations."""
    annotations: List[Dict[str, Any]]
    total: int
    offset: int
    limit: int


class AnnotatorStatsResponse(BaseModel):
    """Response for annotator statistics."""
    annotator_id: str
    total_annotations: int
    approved: int
    corrected: int
    rejected: int
    avg_time_seconds: Optional[float]
    approval_rate: float
    daily_stats: List[Dict[str, Any]]


class QueueStatsResponse(BaseModel):
    """Response for queue statistics."""
    total_pending: int
    total_in_review: int
    total_approved: int
    total_corrected: int
    total_rejected: int
    by_template_type: Dict[str, Dict[str, int]]
    avg_confidence_pending: Optional[float]


# =============================================================================
# Database Functions
# =============================================================================

def get_db():
    """Get database client."""
    from app.db.supabase_db import SupabaseDB
    from app.core.config import load_settings
    
    settings = load_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    return SupabaseDB(settings.supabase_url, settings.supabase_service_role_key)


def get_sample_by_id(db, sample_id: str) -> Optional[Dict[str, Any]]:
    """Get a sample by ID."""
    result = db.client.table("generated_samples").select("*, raw_documents(source, ticker, document_type, raw_content)").eq("id", sample_id).execute()
    return result.data[0] if result.data else None


def get_next_pending_sample(db, template_type: Optional[str] = None, annotator_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get the next sample for review (highest priority first)."""
    query = db.client.table("generated_samples").select(
        "id, template_type, generated_content, confidence_score, raw_documents(source, ticker, document_type, raw_content)"
    ).eq("review_status", "pending")
    
    if template_type:
        query = query.eq("template_type", template_type)
    
    query = query.order("priority_score", desc=True).order("created_at").limit(1)
    
    result = query.execute()
    return result.data[0] if result.data else None


def update_sample_status(db, sample_id: str, status: str, corrections: Optional[Dict[str, Any]] = None):
    """Update sample review status."""
    payload = {"review_status": status}
    
    if status == "corrected" and corrections:
        payload["generated_content"] = corrections
    
    db.client.table("generated_samples").update(payload).eq("id", sample_id).execute()


def insert_annotation(db, annotation_data: Dict[str, Any]) -> str:
    """Insert a human annotation."""
    annotation_id = str(uuid4())
    
    # Get original content for snapshot
    sample = db.client.table("generated_samples").select("generated_content").eq("id", annotation_data["sample_id"]).execute()
    original_content = sample.data[0]["generated_content"] if sample.data else None
    
    payload = {
        "id": annotation_id,
        "sample_id": annotation_data["sample_id"],
        "annotator_id": annotation_data["annotator_id"],
        "annotator_name": annotation_data.get("annotator_name"),
        "action": annotation_data["action"],
        "original_content": original_content,
        "corrections": annotation_data.get("corrections"),
        "reasoning": annotation_data.get("reasoning"),
        "time_spent_seconds": annotation_data.get("time_spent_seconds")
    }
    
    db.client.table("human_annotations").insert(payload).execute()
    return annotation_id


def get_annotations(
    db,
    annotator_id: Optional[str] = None,
    action: Optional[str] = None,
    offset: int = 0,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Query annotations with filters."""
    query = db.client.table("human_annotations").select("*, generated_samples(template_type, raw_document_id)")
    
    if annotator_id:
        query = query.eq("annotator_id", annotator_id)
    if action:
        query = query.eq("action", action)
    
    query = query.order("annotated_at", desc=True)
    query = query.range(offset, offset + limit - 1)
    
    result = query.execute()
    return result.data or []


def get_annotation_by_id(db, annotation_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific annotation."""
    result = db.client.table("human_annotations").select("*, generated_samples(template_type, generated_content, raw_document_id)").eq("id", annotation_id).execute()
    return result.data[0] if result.data else None


def get_annotator_stats(db, annotator_id: str) -> Dict[str, Any]:
    """Get statistics for an annotator."""
    result = db.client.table("human_annotations").select("action, time_spent_seconds, annotated_at").eq("annotator_id", annotator_id).execute()
    
    annotations = result.data or []
    
    if not annotations:
        return {
            "annotator_id": annotator_id,
            "total_annotations": 0,
            "approved": 0,
            "corrected": 0,
            "rejected": 0,
            "avg_time_seconds": None,
            "approval_rate": 0.0,
            "daily_stats": []
        }
    
    # Count by action
    approved = sum(1 for a in annotations if a["action"] == "approved")
    corrected = sum(1 for a in annotations if a["action"] == "corrected")
    rejected = sum(1 for a in annotations if a["action"] == "rejected")
    
    # Calculate average time
    times = [a["time_spent_seconds"] for a in annotations if a.get("time_spent_seconds")]
    avg_time = sum(times) / len(times) if times else None
    
    # Daily aggregation
    daily_counts: Dict[str, Dict[str, int]] = {}
    for a in annotations:
        day = a["annotated_at"][:10] if a.get("annotated_at") else "unknown"
        if day not in daily_counts:
            daily_counts[day] = {"approved": 0, "corrected": 0, "rejected": 0}
        action = a["action"]
        if action in daily_counts[day]:
            daily_counts[day][action] += 1
    
    daily_stats = [{"date": k, **v} for k, v in sorted(daily_counts.items(), reverse=True)[:30]]
    
    total = len(annotations)
    approval_rate = (approved + corrected) / total if total > 0 else 0.0
    
    return {
        "annotator_id": annotator_id,
        "total_annotations": total,
        "approved": approved,
        "corrected": corrected,
        "rejected": rejected,
        "avg_time_seconds": avg_time,
        "approval_rate": approval_rate,
        "daily_stats": daily_stats
    }


def get_queue_stats(db) -> Dict[str, Any]:
    """Get overall queue statistics."""
    result = db.client.table("generated_samples").select("review_status, template_type, confidence_score").execute()
    samples = result.data or []
    
    total_pending = sum(1 for s in samples if s["review_status"] == "pending")
    total_in_review = sum(1 for s in samples if s["review_status"] == "in_review")
    total_approved = sum(1 for s in samples if s["review_status"] == "approved")
    total_corrected = sum(1 for s in samples if s["review_status"] == "corrected")
    total_rejected = sum(1 for s in samples if s["review_status"] == "rejected")
    
    # By template type
    by_template: Dict[str, Dict[str, int]] = {}
    for s in samples:
        tt = s.get("template_type", "unknown")
        status = s.get("review_status", "unknown")
        if tt not in by_template:
            by_template[tt] = {"pending": 0, "in_review": 0, "approved": 0, "corrected": 0, "rejected": 0}
        if status in by_template[tt]:
            by_template[tt][status] += 1
    
    # Average confidence of pending
    pending_confidences = [s["confidence_score"] for s in samples if s["review_status"] == "pending" and s.get("confidence_score")]
    avg_confidence = sum(pending_confidences) / len(pending_confidences) if pending_confidences else None
    
    return {
        "total_pending": total_pending,
        "total_in_review": total_in_review,
        "total_approved": total_approved,
        "total_corrected": total_corrected,
        "total_rejected": total_rejected,
        "by_template_type": by_template,
        "avg_confidence_pending": avg_confidence
    }


def update_annotator_daily_stats(db, annotator_id: str, action: str, time_spent: Optional[int]):
    """Update daily annotator statistics."""
    today = date.today().isoformat()
    
    # Check if record exists
    result = db.client.table("annotator_stats").select("*").eq("annotator_id", annotator_id).eq("stat_date", today).execute()
    
    if result.data:
        # Update existing
        existing = result.data[0]
        updates = {
            "annotations_count": existing["annotations_count"] + 1
        }
        if action == "approved":
            updates["approved_count"] = existing["approved_count"] + 1
        elif action == "corrected":
            updates["corrected_count"] = existing["corrected_count"] + 1
        elif action == "rejected":
            updates["rejected_count"] = existing["rejected_count"] + 1
        
        if time_spent:
            current_avg = existing.get("avg_time_per_annotation") or time_spent
            count = existing["annotations_count"]
            updates["avg_time_per_annotation"] = (current_avg * count + time_spent) / (count + 1)
        
        db.client.table("annotator_stats").update(updates).eq("id", existing["id"]).execute()
    else:
        # Insert new
        payload = {
            "id": str(uuid4()),
            "annotator_id": annotator_id,
            "stat_date": today,
            "annotations_count": 1,
            "approved_count": 1 if action == "approved" else 0,
            "corrected_count": 1 if action == "corrected" else 0,
            "rejected_count": 1 if action == "rejected" else 0,
            "avg_time_per_annotation": time_spent
        }
        db.client.table("annotator_stats").insert(payload).execute()


def update_dataforge_metrics(db, action: str):
    """Update daily DataForge metrics."""
    today = date.today().isoformat()
    
    # Check if record exists
    result = db.client.table("dataforge_metrics").select("*").eq("metric_date", today).execute()
    
    field_map = {
        "approved": "samples_approved",
        "corrected": "samples_corrected",
        "rejected": "samples_rejected"
    }
    
    field = field_map.get(action)
    if not field:
        return
    
    if result.data:
        existing = result.data[0]
        updates = {field: existing[field] + 1}
        db.client.table("dataforge_metrics").update(updates).eq("id", existing["id"]).execute()
    else:
        payload = {
            "id": str(uuid4()),
            "metric_date": today,
            "documents_ingested": 0,
            "samples_generated": 0,
            "samples_approved": 1 if action == "approved" else 0,
            "samples_corrected": 1 if action == "corrected" else 0,
            "samples_rejected": 1 if action == "rejected" else 0
        }
        db.client.table("dataforge_metrics").insert(payload).execute()


# =============================================================================
# WS8: Spoke A/B downstream artifacts on HITL approval
# =============================================================================

def _build_distill_from_raw_document(raw_doc: Dict[str, Any]) -> "DistillResult":
    """
    Best-effort DistillResult from DataForge raw_documents row.
    raw_documents.raw_content is already "normalized" when UnifiedConversionEngine ran.
    """
    from app.services.types import DistillResult

    raw_content = (raw_doc or {}).get("raw_content") or {}
    facts = raw_content.get("facts") or []
    cot = raw_content.get("cot_markdown")
    if not cot:
        jsonl_data = raw_content.get("jsonl_data") or []
        if isinstance(jsonl_data, list) and jsonl_data:
            cot = "\n".join([str(x) for x in jsonl_data])
    if not cot:
        reasoning_qa = raw_content.get("reasoning_qa") or []
        if isinstance(reasoning_qa, list) and reasoning_qa:
            cot = "\n\n".join([str(qa.get("response", "")) for qa in reasoning_qa if isinstance(qa, dict)])
    metadata = {
        "source": raw_doc.get("source"),
        "ticker": raw_doc.get("ticker"),
        "document_type": raw_doc.get("document_type"),
        "doc_id": raw_doc.get("id"),
    }
    return DistillResult(facts=facts, cot_markdown=cot or "", metadata=metadata)


def _ws8_on_approval(db, *, sample: Dict[str, Any], request: AnnotationRequest) -> None:
    """
    Hook: when a HITL action is approved/corrected, generate:
    - Spoke A training record (JSONL)
    - Spoke B artifacts (facts/tables/features parquet)
    Failures must not break HITL submission.
    """
    from app.core.tenant_context import get_effective_tenant_id
    from app.services.spoke_ab_service import SpokeABService
    from app.services.spokes import build_rag_context

    action = request.action
    if action not in ("approved", "corrected"):
        return

    tenant_id = get_effective_tenant_id()
    raw_doc = sample.get("raw_documents") or {}
    doc_id = str(sample.get("raw_document_id") or raw_doc.get("id") or "")
    if not doc_id:
        return

    template_type = str(sample.get("template_type") or "unknown")
    instruction_map = {
        "risk_analysis": "Write an audit-grade risk analysis grounded in the provided evidence and numeric facts.",
        "summary": "Summarize the document with numeric precision and cite key evidence.",
        "qa_pair": "Answer the question using only the provided evidence; include numeric facts when relevant.",
        "reasoning_chain": "Produce a step-by-step reasoning answer grounded in evidence and numeric facts.",
        "metrics_extraction": "Extract key financial metrics with periods/units and provide a grounded explanation.",
    }
    instruction = instruction_map.get(template_type, "Generate a grounded answer based on the provided evidence.")

    distill = _build_distill_from_raw_document(raw_doc)
    fact_preview = "\n".join([str(f) for f in (distill.facts or [])[:40]])
    input_text = (
        f"Doc: {doc_id}\n"
        f"Source: {raw_doc.get('source')}\n"
        f"Ticker: {raw_doc.get('ticker')}\n"
        f"Type: {raw_doc.get('document_type')}\n\n"
        f"Facts (preview):\n{fact_preview}\n\n"
        f"CoT/Notes:\n{(distill.cot_markdown or '')[:6000]}"
    )
    math_summary = service.build_math_summary(distill)
    if math_summary:
        input_text = input_text + "\n\n" + math_summary

    original = sample.get("generated_content") or {}
    final_output = original if action == "approved" else (request.corrections or {})
    output_text = json.dumps(final_output, ensure_ascii=False, default=str)
    if request.reasoning:
        output_text = output_text + "\n\nHuman reasoning:\n" + request.reasoning

    rag_contexts = build_rag_context(distill, case_id=str(sample.get("id") or request.sample_id))
    if rag_contexts:
        evidence_chunk_ids = [c.get("chunk_id") for c in rag_contexts if c.get("chunk_id")]
    else:
        evidence_chunk_ids = [f"raw_doc:{doc_id}", f"facts:{doc_id}"]

    service = SpokeABService()
    fact_refs = service.build_fact_refs(distill, limit=80)
    selfcheck_payload = {"confidence_score": float(sample.get("confidence_score") or 0.0)}
    approval_meta = {
        "approved_by": request.annotator_id,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "edit_distance": abs(len(json.dumps(original, ensure_ascii=False, default=str)) - len(json.dumps(final_output, ensure_ascii=False, default=str))),
        "source": raw_doc.get("source") or "dataforge",
    }

    ds = db.get_or_create_active_dataset_version(
        name_hint=datetime.now(timezone.utc).strftime("dataset-%Y-%m-%d")
    )
    version = ds.get("name") or "active"
    spoke_a = service.build_spoke_a_record(
        tenant_id=tenant_id,
        doc_id=doc_id,
        case_id=str(sample.get("id") or request.sample_id),
        version=str(version),
        instruction=instruction,
        input_text=input_text,
        output_text=output_text,
        evidence_chunk_ids=evidence_chunk_ids,
        fact_refs=fact_refs,
        selfcheck=selfcheck_payload,
        approval=approval_meta,
    )
    gates = service.evaluate_gates(spoke_a_record=spoke_a, distill=distill)
    db.insert_spoke_a_sample(
        {
            "dataset_version_id": ds.get("id"),
            "case_id": str(sample.get("id") or request.sample_id),
            "doc_id": doc_id,
            "sample_json": spoke_a,
            "jsonl_line": json.dumps(spoke_a, ensure_ascii=False, default=str),
            "gates": gates.details,
            "status": gates.status,
        }
    )

    if rag_contexts:
        try:
            db.save_rag_context(str(sample.get("id") or request.sample_id), rag_contexts)
        except Exception as exc:
            logger.warning("swallowed exception", exc_info=exc)

    artifacts = service.build_spoke_b_parquets(
        tenant_id=tenant_id,
        doc_id=doc_id,
        distill=distill,
        normalized=(raw_doc.get("raw_content") or {}),
    )
    service.save_spoke_b_artifacts(
        db=db,
        doc_id=doc_id,
        artifacts=artifacts,
        metadata={"sample_id": str(sample.get("id") or request.sample_id), "template_type": template_type},
    )


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/submit", response_model=AnnotationResponse)
async def submit_annotation(request: AnnotationRequest):
    """
    Submit a human annotation for a generated sample.
    
    Actions:
    - `approved`: Sample is correct as-is
    - `corrected`: Sample needs corrections (provide in `corrections` field)
    - `rejected`: Sample is unusable
    """
    if request.action not in ["approved", "corrected", "rejected"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid action. Must be 'approved', 'corrected', or 'rejected'"
        )
    
    if request.action == "corrected" and not request.corrections:
        raise HTTPException(
            status_code=400,
            detail="Corrections required when action is 'corrected'"
        )
    
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # Verify sample exists
    sample = get_sample_by_id(db, request.sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    # Insert annotation
    annotation_data = {
        "sample_id": request.sample_id,
        "annotator_id": request.annotator_id,
        "annotator_name": request.annotator_name,
        "action": request.action,
        "corrections": request.corrections,
        "reasoning": request.reasoning,
        "time_spent_seconds": request.time_spent_seconds
    }
    
    try:
        annotation_id = insert_annotation(db, annotation_data)
        
        # Update sample status
        update_sample_status(db, request.sample_id, request.action, request.corrections)
        
        # Update statistics
        update_annotator_daily_stats(db, request.annotator_id, request.action, request.time_spent_seconds)
        update_dataforge_metrics(db, request.action)

        # WS8: generate Spoke A/B artifacts on approval/correction.
        try:
            _ws8_on_approval(db, sample=sample, request=request)
        except Exception as ws8_exc:
            logger.warning(f"WS8 spoke A/B generation failed (non-blocking): {ws8_exc}")
        
        return AnnotationResponse(
            annotation_id=annotation_id,
            status="success",
            message=f"Sample {request.action} successfully"
        )
        
    except Exception as e:
        logger.error(f"Annotation submission failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save annotation: {str(e)}")


@router.get("/next", response_model=NextSampleResponse)
async def get_next_sample(
    annotator_id: str = Query(..., description="Annotator ID"),
    template_type: Optional[str] = Query(None, description="Filter by template type")
):
    """
    Get the next sample for review from the HITL queue.
    
    Returns the highest priority pending sample and marks it as in_review.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    sample = get_next_pending_sample(db, template_type, annotator_id)
    
    if not sample:
        return NextSampleResponse(
            has_sample=False,
            message="No pending samples in queue"
        )
    
    # Mark as in_review
    update_sample_status(db, sample["id"], "in_review")
    
    # Extract nested document info
    doc_info = sample.get("raw_documents", {})
    
    return NextSampleResponse(
        sample_id=sample["id"],
        template_type=sample["template_type"],
        generated_content=sample["generated_content"],
        source=doc_info.get("source"),
        ticker=doc_info.get("ticker"),
        raw_content=doc_info.get("raw_content"),
        confidence_score=sample.get("confidence_score"),
        has_sample=True,
        message="Sample ready for review"
    )


@router.post("/skip/{sample_id}")
async def skip_sample(sample_id: str, annotator_id: str = Query(...)):
    """
    Skip a sample and return it to the queue.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    sample = get_sample_by_id(db, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    # Return to pending
    update_sample_status(db, sample_id, "pending")
    
    return {"status": "skipped", "sample_id": sample_id, "message": "Sample returned to queue"}


@router.get("/sample/{sample_id}")
async def get_sample_for_review(sample_id: str):
    """
    Get a specific sample for review (with source document context).
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    sample = get_sample_by_id(db, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    return sample


@router.get("/annotations", response_model=AnnotationListResponse)
async def list_annotations(
    annotator_id: Optional[str] = Query(None, description="Filter by annotator"),
    action: Optional[str] = Query(None, description="Filter by action"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    List annotations with optional filters.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    annotations = get_annotations(db, annotator_id, action, offset, limit)
    
    # Get total count
    query = db.client.table("human_annotations").select("id", count="exact")
    if annotator_id:
        query = query.eq("annotator_id", annotator_id)
    if action:
        query = query.eq("action", action)
    
    result = query.execute()
    total = result.count or len(annotations)
    
    return AnnotationListResponse(
        annotations=annotations,
        total=total,
        offset=offset,
        limit=limit
    )


@router.get("/annotations/{annotation_id}")
async def get_annotation(annotation_id: str):
    """
    Get a specific annotation.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    annotation = get_annotation_by_id(db, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    return annotation


@router.get("/stats/annotator/{annotator_id}", response_model=AnnotatorStatsResponse)
async def get_annotator_statistics(annotator_id: str):
    """
    Get statistics for a specific annotator.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    stats = get_annotator_stats(db, annotator_id)
    return AnnotatorStatsResponse(**stats)


@router.get("/stats/queue", response_model=QueueStatsResponse)
async def get_queue_statistics():
    """
    Get overall HITL queue statistics.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    stats = get_queue_stats(db)
    return QueueStatsResponse(**stats)


@router.get("/leaderboard")
async def get_annotator_leaderboard(limit: int = Query(10, ge=1, le=50)):
    """
    Get annotator leaderboard by annotation count.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    result = db.client.table("annotator_stats").select("*").order("annotations_count", desc=True).limit(limit).execute()
    
    # Aggregate by annotator
    annotator_totals: Dict[str, Dict[str, Any]] = {}
    for row in (result.data or []):
        aid = row["annotator_id"]
        if aid not in annotator_totals:
            annotator_totals[aid] = {
                "annotator_id": aid,
                "total_annotations": 0,
                "approved": 0,
                "corrected": 0,
                "rejected": 0
            }
        annotator_totals[aid]["total_annotations"] += row.get("annotations_count", 0)
        annotator_totals[aid]["approved"] += row.get("approved_count", 0)
        annotator_totals[aid]["corrected"] += row.get("corrected_count", 0)
        annotator_totals[aid]["rejected"] += row.get("rejected_count", 0)
    
    leaderboard = sorted(annotator_totals.values(), key=lambda x: x["total_annotations"], reverse=True)[:limit]
    
    return {"leaderboard": leaderboard}
