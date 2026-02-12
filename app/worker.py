import logging
import time
import os
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta

from app.core.logging import configure_logging
from app.core.tenant_context import clear_tenant_id, set_tenant_id
from app.api.v1.ingest import (
    get_db,
    get_document_by_id,
    update_document_content,
    update_document_status,
    update_document_metadata,
)
from app.services.task_queue import TaskQueue
from app.services.unified_engine import UnifiedConversionEngine
from app.services.enterprise_collab import EnterpriseCollabStore

logger = logging.getLogger(__name__)


def run_worker_loop() -> None:
    queue = TaskQueue()
    if not queue.enabled():
        raise RuntimeError("TaskQueue disabled: set REDIS_URL to enable worker")

    db = get_db()
    logger.info("DataForge worker started")
    engine = UnifiedConversionEngine()
    collab = EnterpriseCollabStore(db)
    rag_queue_name = os.getenv("DATAFORGE_RAG_QUEUE", "dataforge:rag")
    last_reclaim = 0.0
    lease_seconds = int(os.getenv("DATAFORGE_LEASE_SECONDS", "300"))
    max_retries = int(os.getenv("DATAFORGE_MAX_RETRIES", "3"))

    while True:
        now = time.time()
        if now - last_reclaim > 60:
            _reclaim_stale_jobs(db, queue, lease_seconds)
            last_reclaim = now
        # Prefer interactive RAG tasks when present to avoid UI latency spikes.
        task = queue.dequeue_from(rag_queue_name, timeout=1) or queue.dequeue(timeout=5)
        if not task:
            time.sleep(1)
            continue

        task_type = str(task.get("task_type") or "")
        if task_type == "rag_query":
            _handle_rag_task(db, queue, collab, task)
            continue

        doc_id = task.get("doc_id")
        if not doc_id:
            continue

        doc = get_document_by_id(db, doc_id)
        if not doc:
            continue

        metadata0 = doc.get("metadata", {}) or {}
        tenant_id = str(metadata0.get("tenant_id") or "").strip() or "public"
        set_tenant_id(tenant_id)
        try:
            start = time.time()
            # If this document is tied to a pipeline job that has been canceled, do not process it.
            try:
                pipeline_job_id0 = str(metadata0.get("pipeline_job_id") or "")
                if pipeline_job_id0:
                    j = collab.get_pipeline_job(job_id=pipeline_job_id0) or {}
                    if str(j.get("status") or "") == "canceled":
                        update_document_status(db, doc_id, "canceled", "pipeline job canceled")
                        try:
                            queue.ack(task)
                        except Exception:
                            pass
                        continue
            except Exception:
                pass
            update_document_status(db, doc_id, "processing")
            raw_content = doc.get("raw_content") or {}
            file_bytes = None
            filename = "document"
            if isinstance(raw_content, dict) and raw_content.get("file_path"):
                file_path = raw_content.get("file_path")
                filename = raw_content.get("filename") or os.path.basename(file_path)
                if file_path and os.path.exists(file_path):
                    file_bytes = Path(file_path).read_bytes()
            metadata = metadata0
            # Prefer queue-provided job/user hints (no extra DB lookups), but persist them on the document row.
            changed = False
            if task.get("job_id") and not metadata.get("pipeline_job_id"):
                metadata["pipeline_job_id"] = str(task.get("job_id"))
                changed = True
            if task.get("owner_user_id") and not metadata.get("owner_user_id"):
                metadata["owner_user_id"] = str(task.get("owner_user_id"))
                changed = True
            if changed:
                update_document_metadata(db, doc_id, metadata)
            pipeline_job_id = str(metadata.get("pipeline_job_id") or "")
            actor_user_id = str(metadata.get("owner_user_id") or "system")
            if pipeline_job_id:
                try:
                    collab.update_pipeline_job_status(
                        actor_user_id=actor_user_id,
                        job_id=pipeline_job_id,
                        status="processing",
                        output_ref={"doc_id": doc_id},
                    )
                except Exception:
                    pass
            metadata["lease_until"] = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
            metadata["worker_id"] = os.getenv("HOSTNAME", "worker")
            update_document_metadata(db, doc_id, metadata)
            unified = asyncio.run(engine.convert_document(
                file_bytes=file_bytes,
                filename=filename,
                document={"content": raw_content},
                source=doc.get("source", "upload"),
                run_snorkel=False,
            ))
            processed = unified.normalized or (doc.get("raw_content") or {})
            update_document_content(db, doc_id, processed)
            metadata = doc.get("metadata", {}) or {}
            metadata["unified_summary"] = {
                "fact_count": len(unified.distill.facts),
                "table_count": len((unified.normalized or {}).get("tables", []) or []),
            }
            update_document_metadata(db, doc_id, metadata)
            update_document_status(db, doc_id, "completed")
            if pipeline_job_id:
                try:
                    collab.update_pipeline_job_status(
                        actor_user_id=actor_user_id,
                        job_id=pipeline_job_id,
                        status="completed",
                        output_ref={
                            "doc_id": doc_id,
                            "unified_summary": metadata.get("unified_summary") or {},
                        },
                    )
                except Exception:
                    pass
            # Ack after we have persisted status/content; prevents "processed but not acked".
            try:
                queue.ack(task)
            except Exception:
                logger.warning("queue ack failed", exc_info=True)
            try:
                from app.services.metrics_logger import MetricsLogger
                MetricsLogger().log("worker.job_latency_ms", int((time.time() - start) * 1000), {})
                MetricsLogger().log("worker.job_success", 1, {})
            except Exception:
                logger.warning("metrics logging failed (success)", exc_info=True)
        except Exception as exc:
            logger.exception("Worker failed for %s", doc_id)
            metadata = metadata0
            retries = int(metadata.get("retry_count", 0))
            pipeline_job_id = str(metadata.get("pipeline_job_id") or "")
            actor_user_id = str(metadata.get("owner_user_id") or "system")
            metadata["retry_count"] = retries + 1
            metadata["error_class"] = _classify_error(exc)
            update_document_metadata(db, doc_id, metadata)
            if retries < max_retries:
                update_document_status(db, doc_id, "retrying", str(exc))
                if pipeline_job_id:
                    try:
                        collab.update_pipeline_job_status(
                            actor_user_id=actor_user_id,
                            job_id=pipeline_job_id,
                            status="retrying",
                            error=str(exc),
                            output_ref={"doc_id": doc_id, "retry_count": retries + 1},
                        )
                    except Exception:
                        pass
                time.sleep(min(5 * (retries + 1), 20))
                try:
                    queue.ack(task)
                except Exception:
                    logger.warning("queue ack failed (retry)", exc_info=True)
                queue.enqueue_extract(doc_id)
                update_document_status(db, doc_id, "queued")
            else:
                update_document_status(db, doc_id, "dead_letter", str(exc))
                if pipeline_job_id:
                    try:
                        collab.update_pipeline_job_status(
                            actor_user_id=actor_user_id,
                            job_id=pipeline_job_id,
                            status="dead_letter",
                            error=str(exc),
                            output_ref={"doc_id": doc_id, "retry_count": retries + 1},
                        )
                    except Exception:
                        pass
                try:
                    queue.ack(task)
                except Exception:
                    logger.warning("queue ack failed (dlq)", exc_info=True)
                try:
                    queue.enqueue_dead_letter(
                        doc_id,
                        reason=str(exc),
                        extra={
                            "tenant_id": str(metadata.get("tenant_id") or tenant_id or "public"),
                            "pipeline_job_id": pipeline_job_id or None,
                            "owner_user_id": str(metadata.get("owner_user_id") or actor_user_id or "system"),
                            "error_class": str(metadata.get("error_class") or ""),
                            "retry_count": int(metadata.get("retry_count") or (retries + 1)),
                            "worker_id": os.getenv("HOSTNAME", "worker"),
                        },
                    )
                except Exception:
                    logger.warning("dead letter enqueue failed", exc_info=True)
            try:
                from app.services.metrics_logger import MetricsLogger
                MetricsLogger().log("worker.job_failure", 1, {"retry": retries})
            except Exception:
                logger.warning("metrics logging failed (failure)", exc_info=True)
        finally:
            clear_tenant_id()


