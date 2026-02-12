from __future__ import annotations

import json
from typing import Any, Dict, Optional

from app.api.v1.ingest import compute_file_hash, get_db, insert_raw_document, update_document_status
from app.services.metrics_logger import MetricsLogger
from app.services.spokes import build_rag_context, extract_graph_triples
from app.services.spoke_ab_service import SpokeABService
from app.services.types import DistillResult
from app.services.spoke_c_rag import RAGEngine
from app.core.tenant_context import get_effective_tenant_id


def ingest_snapshot(source: str, symbol: Optional[str], content: Dict[str, Any]) -> str:
    """
    Insert normalized external data into raw_documents + spokes.
    Returns document id. Uses file_hash for idempotency.
    """
    db = get_db()
    payload_bytes = json.dumps(content, sort_keys=True, ensure_ascii=True).encode("utf-8")
    file_hash = compute_file_hash(payload_bytes)

    doc_data = {
        "source": source,
        "ticker": symbol,
        "document_type": "market_snapshot",
        "document_date": None,
        "content": content,
        "file_hash": file_hash,
        "metadata": {"source": source, "symbol": symbol, "tenant_id": get_effective_tenant_id()},
    }
    doc_id = insert_raw_document(db, doc_data)
    update_document_status(db, doc_id, "completed")

    facts = (content or {}).get("facts") if isinstance(content, dict) else None
    if not facts:
        return doc_id

    distill = DistillResult(facts=facts, cot_markdown="", metadata={"doc_id": doc_id, "source": source, "symbol": symbol})
    contexts = build_rag_context(distill, case_id=str(doc_id))
    if contexts:
        db.save_rag_context(str(doc_id), contexts)
        supa_client = getattr(db, "client", None)
        if supa_client:
            rag_engine = RAGEngine(supabase_client=supa_client)
            rag_text = "\n\n".join([ctx.get("text_content") or "" for ctx in contexts if ctx.get("text_content")])
            ingested = rag_engine.ingest_document(rag_text, metadata={"doc_id": doc_id, "source": source})
            MetricsLogger().log("market.spoke_c.ingested_chunks", ingested, {"source": source})

    triples = extract_graph_triples(distill)
    if triples:
        db.save_graph_triples(str(doc_id), triples)
        MetricsLogger().log("market.spoke_d.triples", len(triples), {"source": source})

    try:
        tenant_id = get_effective_tenant_id()
        service = SpokeABService()
        artifacts = service.build_spoke_b_parquets(
            tenant_id=tenant_id,
            doc_id=str(doc_id),
            distill=distill,
            normalized=content if isinstance(content, dict) else None,
        )
        service.save_spoke_b_artifacts(db, doc_id=str(doc_id), artifacts=artifacts)
        MetricsLogger().log("market.spoke_b.artifacts", len(artifacts), {"source": source})
    except Exception:
        MetricsLogger().log("market.spoke_b.artifacts_error", 1, {"source": source})

    return doc_id
