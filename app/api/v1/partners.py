"""
Partner Ingest API (External Company Data)

Purpose:
- Allow other companies to push structured financial facts/tables/events into Preciso.
- Convert the payload into Preciso normalized/distill/spokes via UnifiedConversionEngine.
- Persist it as a raw_document for downstream HITL/WS8 usage.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.ingest import (
    get_db,
    insert_raw_document,
    update_document_content,
    update_document_metadata,
    update_document_status,
)
from app.services.partner_ingest import convert_partner_payload, verify_partner_api_key
from app.services.spokes import build_rag_context, extract_graph_triples
from app.services.spoke_ab_service import SpokeABService
from app.core.tenant_context import get_effective_tenant_id
from app.services.quality_monitor import record_quality_gate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/partners", tags=["Partners"])


class PartnerFinancialsRequest(BaseModel):
    partner_id: str = Field(..., description="Partner identifier (stable)")
    payload: Dict[str, Any] = Field(..., description="Structured financial payload (facts/tables/metadata)")
    source: str = Field("partner", description="Source label for lineage")
    document_type: str = Field("partner_financials", description="Raw document type")
    ticker: Optional[str] = Field(None, description="Optional ticker or entity shortcut")

class PartnerMarketRequest(BaseModel):
    partner_id: str = Field(..., description="Partner identifier (stable)")
    payload: Dict[str, Any] = Field(..., description="Market data payload (facts/metadata/raw)")
    source: str = Field("partner_market", description="Source label for lineage")
    document_type: str = Field("partner_market", description="Raw document type")
    symbol: Optional[str] = Field(None, description="Optional symbol/ticker shortcut")


class PartnerEventRequest(BaseModel):
    partner_id: str = Field(..., description="Partner identifier (stable)")
    payload: Dict[str, Any] = Field(..., description="Event payload (events/metadata)")
    source: str = Field("partner_event", description="Source label for lineage")
    document_type: str = Field("partner_event", description="Raw document type")
    symbol: Optional[str] = Field(None, description="Optional entity symbol shortcut")


class PartnerAltRequest(BaseModel):
    partner_id: str = Field(..., description="Partner identifier (stable)")
    payload: Dict[str, Any] = Field(..., description="Alternative/ownership payload (facts/signals/metadata)")
    source: str = Field("partner_alt", description="Source label for lineage")
    document_type: str = Field("partner_alt", description="Raw document type")
    symbol: Optional[str] = Field(None, description="Optional entity symbol shortcut")


def _ingest_partner_document(
    *,
    db,
    partner_id: str,
    payload: Dict[str, Any],
    source: str,
    document_type: str,
    symbol_or_ticker: Optional[str],
    auth,
    category: Optional[str],
) -> Dict[str, Any]:
    doc_id = insert_raw_document(
        db,
        {
            "source": source,
            "ticker": symbol_or_ticker,
            "document_type": document_type,
            "content": payload,
            "metadata": {
                "partner_id": partner_id,
                "partner_account_id": auth.partner_account_id,
                "partner_key_id": auth.key_id,
                "converted": True,
                "category": category,
            },
        },
    )
    return {"document_id": doc_id}


def _post_process_spokes(
    *,
    db,
    doc_id: str,
    distill,
    normalized: Dict[str, Any],
) -> None:
    try:
        contexts = build_rag_context(distill, case_id=str(doc_id))
        if contexts:
            db.save_rag_context(str(doc_id), contexts)
    except Exception as exc:
        logger.warning("swallowed exception", exc_info=exc)

    try:
        triples = extract_graph_triples(distill)
        if triples:
            db.save_graph_triples(str(doc_id), triples)
    except Exception as exc:
        logger.warning("swallowed exception", exc_info=exc)

    try:
        tenant_id = get_effective_tenant_id()
        service = SpokeABService()
        artifacts = service.build_spoke_b_parquets(
            tenant_id=tenant_id,
            doc_id=str(doc_id),
            distill=distill,
            normalized=normalized,
        )
        service.save_spoke_b_artifacts(db, doc_id=str(doc_id), artifacts=artifacts)
    except Exception as exc:
        logger.warning("swallowed exception", exc_info=exc)


@router.post("/financials")
async def ingest_partner_financials(
    request: PartnerFinancialsRequest,
    x_partner_api_key: Optional[str] = Header(None),
    user_agent: Optional[str] = Header(None),
):
    db = get_db()
    auth = verify_partner_api_key(
        x_partner_api_key,
        db=db,
        partner_id=request.partner_id,
        user_agent=user_agent,
    )
    if not auth.ok:
        raise HTTPException(status_code=401, detail="invalid partner api key")

    # 1) Convert payload into Preciso internal representation
    result = await convert_partner_payload(
        payload=request.payload,
        source=request.source,
        category="fundamentals",
        document_type=request.document_type,
        partner_id=request.partner_id,
    )

    # 2) Persist as raw_document
    doc_id = _ingest_partner_document(
        db=db,
        partner_id=request.partner_id,
        payload=request.payload,
        source=request.source,
        document_type=request.document_type,
        symbol_or_ticker=request.ticker,
        auth=auth,
        category="fundamentals",
    )["document_id"]

    # Save normalized content + conversion artifacts to metadata for downstream use.
    try:
        update_document_content(db, doc_id, result.normalized)
        update_document_metadata(
            db,
            doc_id,
            {
                "partner_id": request.partner_id,
                "converted": True,
                "facts_count": result.distill_facts_count,
                "needs_review": result.needs_review,
                "quality_gate": (result.unified.metrics or {}).get("quality_gate"),
                "unified_summary": {
                    "fact_count": len(result.unified.distill.facts or []),
                    "exports": list((result.unified.exports or {}).keys()),
                    "spokes": list((result.unified.spokes or {}).keys()),
                },
            },
        )
        record_quality_gate(
            db=db,
            doc_id=str(doc_id),
            metadata={
                **(result.normalized.get("metadata") if isinstance(result.normalized, dict) else {}),
                "tenant_id": get_effective_tenant_id(),
            },
            metrics=result.unified.metrics,
            source=request.source,
        )
        _post_process_spokes(db=db, doc_id=str(doc_id), distill=result.unified.distill, normalized=result.normalized)
        update_document_status(db, doc_id, "completed")
    except Exception:
        # Non-blocking; raw payload was already stored.
        update_document_status(db, doc_id, "completed")

    return {
        "document_id": doc_id,
        "facts_count": result.distill_facts_count,
        "needs_review": result.needs_review,
        "auth_mode": auth.mode,
        "message": "partner payload ingested",
    }


@router.post("/market")
async def ingest_partner_market(
    request: PartnerMarketRequest,
    x_partner_api_key: Optional[str] = Header(None),
    user_agent: Optional[str] = Header(None),
):
    db = get_db()
    auth = verify_partner_api_key(
        x_partner_api_key,
        db=db,
        partner_id=request.partner_id,
        user_agent=user_agent,
    )
    if not auth.ok:
        raise HTTPException(status_code=401, detail="invalid partner api key")

    result = await convert_partner_payload(
        payload=request.payload,
        source=request.source,
        category="market",
        document_type=request.document_type,
        partner_id=request.partner_id,
    )
    doc_id = _ingest_partner_document(
        db=db,
        partner_id=request.partner_id,
        payload=request.payload,
        source=request.source,
        document_type=request.document_type,
        symbol_or_ticker=request.symbol,
        auth=auth,
        category="market",
    )["document_id"]
    try:
        update_document_content(db, doc_id, result.normalized)
        update_document_metadata(
            db,
            doc_id,
            {
                "partner_id": request.partner_id,
                "converted": True,
                "facts_count": result.distill_facts_count,
                "needs_review": result.needs_review,
                "category": "market",
                "quality_gate": (result.unified.metrics or {}).get("quality_gate"),
                "unified_summary": {
                    "fact_count": len(result.unified.distill.facts or []),
                    "exports": list((result.unified.exports or {}).keys()),
                    "spokes": list((result.unified.spokes or {}).keys()),
                },
            },
        )
        record_quality_gate(
            db=db,
            doc_id=str(doc_id),
            metadata={
                **(result.normalized.get("metadata") if isinstance(result.normalized, dict) else {}),
                "tenant_id": get_effective_tenant_id(),
            },
            metrics=result.unified.metrics,
            source=request.source,
        )
        _post_process_spokes(db=db, doc_id=str(doc_id), distill=result.unified.distill, normalized=result.normalized)
        update_document_status(db, doc_id, "completed")
    except Exception:
        update_document_status(db, doc_id, "completed")
    return {
        "document_id": doc_id,
        "facts_count": result.distill_facts_count,
        "needs_review": result.needs_review,
        "auth_mode": auth.mode,
        "message": "partner market payload ingested",
    }


@router.post("/events")
async def ingest_partner_events(
    request: PartnerEventRequest,
    x_partner_api_key: Optional[str] = Header(None),
    user_agent: Optional[str] = Header(None),
):
    db = get_db()
    auth = verify_partner_api_key(
        x_partner_api_key,
        db=db,
        partner_id=request.partner_id,
        user_agent=user_agent,
    )
    if not auth.ok:
        raise HTTPException(status_code=401, detail="invalid partner api key")

    result = await convert_partner_payload(
        payload=request.payload,
        source=request.source,
        category="event",
        document_type=request.document_type,
        partner_id=request.partner_id,
    )
    doc_id = _ingest_partner_document(
        db=db,
        partner_id=request.partner_id,
        payload=request.payload,
        source=request.source,
        document_type=request.document_type,
        symbol_or_ticker=request.symbol,
        auth=auth,
        category="event",
    )["document_id"]
    try:
        update_document_content(db, doc_id, result.normalized)
        update_document_metadata(
            db,
            doc_id,
            {
                "partner_id": request.partner_id,
                "converted": True,
                "facts_count": result.distill_facts_count,
                "needs_review": result.needs_review,
                "category": "event",
                "quality_gate": (result.unified.metrics or {}).get("quality_gate"),
                "unified_summary": {
                    "fact_count": len(result.unified.distill.facts or []),
                    "exports": list((result.unified.exports or {}).keys()),
                    "spokes": list((result.unified.spokes or {}).keys()),
                },
            },
        )
        record_quality_gate(
            db=db,
            doc_id=str(doc_id),
            metadata={
                **(result.normalized.get("metadata") if isinstance(result.normalized, dict) else {}),
                "tenant_id": get_effective_tenant_id(),
            },
            metrics=result.unified.metrics,
            source=request.source,
        )
        _post_process_spokes(db=db, doc_id=str(doc_id), distill=result.unified.distill, normalized=result.normalized)
        update_document_status(db, doc_id, "completed")
    except Exception:
        update_document_status(db, doc_id, "completed")
    return {
        "document_id": doc_id,
        "facts_count": result.distill_facts_count,
        "needs_review": result.needs_review,
        "auth_mode": auth.mode,
        "message": "partner event payload ingested",
    }


@router.post("/alt")
async def ingest_partner_alt(
    request: PartnerAltRequest,
    x_partner_api_key: Optional[str] = Header(None),
    user_agent: Optional[str] = Header(None),
):
    db = get_db()
    auth = verify_partner_api_key(
        x_partner_api_key,
        db=db,
        partner_id=request.partner_id,
        user_agent=user_agent,
    )
    if not auth.ok:
        raise HTTPException(status_code=401, detail="invalid partner api key")

    result = await convert_partner_payload(
        payload=request.payload,
        source=request.source,
        category="alternative",
        document_type=request.document_type,
        partner_id=request.partner_id,
    )
    doc_id = _ingest_partner_document(
        db=db,
        partner_id=request.partner_id,
        payload=request.payload,
        source=request.source,
        document_type=request.document_type,
        symbol_or_ticker=request.symbol,
        auth=auth,
        category="alternative",
    )["document_id"]
    try:
        update_document_content(db, doc_id, result.normalized)
        update_document_metadata(
            db,
            doc_id,
            {
                "partner_id": request.partner_id,
                "converted": True,
                "facts_count": result.distill_facts_count,
                "needs_review": result.needs_review,
                "category": "alternative",
                "quality_gate": (result.unified.metrics or {}).get("quality_gate"),
                "unified_summary": {
                    "fact_count": len(result.unified.distill.facts or []),
                    "exports": list((result.unified.exports or {}).keys()),
                    "spokes": list((result.unified.spokes or {}).keys()),
                },
            },
        )
        record_quality_gate(
            db=db,
            doc_id=str(doc_id),
            metadata={
                **(result.normalized.get("metadata") if isinstance(result.normalized, dict) else {}),
                "tenant_id": get_effective_tenant_id(),
            },
            metrics=result.unified.metrics,
            source=request.source,
        )
        _post_process_spokes(db=db, doc_id=str(doc_id), distill=result.unified.distill, normalized=result.normalized)
        update_document_status(db, doc_id, "completed")
    except Exception:
        update_document_status(db, doc_id, "completed")
    return {
        "document_id": doc_id,
        "facts_count": result.distill_facts_count,
        "needs_review": result.needs_review,
        "auth_mode": auth.mode,
        "message": "partner alt payload ingested",
    }


@router.get("/documents")
async def list_partner_documents(
    partner_id: str,
    limit: int = 50,
    x_partner_api_key: Optional[str] = Header(None),
    user_agent: Optional[str] = Header(None),
):
    db = get_db()
    auth = verify_partner_api_key(
        x_partner_api_key,
        db=db,
        partner_id=partner_id,
        user_agent=user_agent,
    )
    if not auth.ok:
        raise HTTPException(status_code=401, detail="invalid partner api key")

    res = (
        db.client.table("raw_documents")
        .select("id, source, ticker, document_type, document_date, ingested_at, processing_status, metadata")
        .contains("metadata", {"partner_id": partner_id})
        .order("ingested_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"partner_id": partner_id, "documents": res.data or []}


@router.get("/documents/{document_id}")
async def get_partner_document(
    document_id: str,
    partner_id: str,
    x_partner_api_key: Optional[str] = Header(None),
    user_agent: Optional[str] = Header(None),
):
    db = get_db()
    auth = verify_partner_api_key(
        x_partner_api_key,
        db=db,
        partner_id=partner_id,
        user_agent=user_agent,
    )
    if not auth.ok:
        raise HTTPException(status_code=401, detail="invalid partner api key")

    res = db.client.table("raw_documents").select("*").eq("id", document_id).limit(1).execute()
    row = (res.data or [None])[0]
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    meta = row.get("metadata") or {}
    if (meta.get("partner_id") or "") != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    return row
