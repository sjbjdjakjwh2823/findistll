from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.core.tenant_context import get_effective_tenant_id
from app.db.registry import get_db
from app.services.spoke_c_rag import RAGEngine
from app.services.metrics_logger import MetricsLogger
from app.services.enterprise_collab import EnterpriseCollabStore, TenantPipelineManager
from app.services.task_queue import TaskQueue
from app.services.feature_flags import get_flag


router = APIRouter(prefix="/rag", tags=["RAG"])


class RagQueryIn(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    metadata_filter: Optional[Dict[str, Any]] = None
    mode: str = Field(default="sync", description="sync|async")


def _role_policy(role: str) -> Dict[str, Any]:
    role = (role or "viewer").lower().strip()
    # Map enterprise roles onto retrieval policy buckets.
    if role in {"approver"}:
        role = "reviewer"
    if role in {"auditor"}:
        role = "analyst"
    default_policy = {
        "viewer": {"max_k": 2, "evidence": False, "causal": False, "prediction": False},
        "analyst": {"max_k": 5, "evidence": True, "causal": True, "prediction": False},
        "reviewer": {"max_k": 8, "evidence": True, "causal": True, "prediction": True},
        "admin": {"max_k": 12, "evidence": True, "causal": True, "prediction": True},
    }
    raw = os.getenv("RAG_ROLE_POLICY_JSON", "")
    if raw:
        try:
            override = json.loads(raw)
            if isinstance(override, dict):
                default_policy.update(override)
        except Exception:
            pass
    return default_policy.get(role, default_policy["viewer"])


def _mask_sensitive(text: str) -> str:
    if not text:
        return text
    masked = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}", "[email]", text)
    masked = re.sub(r"\\b\\d{3}-\\d{2}-\\d{4}\\b", "[ssn]", masked)
    masked = re.sub(r"\\b\\d{13,19}\\b", "[card]", masked)
    masked = re.sub(r"\\bAIza[0-9A-Za-z_-]{30,}\\b", "[api_key]", masked)
    masked = re.sub(r"\\bsk-[0-9A-Za-z]{16,}\\b", "[api_key]", masked)
    return masked


def _build_causal_sections(db: Any, query: str, limit: int = 12) -> Dict[str, Any]:
    try:
        triples = db.search_graph_triples(limit=limit)
    except Exception:
        triples = []

    q = (query or "").lower()
    # Build adjacency to allow 3-hop causal tracing.
    adjacency: Dict[str, List[Dict[str, Any]]] = {}
    for t in triples or []:
        head = str(t.get("head_node", "")).strip()
        tail = str(t.get("tail_node", "")).strip()
        if not head or not tail:
            continue
        adjacency.setdefault(head, []).append(t)

    def _match_triple(t: Dict[str, Any]) -> bool:
        h = str(t.get("head_node", "")).lower()
        r = str(t.get("relation", "")).lower()
        tail = str(t.get("tail_node", "")).lower()
        if not q:
            return True
        return q in h or q in tail or q in r

    seeds = [t for t in (triples or []) if _match_triple(t)]
    if not seeds:
        seeds = (triples or [])[: min(3, len(triples or []))]

    paths: List[List[Dict[str, Any]]] = []
    for seed in seeds[: min(len(seeds), limit)]:
        head = str(seed.get("head_node", "")).strip()
        if not head:
            continue
        # 1 hop
        paths.append([seed])
        # 2 hop
        for t2 in adjacency.get(str(seed.get("tail_node", "")).strip(), [])[:3]:
            paths.append([seed, t2])
            # 3 hop
            for t3 in adjacency.get(str(t2.get("tail_node", "")).strip(), [])[:2]:
                paths.append([seed, t2, t3])

    cause_chain: List[str] = []
    effect_chain: List[str] = []
    for path in paths[: min(len(paths), 8)]:
        segments = []
        for step in path:
            head = str(step.get("head_node", ""))
            rel = str(step.get("relation", "affects"))
            tail = str(step.get("tail_node", ""))
            weight = ""
            props = step.get("properties") if isinstance(step.get("properties"), dict) else {}
            if props and props.get("weight"):
                weight = f" (w={props.get('weight')})"
            segments.append(f"{head} --[{rel}]--> {tail}{weight}")
        if segments:
            chain = " | ".join(segments)
            cause_chain.append(chain)
            effect_chain.append(str(path[-1].get("tail_node", "")))

    prediction = None
    if cause_chain:
        prediction = {
            "horizon": "near_term",
            "statement": f"If current drivers persist, likely effect: {effect_chain[0]}",
            "confidence": 0.62,
        }

    return {
        "cause_chain": cause_chain[:5],
        "effect_chain": effect_chain[:5],
        "prediction": prediction,
    }


