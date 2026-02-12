from fastapi import APIRouter, HTTPException, Depends
import os
import json
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.core.auth import get_current_user
from app.db.registry import get_db
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_trust import (
    AuditEventLogger,
    StructuredChunker,
    build_human_diff,
    build_selfcheck_runs,
)
from app.services.types import DecisionResult
from app.services.spoke_ab_service import SpokeABService
from app.core.tenant_context import get_effective_tenant_id
from app.services.spokes import build_rag_context, extract_graph_triples
from app.services.spoke_c_rag import RAGEngine
from app.services.metrics_logger import MetricsLogger
from app.services.training_service import enqueue_training_run, get_auto_train_enabled
from app.services.mlflow_service import MlflowService

router = APIRouter(prefix='/approvals', tags=['approvals'])


def _require_reviewer_role(role: str) -> None:
    r = (role or "viewer").lower().strip()
    if r in {"approver"}:
        r = "reviewer"
    allowed = {"reviewer", "admin"}
    if r not in allowed:
        raise HTTPException(status_code=403, detail="reviewer/admin role required")


class ApprovalRequest(BaseModel):
    decision: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None
    confidence_score: Optional[float] = None
    selfcheck_runs: Optional[Dict[str, Any]] = None


@router.post('/cases/{case_id}/approve')
async def approve_case(case_id: str, payload: ApprovalRequest, current_user = Depends(get_current_user)):
    _require_reviewer_role(getattr(current_user, "role", "viewer"))
    db = get_db()
    case = db.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail='case not found')
    case_uuid = case.get("id") or case_id

    ai_recommendation = case.get('decision') or case.get('ai_recommendation') or {}
    human_diff = build_human_diff(ai_recommendation, payload.decision or {})
    # Allow approve-as-is: reviewers may accept the AI recommendation without edits.
    # We still log the event to keep the audit trail explicit.
    if not human_diff.get("diffs"):
        AuditEventLogger().log(
            "HUMAN_APPROVED_AS_IS",
            case_id=str(case_uuid),
            metadata={"reason": "No diff between AI and human decision"},
        )

    distill_raw = case.get('distill')
    distill = None
    if isinstance(distill_raw, dict):
        from app.services.types import DistillResult as _DistillResult
        distill = _DistillResult(
            facts=distill_raw.get("facts") or [],
            cot_markdown=distill_raw.get("cot_markdown") or "",
            metadata=distill_raw.get("metadata") or {},
        )
    else:
        distill = distill_raw
    confidence_score = payload.confidence_score
    selfcheck_runs = payload.selfcheck_runs
    if distill and confidence_score is None:
        try:
            decision_obj = DecisionResult(
                decision=str((payload.decision or {}).get("decision", "approved")),
                rationale=payload.reasoning or (payload.decision or {}).get("rationale", ""),
                actions=(payload.decision or {}).get("actions", []) or [],
                approvals=(payload.decision or {}).get("approvals", []) or [],
            )
            selfcheck_runs = build_selfcheck_runs(decision_obj, distill)
            confidence_score = selfcheck_runs.get("summary", {}).get("confidence_score")
        except Exception:
            confidence_score = confidence_score or 0.0

    if confidence_score is not None and confidence_score < 0.7:
        db.update_case_status(case_id, 'needs_review', {
            'needs_review': True,
            'confidence_score': confidence_score,
            'selfcheck_runs': selfcheck_runs or {},
            'human_diff': human_diff,
        })
        AuditEventLogger().log(
            "LOW_CONFIDENCE_DETECTED",
            case_id=str(case_uuid),
            metadata={"confidence_score": confidence_score},
        )
        raise HTTPException(status_code=409, detail='low confidence - human review required')

    db.update_case_status(case_id, 'approved', {
        'approved_by': current_user.user_id,
        'approved_at': 'now',
        'approval_reasoning': payload.reasoning,
        'final_decision': payload.decision,
        'confidence_score': confidence_score,
        'selfcheck_runs': selfcheck_runs or {},
        'needs_review': False,
        'human_diff': human_diff,
    })
    AuditEventLogger().log(
        "MLFLOW_RUN_CANDIDATE",
        case_id=str(case_uuid),
        metadata={
            "mlflow_run_candidate": True,
            "dataset_version_hint": datetime.now(timezone.utc).strftime("dataset-%Y-%m-%d"),
            "approved_by": current_user.user_id,
        },
    )

    sections = []
    if distill:
        chunker = StructuredChunker()
        sections.extend(chunker.chunk_distill(distill))
    if payload.decision or payload.reasoning:
        chunker = StructuredChunker()
        sections.extend(chunker.chunk_decision(payload.decision or {}, payload.reasoning or ""))
    if sections:
        doc_id_hint = None
        try:
            if distill and getattr(distill, "metadata", None):
                doc_id_hint = (distill.metadata or {}).get("doc_id") or (distill.metadata or {}).get("document_id")
        except Exception:
            doc_id_hint = None
        doc_id_hint = doc_id_hint or case_id
        EmbeddingService(db).embed_case_sections(
            str(case_uuid),
            sections,
            metadata={
                'approval_status': 'approved',
                'approved_at': 'now',
                'approved_by': current_user.user_id,
                'tenant_id': get_effective_tenant_id(),
                'doc_id': doc_id_hint,
            },
        )
        AuditEventLogger().log(
            "APPROVED_INDEXED",
            case_id=str(case_uuid),
            metadata={"section_count": len(sections)},
        )
    AuditEventLogger().log(
        "HUMAN_OVERRIDE",
        case_id=str(case_uuid),
        metadata={"diffs": human_diff.get("diffs", [])},
    )

    # ---------------------------------------------------------------------
    # WS8: Spoke A/B downstream artifacts
    # - Generate Spoke A SFT JSONL record only on approval events.
    # - Generate Spoke B artifacts (facts/tables/features) for downstream quant + grounding.
    # If any failure occurs here, do NOT fail the approval; log and continue.
    # ---------------------------------------------------------------------
    try:
        service = SpokeABService()
        tenant_id = get_effective_tenant_id()
        doc_id = (distill.metadata or {}).get("doc_id") if distill else None
        doc_id = doc_id or case_id

        # Spoke A inputs/outputs
        instruction = "Generate an audit-grade financial risk summary grounded in extracted facts and evidence."
        fact_preview = "\n".join([str(f) for f in (distill.facts or [])[:30]]) if distill else ""
        input_text = f"Case: {case_id}\n\nFacts:\n{fact_preview}\n\nCoT:\n{(distill.cot_markdown or '')[:4000] if distill else ''}"
        if distill:
            math_summary = service.build_math_summary(distill)
            if math_summary:
                input_text = input_text + "\n\n" + math_summary
        output_text = json.dumps(payload.decision or {}, ensure_ascii=False) + "\n" + (payload.reasoning or "")

        evidence_chunk_ids = [f"{case_id}:{s.get('chunk_id')}" for s in sections if s.get("chunk_id")]
        fact_refs = service.build_fact_refs(distill, limit=80) if distill else []

        decision_obj = DecisionResult(
            decision=str((payload.decision or {}).get("decision", "approved")),
            rationale=payload.reasoning or (payload.decision or {}).get("rationale", ""),
            actions=(payload.decision or {}).get("actions", []) or [],
            approvals=(payload.decision or {}).get("approvals", []) or [],
        )
        selfcheck_payload = selfcheck_runs or {}
        if distill and not selfcheck_payload:
            selfcheck_payload = service.compute_selfcheck(decision=decision_obj, distill=distill)

        ds = db.get_or_create_active_dataset_version(
            name_hint=datetime.now(timezone.utc).strftime("dataset-%Y-%m-%d")
        )
        version = ds.get("name") or "active"
        approval_meta = {
            "approved_by": current_user.user_id,
            "approved_at": "now()",
            "edit_distance": len(human_diff.get("diffs") or []),
            "source": (distill.metadata or {}).get("source") if distill else "preciso",
            "human_diff": human_diff,
        }
        spoke_a = service.build_spoke_a_record(
            tenant_id=tenant_id,
            doc_id=str(doc_id),
            case_id=case_id,
            version=str(version),
            instruction=instruction,
            input_text=input_text,
            output_text=output_text,
            evidence_chunk_ids=evidence_chunk_ids,
            fact_refs=fact_refs,
            selfcheck=selfcheck_payload,
            approval=approval_meta,
        )

        gates = service.evaluate_gates(spoke_a_record=spoke_a, distill=distill) if distill else None
        db.insert_spoke_a_sample(
            {
                "dataset_version_id": ds.get("id"),
                "case_id": case_id,
                "doc_id": str(doc_id),
                "sample_json": spoke_a,
                "jsonl_line": json.dumps(spoke_a, ensure_ascii=False),
                "gates": gates.details if gates else {},
                "status": gates.status if gates else "needs_review",
            }
        )

        # MLflow linkage: each approval candidate creates a tracked run bound to dataset_version.
        try:
            MlflowService(db).start_run(
                dataset_version_id=str(ds.get("id")) if ds.get("id") else None,
                model_name=os.getenv("TRAINING_MODEL_NAME", "preciso-fin"),
                params={
                    "case_id": case_id,
                    "gate_status": gates.status if gates else "needs_review",
                },
                metrics={
                    "faithfulness": float(((selfcheck_payload or {}).get("summary", {}) or {}).get("faithfulness", 0.0) or 0.0),
                    "numeric_consistency": float(((selfcheck_payload or {}).get("summary", {}) or {}).get("numeric_consistency", 0.0) or 0.0),
                    "confidence_score": float((selfcheck_payload or {}).get("summary", {}).get("confidence_score", 0.0) or 0.0),
                },
                artifacts={"sample_key": spoke_a.get("id")},
                requested_by=current_user.user_id,
            )
        except Exception as exc:
            AuditEventLogger().log(
                "MLFLOW_LINK_FAILED",
                case_id=str(case_uuid),
                metadata={"error": str(exc)},
            )

        auto_train = get_auto_train_enabled()
        if auto_train and gates and gates.status == "candidate":
            enqueue_training_run(
                dataset_version_id=str(ds.get("id")),
                model_name=os.getenv("TRAINING_MODEL_NAME", "preciso-fin"),
                triggered_by=current_user.user_id,
                auto=True,
                notes="auto: approval gate candidate",
            )

        if distill:
            artifacts = service.build_spoke_b_parquets(
                tenant_id=tenant_id,
                doc_id=str(doc_id),
                distill=distill,
                normalized=(distill.metadata or {}).get("normalized"),  # optional
            )
            service.save_spoke_b_artifacts(
                db=db,
                doc_id=str(doc_id),
                artifacts=artifacts,
                metadata={"case_id": case_id},
            )
    except Exception as exc:
        AuditEventLogger().log(
            "WS8_SPOKE_AB_FAILED",
            case_id=str(case_uuid),
            metadata={"error": str(exc)},
        )

    # ---------------------------------------------------------------------
    # Continuous Learning Loop: Spoke C + Spoke D updates on approval
    # ---------------------------------------------------------------------
    try:
        if distill:
            rag_contexts = build_rag_context(distill, case_id=str(case_uuid))
            if rag_contexts:
                db.save_rag_context(str(case_uuid), rag_contexts)
                rag_text = "\n\n".join([ctx.get("text_content") or "" for ctx in rag_contexts if ctx.get("text_content")])
                # InMemoryDB does not expose a Supabase client; skip vector ingestion in that mode.
                supa_client = getattr(db, "client", None)
                if supa_client:
                    rag_engine = RAGEngine(supabase_client=supa_client)
                    ingested = rag_engine.ingest_document(
                        rag_text,
                        metadata={
                            "case_id": str(case_uuid),
                            "doc_id": str(doc_id),
                            "source": (distill.metadata or {}).get("source"),
                        },
                    )
                    MetricsLogger().log("spoke_c.ingested_chunks", ingested, {"case_id": str(case_uuid)})

            graph_triples = extract_graph_triples(distill)
            if graph_triples:
                db.save_graph_triples(str(case_uuid), graph_triples)
                MetricsLogger().log("spoke_d.triples", len(graph_triples), {"case_id": str(case_uuid)})
    except Exception as exc:
        AuditEventLogger().log(
            "WS8_SPOKE_CD_FAILED",
            case_id=str(case_uuid),
            metadata={"error": str(exc)},
        )

    return {'status': 'approved'}


@router.post('/cases/{case_id}/reject')
async def reject_case(case_id: str, payload: ApprovalRequest, current_user = Depends(get_current_user)):
    _require_reviewer_role(getattr(current_user, "role", "viewer"))
    db = get_db()
    case = db.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail='case not found')
    db.update_case_status(case_id, 'rejected', {
        'rejected_by': current_user.user_id,
        'rejected_at': 'now',
        'rejection_reasoning': payload.reasoning,
    })
    return {'status': 'rejected'}


@router.post('/cases/{case_id}/request-changes')
async def request_changes(case_id: str, payload: ApprovalRequest, current_user = Depends(get_current_user)):
    _require_reviewer_role(getattr(current_user, "role", "viewer"))
    db = get_db()
    case = db.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail='case not found')
    db.update_case_status(case_id, 'changes_requested', {
        'requested_by': current_user.user_id,
        'requested_at': 'now',
        'request_reasoning': payload.reasoning,
    })
    return {'status': 'changes_requested'}
