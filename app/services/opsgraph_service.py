"""
OpsGraph Service - Phase 3
Case management, dynamic ontology, and audit trail.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.config import load_settings
from app.db.supabase_db import SupabaseDB
from app.db.registry import get_db as get_registry_db
from app.services.decision_state_machine import DecisionStateMachine, TransitionData
from app.services.active_learning import ActiveLearningPrioritizer
from app.services.knowledge_graph import KnowledgeGraphBuilder, OntologyBuilder
from app.services.graph_reasoning import GraphReasoningService

logger = logging.getLogger(__name__)


class OpsGraphService:
    def __init__(self) -> None:
        self._db, self._mode = self._init_db()

    def _init_db(self) -> tuple[Any, str]:
        settings = load_settings()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            # Dev/test fallback: run OpsGraph against the global DB (often InMemoryDB).
            return (get_registry_db(), "inmemory")
        return (SupabaseDB(settings.supabase_url, settings.supabase_service_role_key), "supabase")

    @property
    def client(self):
        if self._mode != "supabase":
            raise RuntimeError("Supabase client not available in in-memory mode")
        return self._db.client

    # ---------------------------------------------------------------------
    # Entities (Dynamic Ontology)
    # ---------------------------------------------------------------------
    def create_entity(
        self,
        entity_type: str,
        name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        if self._mode != "supabase":
            store = getattr(self._db, "ops_entities", None)
            if store is None:
                store = {}
                setattr(self._db, "ops_entities", store)
            entity_id = str(uuid4())
            store[entity_id] = {
                "id": entity_id,
                "entity_type": entity_type,
                "name": name,
                "properties": properties or {},
            }
            return entity_id

        entity_id = str(uuid4())
        payload = {
            "id": entity_id,
            "entity_type": entity_type,
            "name": name,
            "properties": properties or {},
        }
        self.client.table("ops_entities").insert(payload).execute()
        return entity_id

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        if self._mode != "supabase":
            store = getattr(self._db, "ops_entities", {}) or {}
            return store.get(entity_id)
        res = self.client.table("ops_entities").select("*").eq("id", entity_id).execute()
        return res.data[0] if res.data else None

    def link_entities(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None,
        confidence: float = 0.5,
    ) -> str:
        if self._mode != "supabase":
            rels = getattr(self._db, "ops_relationships", None)
            if rels is None:
                rels = {}
                setattr(self._db, "ops_relationships", rels)
            rel_id = str(uuid4())
            rels[rel_id] = {
                "id": rel_id,
                "source_id": source_id,
                "target_id": target_id,
                "relationship_type": relationship_type,
                "properties": properties or {},
                "confidence": confidence,
            }
            return rel_id

        rel_id = str(uuid4())
        payload = {
            "id": rel_id,
            "source_id": source_id,
            "target_id": target_id,
            "relationship_type": relationship_type,
            "properties": properties or {},
            "confidence": confidence,
        }
        self.client.table("ops_relationships").insert(payload).execute()
        return rel_id

    def get_entity_graph(self, entity_id: str) -> Dict[str, Any]:
        if self._mode != "supabase":
            store_nodes = getattr(self._db, "ops_entities", {}) or {}
            store_rels = getattr(self._db, "ops_relationships", {}) or {}
            relationships = [
                r
                for r in store_rels.values()
                if r.get("source_id") == entity_id or r.get("target_id") == entity_id
            ]
            node_ids = {entity_id}
            for rel in relationships:
                node_ids.add(rel.get("source_id"))
                node_ids.add(rel.get("target_id"))
            nodes = [store_nodes[n] for n in node_ids if n in store_nodes]
            return {"nodes": nodes, "relationships": relationships}

        rels = (
            self.client.table("ops_relationships")
            .select("*")
            .or_(f"source_id.eq.{entity_id},target_id.eq.{entity_id}")
            .execute()
        )
        relationships = rels.data or []

        node_ids = {entity_id}
        for rel in relationships:
            node_ids.add(rel.get("source_id"))
            node_ids.add(rel.get("target_id"))

        if node_ids:
            nodes = (
                self.client.table("ops_entities")
                .select("*")
                .in_("id", list(node_ids))
                .execute()
            ).data or []
        else:
            nodes = []

        return {"nodes": nodes, "relationships": relationships}

    # ---------------------------------------------------------------------
    # Cases
    # ---------------------------------------------------------------------
    def create_case(
        self,
        title: str,
        entity_id: Optional[str],
        priority: str,
        ai_recommendation: Optional[Dict[str, Any]] = None,
    ) -> str:
        if self._mode != "supabase":
            # Use DBClient case store.
            case_id = self._db.create_case({"title": title})
            self.log_audit(
                action="case_created",
                actor_type="system",
                actor_id="opsgraph",
                context={"case_id": case_id, "title": title},
                outcome={"status": "open"},
            )
            return case_id

        case_id = str(uuid4())
        payload = {
            "id": case_id,
            "title": title,
            "status": "open",
            "priority": priority,
            "entity_id": entity_id,
            "ai_recommendation": ai_recommendation or {},
            "human_decision": {},
        }
        self.client.table("ops_cases").insert(payload).execute()
        self.log_audit(
            action="case_created",
            actor_type="system",
            actor_id="opsgraph",
            context={"case_id": case_id, "title": title},
            outcome={"status": "open"},
        )
        return case_id

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        if self._mode != "supabase":
            return self._db.get_case(case_id) or None
        res = self.client.table("ops_cases").select("*").eq("id", case_id).execute()
        return res.data[0] if res.data else None

    def list_cases(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if self._mode != "supabase":
            cases = self._db.list_cases() or []
            if status:
                cases = [c for c in cases if c.get("status") == status]
            return cases[:limit]
        query = self.client.table("ops_cases").select("*")
        if status:
            query = query.eq("status", status)
        res = query.order("created_at", desc=True).limit(limit).execute()
        return res.data or []

    def list_prioritized_cases(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if self._mode != "supabase":
            # No selfcheck_samples table in InMemory mode; return ordered list.
            return self.list_cases(status=status, limit=limit)
        cases = self.list_cases(status=status, limit=limit)
        case_ids = [c.get("id") for c in cases if c.get("id")]
        selfcheck_map: Dict[str, Dict[str, Any]] = {}
        if case_ids:
            rows = (
                self.client.table("selfcheck_samples")
                .select("case_id,consistency_score,confidence_level,created_at")
                .in_("case_id", case_ids)
                .order("created_at", desc=True)
                .execute()
            ).data or []
            for row in rows:
                if row.get("case_id") not in selfcheck_map:
                    selfcheck_map[row.get("case_id")] = row

        enriched = []
        for case in cases:
            check = selfcheck_map.get(case.get("id"), {})
            enriched.append(
                {
                    **case,
                    "consistency_score": check.get("consistency_score", 0.5),
                    "confidence_level": check.get("confidence_level", "Unknown"),
                }
            )

        prioritizer = ActiveLearningPrioritizer()
        return prioritizer.prioritize(enriched)

    def build_knowledge_graph(self) -> Dict[str, int]:
        if self._mode != "supabase":
            return {"nodes": 0, "relationships": 0}
        builder = KnowledgeGraphBuilder(self.client)
        return builder.build()

    def predict_entity_risk(self, entity_id: str) -> Dict[str, Any]:
        if self._mode != "supabase":
            return {"entity_id": entity_id, "risk_score": 0.5, "status": "unavailable_in_memory"}
        reasoner = GraphReasoningService(self.client)
        return reasoner.predict_risk(entity_id)

    def build_ontology(self) -> Dict[str, int]:
        if self._mode != "supabase":
            return {"entity_types": 0, "relationship_types": 0}
        builder = OntologyBuilder(self.client)
        return builder.build()


    def list_audit_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        if self._mode != "supabase":
            return self._db.list_audit_logs(limit=limit)
        res = self.client.table("ops_audit_logs").select("*").order("created_at", desc=True).limit(limit).execute()
        return res.data or []

    def transition_case(
        self,
        case_id: str,
        target_status: str,
        user_id: str,
        user_role: str,
        reason: Optional[str] = None,
        evidence_reviewed: Optional[List[str]] = None,
        revision_requests: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        case = self.get_case(case_id)
        if not case:
            raise ValueError("case not found")

        current_status = case.get("status", "draft")
        if target_status in ("approved", "rejected", "revision_requested"):
            if not reason:
                raise ValueError("reason is required for audit-grade transitions")
            if not evidence_reviewed:
                raise ValueError("evidence_reviewed is required for audit-grade transitions")
        data = TransitionData(
            user_id=user_id,
            user_role=user_role,
            reason=reason,
            evidence_reviewed=evidence_reviewed,
            revision_requests=revision_requests,
            assigned_approver_id=case.get("assigned_approver_id"),
        )
        DecisionStateMachine.transition(current_status, target_status, data)

        if self._mode != "supabase":
            fields: Dict[str, Any] = {}
            if reason:
                fields["decision_reason"] = reason
            if revision_requests:
                fields["revision_requests"] = revision_requests
            fields["evidence_reviewed"] = evidence_reviewed or []
            self._db.update_case_status(case_id, target_status, fields)
        else:
            payload = {"status": target_status}
            if reason:
                payload["decision_reason"] = reason
            if revision_requests:
                payload["revision_requests"] = revision_requests
            self.client.table("ops_cases").update(payload).eq("id", case_id).execute()

            self.client.table("ops_case_state_history").insert({
                "case_id": case_id,
                "from_status": current_status,
                "to_status": target_status,
                "user_id": user_id,
                "user_role": user_role,
                "reason": reason,
                "evidence_reviewed": evidence_reviewed or [],
                "revision_requests": revision_requests or [],
                "review_metadata": {
                    "audit_grade": True,
                    "timestamp": time.time(),
                },
            }).execute()

        self.log_audit(
            action="state_transition",
            actor_type="human",
            actor_id=user_id,
            context={"case_id": case_id, "from": current_status, "to": target_status},
            outcome={"success": True},
        )
        return {"case_id": case_id, "status": target_status}

    def resolve_case(
        self,
        case_id: str,
        decision: Dict[str, Any],
        agreed_with_ai: bool,
        human_reasoning: Optional[str] = None,
    ) -> None:
        if not human_reasoning:
            raise ValueError("human_reasoning is required for audit-grade resolution")
        if self._mode != "supabase":
            self._db.update_case_status(
                case_id,
                "resolved",
                {
                    "human_decision": {"decision": decision, "reasoning": human_reasoning, "agreed_with_ai": agreed_with_ai},
                },
            )
        else:
            payload = {
                "human_decision": {
                    "decision": decision,
                    "reasoning": human_reasoning,
                    "agreed_with_ai": agreed_with_ai,
                },
                "status": "resolved",
            }
            self.client.table("ops_cases").update(payload).eq("id", case_id).execute()

        self.log_audit(
            action="case_resolved",
            actor_type="human",
            actor_id=decision.get("actor_id", "unknown"),
            context={"case_id": case_id},
            outcome={"agreed_with_ai": agreed_with_ai},
        )

        if not agreed_with_ai:
            self._create_correction_sample(case_id, decision, human_reasoning)

    # ---------------------------------------------------------------------
    # Feedback loop into DataForge
    # ---------------------------------------------------------------------
    def _create_correction_sample(
        self,
        case_id: str,
        decision: Dict[str, Any],
        human_reasoning: Optional[str],
    ) -> None:
        if self._mode != "supabase":
            return
        try:
            case = self.get_case(case_id) or {}
            ai_recommendation = case.get("ai_recommendation", {})

            raw_doc_payload = {
                "source": "opsgraph_feedback",
                "ticker": decision.get("ticker"),
                "document_type": "decision_correction",
                "raw_content": {
                    "case_id": case_id,
                    "ai_recommendation": ai_recommendation,
                    "human_decision": decision,
                    "human_reasoning": human_reasoning,
                },
            }

            raw_doc_res = self.client.table("raw_documents").insert(raw_doc_payload).execute()
            raw_document_id = raw_doc_res.data[0]["id"] if raw_doc_res.data else None

            if not raw_document_id:
                logger.warning("Failed to create raw_document for correction sample")
                return

            sample_payload = {
                "raw_document_id": raw_document_id,
                "template_type": "correction_sample",
                "generated_content": {
                    "ai_recommendation": ai_recommendation,
                    "human_decision": decision,
                    "human_reasoning": human_reasoning,
                },
                "model_used": "human",
                "review_status": "pending",
                "confidence_score": None,
            }
            self.client.table("generated_samples").insert(sample_payload).execute()
        except Exception as exc:
            logger.warning(f"Failed to create correction sample: {exc}")

    # ---------------------------------------------------------------------
    # Audit Trail
    # ---------------------------------------------------------------------
    def log_audit(
        self,
        action: str,
        actor_type: str,
        actor_id: str,
        context: Dict[str, Any],
        outcome: Dict[str, Any],
    ) -> None:
        payload = {
            "id": str(uuid4()),
            "action": action,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "context": context,
            "outcome": outcome,
        }
        if self._mode != "supabase":
            # Reuse the global audit log storage.
            self._db.append_audit_log({**payload, "timestamp": _now_iso()})
            return
        self.client.table("ops_audit_logs").insert(payload).execute()


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
