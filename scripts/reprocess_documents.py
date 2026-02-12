from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

from app.db.registry import get_db
from app.services.unified_engine import UnifiedConversionEngine
from app.api.v1.ingest import update_document_content, update_document_metadata, update_document_status


def _fetch_raw_document(db, doc_id: str) -> Optional[Dict[str, Any]]:
    if hasattr(db, "client"):
        res = db.client.table("raw_documents").select("*").eq("id", doc_id).limit(1).execute()
        return (res.data or [None])[0]
    raw_docs = getattr(db, "raw_documents", {}) or {}
    return raw_docs.get(doc_id)


def _list_needs_review_docs(db, limit: int) -> List[Dict[str, Any]]:
    if hasattr(db, "client"):
        res = (
            db.client.table("raw_documents")
            .select("id, metadata, raw_content, source, document_type")
            .limit(limit)
            .execute()
        )
        rows = res.data or []
        return [r for r in rows if (r.get("metadata") or {}).get("needs_review")]
    raw_docs = getattr(db, "raw_documents", {}) or {}
    out = []
    for item in raw_docs.values():
        if (item.get("metadata") or {}).get("needs_review"):
            out.append(item)
        if len(out) >= limit:
            break
    return out


async def _reprocess(doc: Dict[str, Any]) -> Dict[str, Any]:
    engine = UnifiedConversionEngine()
    raw = doc.get("raw_content") or doc.get("content") or {}
    source = doc.get("source") or "reprocess"
    result = await engine.convert_document(document={"content": raw}, source=source, filename="reprocess.json", mime_type="application/json", run_snorkel=False)
    return {
        "normalized": result.normalized,
        "metrics": result.metrics,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Reprocess Preciso raw_documents (needs_review or by id)")
    parser.add_argument("--doc-id", action="append", default=[], help="raw_documents id to reprocess (repeatable)")
    parser.add_argument("--needs-review", action="store_true", help="Reprocess documents marked needs_review")
    parser.add_argument("--limit", type=int, default=50, help="Max documents for needs_review mode")
    args = parser.parse_args()

    db = get_db()
    targets: List[Dict[str, Any]] = []
    if args.doc_id:
        for doc_id in args.doc_id:
            doc = _fetch_raw_document(db, doc_id)
            if doc:
                targets.append(doc)
    if args.needs_review:
        targets.extend(_list_needs_review_docs(db, args.limit))

    for doc in targets:
        doc_id = doc.get("id")
        if not doc_id:
            continue
        try:
            update_document_status(db, doc_id, "processing")
            out = await _reprocess(doc)
            update_document_content(db, doc_id, out["normalized"])
            meta = doc.get("metadata") or {}
            meta["reprocessed"] = True
            meta["quality_gate"] = (out.get("metrics") or {}).get("quality_gate")
            update_document_metadata(db, doc_id, meta)
            update_document_status(db, doc_id, "completed")
            print(json.dumps({"doc_id": doc_id, "status": "ok"}))
        except Exception as exc:
            update_document_status(db, doc_id, "failed", error=str(exc))
            print(json.dumps({"doc_id": doc_id, "status": "failed", "error": str(exc)}))


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
