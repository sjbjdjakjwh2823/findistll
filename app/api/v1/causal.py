from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.registry import get_db
from app.services.causal_story import CausalStoryService
from app.services.types import DistillResult


router = APIRouter(prefix="/causal", tags=["Causal"])


class CausalStoryRequest(BaseModel):
    entity: Optional[str] = Field(None, description="Entity/company name or ticker")
    as_of: Optional[str] = Field(None, description="As-of date (YYYY-MM-DD). If omitted, inferred from document facts/metadata.")
    horizon_days: int = Field(30, ge=1, le=365, description="Forecast horizon for hypothesis step")
    document_id: Optional[str] = Field(None, description="Optional raw_documents id to load distill facts from")
    max_graph_triples: int = Field(1200, ge=200, le=5000)


@router.post("/story")
async def build_causal_story(payload: CausalStoryRequest) -> Dict[str, Any]:
    """
    Build an evidence-grounded causal chain across macro/fundamentals/supply-chain/market.

    This endpoint is designed for enterprise UI consumption:
    - It never asserts forecasts as facts; forecast is explicitly labeled hypothesis.
    - It returns Spoke C chunk IDs + fact refs when available.
    """
    db = get_db()

    distill = DistillResult(facts=[], cot_markdown="", metadata={})
    if payload.document_id:
        try:
            doc: Optional[Dict[str, Any]] = None
            if hasattr(db, "client"):
                # Supabase path: raw_documents.raw_content is "normalized" output when UnifiedConversionEngine ran.
                row = db.client.table("raw_documents").select("id,raw_content,metadata,source,ticker,document_type").eq("id", payload.document_id).limit(1).execute()  # type: ignore[attr-defined]
                doc = (row.data or [None])[0] if hasattr(row, "data") else None
            else:
                raw_docs = getattr(db, "raw_documents", None)
                if isinstance(raw_docs, dict):
                    doc = raw_docs.get(payload.document_id)

            raw = (doc or {}).get("raw_content") or (doc or {}).get("content") or {}
            meta = (doc or {}).get("metadata") or {}
            if isinstance(raw, dict):
                distill = DistillResult(
                    facts=(raw.get("facts") or []),
                    cot_markdown=(raw.get("cot_markdown") or raw.get("summary") or ""),
                    metadata={**(meta if isinstance(meta, dict) else {}), "doc_id": payload.document_id, "source": (doc or {}).get("source")},
                )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"failed to load document_id: {exc}")

    service = CausalStoryService(db=db)
    return await service.build_story(
        distill=distill,
        entity_hint=payload.entity,
        as_of=payload.as_of,
        horizon_days=payload.horizon_days,
        max_graph_triples=payload.max_graph_triples,
        document_id=payload.document_id,
    )
