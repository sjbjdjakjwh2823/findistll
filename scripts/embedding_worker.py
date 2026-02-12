#!/usr/bin/env python3
from __future__ import annotations

import os
import time
import logging

from app.db.registry import get_db
from app.services.spoke_c_rag import RAGEngine
from app.services.task_queue import TaskQueue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("embedding_worker")


def _extract_text(raw_content):
    if raw_content is None:
        return ""
    if isinstance(raw_content, dict):
        return raw_content.get("text") or ""
    return str(raw_content)


def main() -> None:
    queue = TaskQueue()
    if not queue.enabled():
        raise SystemExit("Redis not configured. Set REDIS_URL.")
    db = get_db()
    supa = getattr(db, "client", None)
    engine = RAGEngine(supabase_client=supa, db_client=db)
    poll_s = int(os.getenv("EMBED_WORKER_POLL_S", "3"))

    logger.info("Embedding worker started. queue=%s", queue.embed_queue)
    while True:
        job = queue.dequeue(timeout=poll_s)
        if not job:
            continue
        doc_id = job.get("doc_id")
        if not doc_id:
            continue
        try:
            if hasattr(db, "client"):
                res = db.client.table("raw_documents").select("id,raw_content,metadata").eq("id", doc_id).limit(1).execute()
                row = (res.data or [None])[0]
            else:
                raw_docs = getattr(db, "raw_documents", {}) or {}
                row = raw_docs.get(doc_id)
            if not row:
                logger.warning("raw_document not found: %s", doc_id)
                continue
            text = _extract_text(row.get("raw_content"))
            meta = row.get("metadata") or {}
            ingested = engine.ingest_document(text, metadata=meta)
            logger.info("Embedded doc %s (%s chunks)", doc_id, ingested)
        except Exception as exc:
            logger.exception("Embedding job failed: %s", exc)
        time.sleep(0.05)


if __name__ == "__main__":
    main()