if __name__ == "__main__":
    configure_logging("worker")
    run_worker_loop()


def _classify_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "parse" in msg or "json" in msg or "csv" in msg:
        return "parser_error"
    if "timeout" in msg or "connection" in msg or "redis" in msg:
        return "infra_error"
    if "llm" in msg or "model" in msg or "token" in msg:
        return "llm_error"
    if "permission" in msg or "unauthorized" in msg:
        return "auth_error"
    return "unknown_error"


def _reclaim_stale_jobs(db, queue: TaskQueue, lease_seconds: int) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=lease_seconds)
    if hasattr(db, "client"):
        # 1) Reclaim "processing" jobs whose worker lease likely died.
        rows = (
            db.client.table("raw_documents")
            .select("id, processing_status, updated_at")
            .eq("processing_status", "processing")
            .lt("updated_at", cutoff.isoformat())
            .limit(200)
            .execute()
            .data
            or []
        )
        for row in rows:
            doc_id = row.get("id")
            if not doc_id:
                continue
            update_document_status(db, doc_id, "retrying", "lease expired")
            try:
                queue.enqueue_extract(doc_id)
                update_document_status(db, doc_id, "queued")
            except Exception:
                update_document_status(db, doc_id, "dead_letter", "requeue failed")

        # 2) Recover "queued" jobs that are not being processed (e.g., Redis pop loss).
        queued = (
            db.client.table("raw_documents")
            .select("id, processing_status, updated_at")
            .eq("processing_status", "queued")
            .lt("updated_at", cutoff.isoformat())
            .limit(200)
            .execute()
            .data
            or []
        )
        for row in queued:
            doc_id = row.get("id")
            if not doc_id:
                continue
            try:
                queue.enqueue_extract(doc_id)
            except Exception:
                update_document_status(db, doc_id, "dead_letter", "requeue failed (queued recovery)")
    else:
        raw_docs = getattr(db, "raw_documents", {}) or {}
        for doc_id, doc in raw_docs.items():
            if doc.get("processing_status") != "processing":
                continue
            updated_at = doc.get("updated_at")
            if not updated_at:
                continue
            try:
                last = datetime.fromisoformat(updated_at)
            except Exception:
                continue
            if last < cutoff:
                update_document_status(db, doc_id, "retrying", "lease expired")
                try:
                    queue.enqueue_extract(doc_id)
                    update_document_status(db, doc_id, "queued")
                except Exception:
                    update_document_status(db, doc_id, "dead_letter", "requeue failed")

        # Recover "queued" docs that likely missed Redis enqueue.
        for doc_id, doc in raw_docs.items():
            if doc.get("processing_status") != "queued":
                continue
            updated_at = doc.get("updated_at")
            if not updated_at:
                continue
            try:
                last = datetime.fromisoformat(updated_at)
            except Exception:
                continue
            if last < cutoff:
                try:
                    queue.enqueue_extract(doc_id)
                except Exception:
                    update_document_status(db, doc_id, "dead_letter", "requeue failed (queued recovery)")