@router.post("/query")
def rag_query(payload: RagQueryIn, user: CurrentUser = Depends(get_current_user)):
    mode = (payload.mode or "sync").strip().lower()
    policy = _role_policy(user.role)
    enforce_owner = (user.role or "").lower() in {"viewer", "analyst"}
    metadata_filter = payload.metadata_filter or {}
    if enforce_owner and "owner_user_id" not in metadata_filter:
        metadata_filter["owner_user_id"] = user.user_id
    k = min(payload.top_k, int(policy.get("max_k", payload.top_k)))
    db = get_db()
    job_id: Optional[str] = None
    store: Optional[EnterpriseCollabStore] = None
    allowed_doc_ids: Optional[set[str]] = None
    try:
        store = EnterpriseCollabStore(db)
        files = store.list_files(user_id=user.user_id, role=user.role, limit=500)
        allowed = {str(f.get("doc_id") or "") for f in files if f.get("doc_id")}
        allowed = {d for d in allowed if d}
        allowed_doc_ids = allowed
        # Always override caller-provided doc_ids to avoid scope escalation (async path cannot re-check ACL).
        metadata_filter["doc_ids"] = sorted(list(allowed_doc_ids))[:500]
    except Exception:
        allowed_doc_ids = None
        # Safety fallback: if ACL store is unavailable, force owner scoping for non-admin.
        if (user.role or "").lower() != "admin":
            metadata_filter["owner_user_id"] = user.user_id

    # Observability + quota: register a tenant-shared pipeline job for this RAG query.
    # This remains synchronous (no queue yet), but makes UI/ops logs consistent.
    if user.user_id and user.user_id != "anonymous":
        try:
            manager = TenantPipelineManager(db)
            input_ref = {
                "query": payload.query[:2000],
                "top_k": k,
                "threshold": payload.threshold,
                "doc_scope_count": len(allowed_doc_ids or []),
                "mode": mode,
                "metadata_filter": metadata_filter,
                "role": user.role,
            }
            job = manager.submit(
                user_id=user.user_id,
                job_type="rag",
                flow="interactive",
                input_ref=input_ref,
            )
            job_id = str(job.get("id") or "")
            if job_id and store is not None and mode != "async":
                store.update_pipeline_job_status(
                    actor_user_id=user.user_id,
                    job_id=job_id,
                    status="processing",
                    output_ref={},
                )
        except PermissionError as exc:
            raise HTTPException(status_code=429, detail=str(exc))
        except Exception:
            job_id = None

    if mode == "async":
        if not get_flag("rag_async_enabled"):
            raise HTTPException(status_code=400, detail="async mode disabled (set RAG_ASYNC_ENABLED=1)")
        if not job_id or not store:
            raise HTTPException(status_code=500, detail="failed to allocate pipeline job for async request")
        queue = TaskQueue()
        if not queue.enabled():
            try:
                store.update_pipeline_job_status(
                    actor_user_id=user.user_id,
                    job_id=job_id,
                    status="failed",
                    error="TaskQueue disabled: set REDIS_URL to enable async RAG",
                )
            except Exception:
                pass
            raise HTTPException(
                status_code=503,
                detail={"job_id": job_id, "error": "TaskQueue disabled: set REDIS_URL to enable async RAG"},
            )
        tenant_id = get_effective_tenant_id()
        try:
            # Mark as queued (pending) after enqueue; worker will transition to processing.
            try:
                store.update_pipeline_job_status(
                    actor_user_id=user.user_id,
                    job_id=job_id,
                    status="pending",
                    output_ref={"mode": "async", "queued": True},
                )
            except Exception:
                pass
            queue.enqueue_rag_query(
                job_id=job_id,
                tenant_id=tenant_id,
                user_id=user.user_id,
                role=user.role,
                query=payload.query[:8000],
                top_k=k,
                threshold=payload.threshold,
                metadata_filter=metadata_filter,
            )
        except Exception as exc:
            try:
                store.update_pipeline_job_status(
                    actor_user_id=user.user_id,
                    job_id=job_id,
                    status="failed",
                    error=str(exc),
                )
            except Exception:
                pass
            raise HTTPException(status_code=500, detail={"job_id": job_id, "error": str(exc)})
        return {
            "job_id": job_id,
            "status": "pending",
            "mode": "async",
        }

    supa = getattr(db, "client", None)
    engine = RAGEngine(
        supabase_client=supa,
        db_client=db,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )
    try:
        context = engine.retrieve(
            query=payload.query,
            k=k,
            threshold=payload.threshold,
            metadata_filter=metadata_filter,
        )
        # Hard filter results to avoid cross-user leakage even if RPC filtering is not deployed.
        if allowed_doc_ids is not None:
            context.results = [
                r
                for r in context.results
                if str((r.metadata or {}).get("doc_id") or (r.metadata or {}).get("document_id") or "") in allowed_doc_ids
            ]
        evidence = [
            {
                "chunk_id": r.chunk_id,
                "content": r.content,
                "similarity": r.similarity,
                "metadata": r.metadata,
            }
            for r in context.results
        ]
        if os.getenv("RAG_PII_MASK_ENABLED", "1") == "1" and (user.role or "").lower() not in {"admin"}:
            for ev in evidence:
                if isinstance(ev.get("content"), str):
                    ev["content"] = _mask_sensitive(ev["content"])
        delta_source_version = None
        for ev in evidence:
            md = ev.get("metadata") or {}
            delta_source_version = md.get("delta_source_version") or md.get("delta_version")
            if delta_source_version:
                break
        causal = _build_causal_sections(db=db, query=payload.query) if policy.get("causal") else {}
        legacy_summary = engine.format_context(context)

        try:
            MetricsLogger().log(
                "rag.query.count",
                1,
                {
                    "k": payload.top_k,
                    "user_id": user.user_id,
                    "has_prediction": 1 if causal.get("prediction") else 0,
                },
            )
        except Exception:
            # Metrics must never break the RAG user path.
            pass

        response = {
            "query": payload.query,
            "evidence": evidence if policy.get("evidence") else [],
            "cause_chain": causal.get("cause_chain") or [],
            "effect_chain": causal.get("effect_chain") or [],
            "prediction": causal.get("prediction") if policy.get("prediction") else None,
            "delta_source_version": delta_source_version,
            "legacy_summary": legacy_summary,
            "metrics": context.metrics,
            "job_id": job_id,
            "access_level": {
                "role": user.role,
                "max_k": int(policy.get("max_k", k)),
                "evidence": bool(policy.get("evidence")),
                "causal": bool(policy.get("causal")),
                "prediction": bool(policy.get("prediction")),
            },
            "ownership_enforced": enforce_owner,
        }
        if job_id and store is not None:
            try:
                store.update_pipeline_job_status(
                    actor_user_id=user.user_id,
                    job_id=job_id,
                    status="completed",
                    output_ref={
                        "k": k,
                        "evidence_count": len(evidence),
                        "avg_similarity": float(context.metrics.get("avg_similarity", 0) or 0),
                    },
                )
            except Exception:
                pass
        return response
    except Exception as exc:
        if job_id and store is not None:
            try:
                store.update_pipeline_job_status(
                    actor_user_id=user.user_id,
                    job_id=job_id,
                    status="failed",
                    error=str(exc),
                )
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=str(exc))
