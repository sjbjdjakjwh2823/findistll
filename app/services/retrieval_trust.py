from __future__ import annotations

import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4
from uuid import UUID

from app.core.config import load_settings
from app.core.tenant_context import get_effective_tenant_id
from app.db.supabase_rest_client import create_client as create_supabase_rest_client
from app.db.tenant_scoped_client import create_tenant_aware_client
from app.services.embedding_service import EmbeddingService
from app.services.evidence_diff import diff_decisions
from app.services.types import DistillResult, DecisionResult

logger = logging.getLogger(__name__)


class StructuredChunker:
    def chunk_distill(self, distill: DistillResult) -> List[Dict[str, Any]]:
        sections: List[Dict[str, Any]] = []

        facts = distill.facts or []
        for idx, fact in enumerate(facts):
            sections.append(
                {
                    "chunk_type": "fact",
                    "chunk_id": f"fact_{idx+1}",
                    "content": self._stringify_fact(fact),
                }
            )

        cot = distill.cot_markdown or ""
        if cot.strip():
            sections.extend(self._chunk_cot(cot))

        return sections

    def chunk_decision(
        self,
        decision: Dict[str, Any],
        reasoning: str,
        agreed_with_ai: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        summary = {
            "decision": decision,
            "reasoning": reasoning,
            "agreed_with_ai": agreed_with_ai,
        }
        return [
            {
                "chunk_type": "decision_final",
                "chunk_id": "decision_final",
                "content": str(summary),
            }
        ]

    def _stringify_fact(self, fact: Any) -> str:
        if isinstance(fact, dict):
            key = fact.get("concept") or fact.get("key") or fact.get("label") or "fact"
            value = fact.get("value") or fact.get("text") or fact
            return f"{key}: {value}"
        return str(fact)

    def _chunk_cot(self, cot: str) -> List[Dict[str, Any]]:
        sections = []
        lines = cot.splitlines()
        buffer: List[str] = []
        current_title = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("##"):
                if buffer:
                    sections.append(self._section_from_buffer(current_title, buffer))
                    buffer = []
                current_title = stripped.lstrip("#").strip()
                continue
            buffer.append(line)
        if buffer:
            sections.append(self._section_from_buffer(current_title, buffer))

        if not sections:
            return []

        normalized = []
        for idx, section in enumerate(sections, start=1):
            normalized.append(
                {
                    "chunk_type": "cot_section",
                    "chunk_id": f"cot_{idx}",
                    "content": section["content"],
                    "metadata": {"section_title": section.get("title")},
                }
            )
        return normalized

    def _section_from_buffer(self, title: Optional[str], buffer: List[str]) -> Dict[str, Any]:
        content = "\n".join(buffer).strip()
        return {"title": title or "section", "content": content}


class AuditEventLogger:
    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is None:
            settings = load_settings()
            if not settings.supabase_url or not settings.supabase_service_role_key:
                return None
            # audit_events table is global (no tenant_id column). Use a raw REST client
            # without tenant_id auto-injection to avoid 400 "column tenant_id does not exist".
            self._client = create_supabase_rest_client(
                settings.supabase_url,
                settings.supabase_service_role_key,
            )
        return self._client

    def log(self, event_type: str, case_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        client = self._get_client()
        if not client:
            return
        # PostgREST does not accept SQL functions like "now()" as JSON values.
        # Let DB defaults populate id/created_at.
        payload: Dict[str, Any] = {"event_type": event_type, "metadata": metadata or {}}
        if case_id:
            # DB schema uses UUID case_id; API uses external text case_id.
            # If it's not a UUID, store it in metadata to preserve traceability.
            try:
                UUID(str(case_id))
                payload["case_id"] = case_id
            except Exception:
                payload["metadata"]["case_id_text"] = str(case_id)
        try:
            client.table("audit_events").insert(payload).execute()
        except Exception as exc:
            logger.warning(f"Failed to log audit event: {exc}")


class HybridRetriever:
    def __init__(self) -> None:
        settings = load_settings()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("Supabase not configured")
        self._client = create_tenant_aware_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
            default_tenant_id=settings.default_tenant_id,
        )
        self._embedder = EmbeddingService(db=None)  # type: ignore[arg-type]
        self._audit = AuditEventLogger()

    def search(
        self,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        use_graph_expansion: bool = True,
    ) -> Dict[str, Any]:
        started = time.time()
        filters = filters.copy() if filters else {}
        filters.setdefault("tenant_id", get_effective_tenant_id())
        expanded_filters = filters.copy()

        if use_graph_expansion:
            expanded_filters = self._expand_filters(filters)

        query_embedding = self._embedder.generate_embedding(query_text)
        payload = {
            "query_embedding": query_embedding,
            "query_text": query_text,
            "filters": expanded_filters,
            "match_count": top_k,
        }
        res = self._client.rpc("hybrid_case_search", payload).execute()
        results = res.data or []
        latency_ms = int((time.time() - started) * 1000)

        if expanded_filters != filters:
            self._audit.log(
                "GRAPH_EXPANSION_APPLIED",
                metadata={"original_filters": filters, "expanded_filters": expanded_filters},
            )

        return {
            "results": results,
            "latency_ms": latency_ms,
            "filters": expanded_filters,
        }

    def _expand_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        company = filters.get("company")
        if not company:
            return filters
        try:
            entities = (
                self._client.table("ops_entities")
                .select("id,name,properties")
                .ilike("name", f"%{company}%")
                .limit(5)
                .execute()
            ).data or []
            if not entities:
                return filters
            entity_ids = [e["id"] for e in entities]
            rels = (
                self._client.table("kg_relationships")
                .select("source_entity_id,target_entity_id")
                .or_(f"source_entity_id.in.({','.join(entity_ids)}),target_entity_id.in.({','.join(entity_ids)})")
                .limit(50)
                .execute()
            ).data or []
            neighbor_ids = set()
            for rel in rels:
                neighbor_ids.add(rel.get("source_entity_id"))
                neighbor_ids.add(rel.get("target_entity_id"))
            neighbor_ids.discard(None)
            if not neighbor_ids:
                return filters
            related = (
                self._client.table("ops_entities")
                .select("name")
                .in_("id", list(neighbor_ids))
                .limit(20)
                .execute()
            ).data or []
            company_in = [row.get("name") for row in related if row.get("name")]
            if company_in:
                merged = filters.copy()
                merged["company_in"] = list(dict.fromkeys([company] + company_in))
                return merged
        except Exception as exc:
            logger.warning(f"Graph expansion failed: {exc}")
        return filters


def build_human_diff(ai_recommendation: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any]:
    try:
        ai = ai_recommendation or {}
        human = decision or {}
        return {"diffs": diff_decisions(ai, human)}
    except Exception:
        return {"diffs": []}


def build_selfcheck_runs(decision: DecisionResult, distill: DistillResult) -> Dict[str, Any]:
    from app.services.selfcheck import SelfCheckService

    service = SelfCheckService()
    check = service.evaluate(decision, distill)
    return {
        "runs": [
            {
                "consistency_score": check.get("consistency_score"),
                "confidence_level": check.get("confidence_level"),
                "field_checks": check.get("field_checks"),
            }
        ],
        "summary": check,
    }