def _handle_rag_task(db, queue: TaskQueue, collab: EnterpriseCollabStore, task: dict) -> None:
    tenant_id = str(task.get("tenant_id") or "").strip() or "public"
    user_id = str(task.get("user_id") or "system")
    role = str(task.get("role") or "viewer")
    job_id = str(task.get("job_id") or "").strip()
    query = str(task.get("query") or "").strip()
    top_k = int(task.get("top_k") or 5)
    threshold = float(task.get("threshold") or 0.6)
    metadata_filter = task.get("metadata_filter") or {}
    if not isinstance(metadata_filter, dict):
        metadata_filter = {}

    if not job_id or not query:
        try:
            queue.ack(task)
        except Exception:
            pass
        return

    set_tenant_id(tenant_id)
    try:
        # Respect cancellation for async jobs.
        try:
            j = collab.get_pipeline_job(job_id=job_id) or {}
            if str(j.get("status") or "") == "canceled":
                try:
                    queue.ack(task)
                except Exception:
                    pass
                return
        except Exception:
            pass
        try:
            collab.update_pipeline_job_status(
                actor_user_id=user_id,
                job_id=job_id,
                status="processing",
                output_ref={"task": "rag_query"},
            )
        except Exception:
            pass

        from app.services.spoke_c_rag import RAGEngine

        supa = getattr(db, "client", None)
        engine = RAGEngine(
            supabase_client=supa,
            db_client=db,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )
        ctx = engine.retrieve(
            query=query,
            k=top_k,
            threshold=threshold,
            metadata_filter=metadata_filter,
        )
        evidence = [
            {
                "chunk_id": r.chunk_id,
                "content": (r.content or "")[:4000],
                "similarity": r.similarity,
                "metadata": r.metadata,
            }
            for r in (ctx.results or [])
        ]
        legacy_summary = engine.format_context(ctx)
        output_ref = {
            "k": top_k,
            "evidence_count": len(evidence),
            "avg_similarity": float((ctx.metrics or {}).get("avg_similarity", 0) or 0),
            "result": {
                "query": query,
                "evidence": evidence,
                "legacy_summary": legacy_summary,
                "metrics": ctx.metrics,
                "access_level": {"role": role},
            },
        }
        try:
            collab.update_pipeline_job_status(
                actor_user_id=user_id,
                job_id=job_id,
                status="completed",
                output_ref=output_ref,
            )
        except Exception:
            pass
        try:
            queue.ack(task)
        except Exception:
            pass
    except Exception as exc:
        try:
            collab.update_pipeline_job_status(
                actor_user_id=user_id,
                job_id=job_id,
                status="failed",
                error=str(exc),
            )
        except Exception:
            pass
        try:
            queue.ack(task)
        except Exception:
            pass
    finally:
        clear_tenant_id()
