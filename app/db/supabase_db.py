import logging
from typing import Any, Dict, List, Optional
from app.services.types import DecisionResult, DistillResult
from app.core.config import load_settings
from app.core.tenant_context import get_effective_tenant_id
from app.db.tenant_scoped_client import create_tenant_aware_client
from uuid import uuid4
from uuid import UUID

logger = logging.getLogger(__name__)

class SupabaseDB:
    def __init__(self, url: str, service_key: str) -> None:
        settings = load_settings()
        self.client: Any = create_tenant_aware_client(
            url,
            service_key,
            default_tenant_id=settings.default_tenant_id,
        )

    def create_case(self, case_data: Dict) -> str:
        case_id = case_data.get("case_id") or f"case_{self._count_rows('cases')+1}"
        payload = {
            "case_id": case_id,
            "title": case_data.get("title", "Untitled"),
            "status": "created",
        }
        self.client.table("cases").upsert(payload).execute()
        return case_id

    def ensure_case_exists(self, case_id: str, *, title: str = "Untitled") -> None:
        """
        Ensure a row exists in public.cases for orchestration flows that accept
        a caller-provided case_id (e.g. multi-agent runs).
        """
        if not case_id:
            return
        try:
            existing = self.client.table("cases").select("case_id").eq("case_id", case_id).limit(1).execute()
            if existing.data:
                return
        except Exception as exc:
            # If select fails, still attempt upsert (idempotent).
            logger.debug("ensure_case_exists select failed: %s", exc)
        self.client.table("cases").upsert({"case_id": case_id, "title": title, "status": "created"}).execute()

    def add_document(self, case_id: str, document: Dict) -> str:
        doc_id = document.get("doc_id") or f"doc_{self._count_rows('documents')+1}"
        payload = {
            "doc_id": doc_id,
            "case_id": case_id,
            "filename": document.get("filename"),
            "mime_type": document.get("mime_type"),
            "source": document.get("source"),
            "payload": document,
        }
        self.client.table("documents").upsert(payload).execute()
        return doc_id

    def save_distill(self, case_id: str, distill: DistillResult) -> None:
        self.ensure_case_exists(case_id, title=(distill.metadata or {}).get("title") or "Untitled")
        payload = {
            "case_id": case_id,
            "distill": {
                "facts": distill.facts,
                "cot_markdown": distill.cot_markdown,
                "metadata": distill.metadata,
            },
            "status": "distilled",
        }
        self.client.table("cases").update(payload).eq("case_id", case_id).execute()

    def save_decision(self, case_id: str, decision: DecisionResult) -> None:
        self.ensure_case_exists(case_id)
        payload = {
            "case_id": case_id,
            "decision": {
                "decision": decision.decision,
                "rationale": decision.rationale,
                "actions": decision.actions,
                "approvals": decision.approvals,
            },
            "status": "decided",
        }
        self.client.table("cases").update(payload).eq("case_id", case_id).execute()

    def get_case(self, case_id: str) -> Dict:
        res = self.client.table("cases").select("*").eq("case_id", case_id).execute()
        if res.data:
            return res.data[0]
        return {}

    def list_cases(self) -> Dict:
        res = self.client.table("cases").select("*").execute()
        return res.data or []

    def list_documents(self) -> Dict:
        res = self.client.table("documents").select("*").execute()
        return res.data or []

    def save_rag_context(self, case_id: str, contexts: List[Dict[str, Any]]) -> None:
        if not contexts:
            return
        payload = [
            {
                "chunk_id": ctx.get("chunk_id"),
                "entity": ctx.get("entity"),
                "period": ctx.get("period"),
                "source": ctx.get("source"),
                "text_content": ctx.get("text_content"),
                "keywords": ctx.get("keywords"),
                "metadata": ctx.get("metadata"),
            }
            for ctx in contexts
        ]
        self.client.table("spoke_c_rag_context").upsert(payload).execute()

    def list_rag_context(self, limit: int = 100) -> List[Dict[str, Any]]:
        res = (
            self.client.table("spoke_c_rag_context")
            .select("*")
            .limit(limit)
            .execute()
        )
        return res.data or []

    def search_rag_context(
        self,
        entity: Optional[str] = None,
        period: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query = self.client.table("spoke_c_rag_context").select("*")
        if entity:
            query = query.eq("entity", entity)
        if period:
            query = query.eq("period", period)
        if keyword:
            query = query.ilike("text_content", f"%{keyword}%")
        res = query.limit(limit).execute()
        return res.data or []

    def save_graph_triples(self, case_id: str, triples: List[Dict[str, Any]]) -> None:
        if not triples:
            return
        payload = [
            {
                "head_node": triple.get("head_node"),
                "relation": triple.get("relation"),
                "tail_node": triple.get("tail_node"),
                "properties": triple.get("properties"),
            }
            for triple in triples
        ]
        self.client.table("spoke_d_graph").insert(payload).execute()

    def list_graph_triples(self, limit: int = 100) -> List[Dict[str, Any]]:
        res = self.client.table("spoke_d_graph").select("*").limit(limit).execute()
        return res.data or []

    def search_graph_triples(
        self,
        head: Optional[str] = None,
        relation: Optional[str] = None,
        tail: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query = self.client.table("spoke_d_graph").select("*")
        if head:
            query = query.eq("head_node", head)
        if relation:
            query = query.eq("relation", relation)
        if tail:
            query = query.eq("tail_node", tail)
        res = query.limit(limit).execute()
        return res.data or []

    def save_training_set(self, case_id: str, record: Dict[str, Any]) -> None:
        payload = {
            "metadata": record.get("metadata"),
            "input_features": record.get("input_features"),
            "reasoning_chain": record.get("reasoning_chain"),
            "output_narrative": record.get("output_narrative"),
            "training_prompt": record.get("training_prompt"),
        }
        self.client.table("ai_training_sets").insert(payload).execute()

    def list_training_sets(self, limit: int = 100) -> List[Dict[str, Any]]:
        res = self.client.table("ai_training_sets").select("*").limit(limit).execute()
        return res.data or []

    def search_training_sets(
        self,
        case_id: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query = self.client.table("ai_training_sets").select("*")
        if case_id:
            query = query.contains("metadata", {"case_id": case_id})
        if keyword:
            query = query.ilike("training_prompt", f"%{keyword}%")
        res = query.limit(limit).execute()
        return res.data or []

    def save_case_embedding(self, record: Dict[str, Any]) -> None:
        payload = dict(record)
        # case_embeddings.case_id is UUID (cases.id), not cases.case_id (text).
        case_id_val = payload.get("case_id")
        if isinstance(case_id_val, str):
            try:
                UUID(case_id_val)
            except Exception:
                res = self.client.table("cases").select("id").eq("case_id", case_id_val).limit(1).execute()
                if res.data:
                    payload["case_id"] = res.data[0].get("id")

        # PostgREST + pgvector: send embedding as vector input string, not JSON array.
        emb = payload.get("embedding")
        if isinstance(emb, list):
            payload["embedding"] = "[" + ",".join([str(x) for x in emb]) + "]"
        self.client.table("case_embeddings").insert(payload).execute()

    def search_case_embeddings(
        self,
        query_embedding: List[float],
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        payload = {
            "query_embedding": query_embedding,
            "match_count": limit,
        }
        merged_filters = filters.copy() if filters else {}
        merged_filters.setdefault("tenant_id", get_effective_tenant_id())
        payload.update({"filters": merged_filters})
        res = self.client.rpc("match_case_embeddings", payload).execute()
        return res.data or []

    def list_case_embeddings(self, limit: int = 100) -> List[Dict[str, Any]]:
        res = self.client.table("case_embeddings").select("*").limit(limit).execute()
        return res.data or []

    def save_evidence_feedback(self, record: Dict[str, Any]) -> None:
        self.client.table("evidence_feedback").insert(record).execute()

    def get_feedback_summary(self, case_id: str) -> Dict[str, Any]:
        payload = {
            "case_id": case_id,
            "tenant_id": get_effective_tenant_id(),
        }
        res = self.client.rpc("feedback_summary", payload).execute()
        if res.data:
            return res.data[0]
        return {
            "case_id": case_id,
            "total_feedback": 0,
            "positive": 0,
            "negative": 0,
            "average_score": 0,
        }

    def append_audit_log(self, record: Dict[str, Any]) -> None:
        self.client.table("audit_logs").insert(record).execute()

    def list_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        res = self.client.table("audit_logs").select("*").order("timestamp", desc=True).limit(limit).execute()
        return res.data or []

    def get_license_by_key(self, license_key: str, user_id: str) -> Optional[Dict[str, Any]]:
        res = (
            self.client.table("licenses")
            .select("*")
            .eq("license_key", license_key)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        return res.data if res.data else None

    def upsert_license_activation(self, license_id: str, device_fingerprint: str) -> None:
        payload = {
            "license_id": license_id,
            "device_fingerprint": device_fingerprint,
        }
        self.client.table("license_activations").upsert(payload).execute()

    def record_license_check(self, license_id: str, device_fingerprint: str, result: str) -> None:
        payload = {
            "license_id": license_id,
            "device_fingerprint": device_fingerprint,
            "check_result": result,
        }
        self.client.table("license_checks").insert(payload).execute()

    def update_case_status(self, case_id: str, status: str, fields: Optional[Dict[str, Any]] = None) -> None:
        payload = {"status": status}
        if fields:
            payload.update(fields)
        self.client.table("cases").update(payload).eq("case_id", case_id).execute()

    # -------------------------------------------------------------------------
    # WS8: dataset versions + Spoke A/B artifacts
    # -------------------------------------------------------------------------
    def get_or_create_active_dataset_version(self, name_hint: Optional[str] = None) -> Dict[str, Any]:
        # Prefer an explicit active version if present.
        existing = (
            self.client.table("dataset_versions")
            .select("*")
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        ).data or []
        if existing:
            return existing[0]

        version_id = str(uuid4())
        payload = {
            "id": version_id,
            "name": name_hint or f"dataset-{version_id[:8]}",
            "status": "active",
            "created_at": "now()",
        }
        self.client.table("dataset_versions").insert(payload).execute()
        created = (
            self.client.table("dataset_versions")
            .select("*")
            .eq("id", version_id)
            .limit(1)
            .execute()
        ).data or []
        return created[0] if created else payload

    def seal_dataset_version(self, dataset_version_id: str) -> None:
        self.client.table("dataset_versions").update(
            {"status": "sealed", "sealed_at": "now()"}
        ).eq("id", dataset_version_id).execute()

    def list_dataset_versions(self, limit: int = 50) -> List[Dict[str, Any]]:
        res = (
            self.client.table("dataset_versions")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []

    def insert_spoke_a_sample(self, record: Dict[str, Any]) -> str:
        sample_id = record.get("id") or str(uuid4())
        payload = {**record, "id": sample_id}
        payload.setdefault("created_at", "now()")
        self.client.table("spoke_a_samples").insert(payload).execute()
        return sample_id

    def list_spoke_a_samples(self, dataset_version_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        res = (
            self.client.table("spoke_a_samples")
            .select("*")
            .eq("dataset_version_id", dataset_version_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []

    def insert_spoke_b_artifact(self, record: Dict[str, Any]) -> str:
        artifact_id = record.get("id") or str(uuid4())
        payload = {**record, "id": artifact_id}
        payload.setdefault("created_at", "now()")
        self.client.table("spoke_b_artifacts").insert(payload).execute()
        return artifact_id

    def get_spoke_b_artifact(self, doc_id: str, kind: str) -> Optional[Dict[str, Any]]:
        res = (
            self.client.table("spoke_b_artifacts")
            .select("*")
            .eq("doc_id", doc_id)
            .eq("kind", kind)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return (res.data or [None])[0]

    # -------------------------------------------------------------------------
    # Console / Model Registry / Run Logs
    # -------------------------------------------------------------------------
    def list_model_registry(self, limit: int = 100) -> List[Dict[str, Any]]:
        res = (
            self.client.table("model_registry")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []

    def upsert_model_registry(self, record: Dict[str, Any]) -> str:
        model_id = record.get("id") or str(uuid4())
        payload = {**record, "id": model_id}
        payload.setdefault("created_at", "now()")
        self.client.table("model_registry").upsert(payload).execute()
        return model_id

    def insert_llm_run(self, record: Dict[str, Any]) -> str:
        run_id = record.get("id") or str(uuid4())
        payload = {**record, "id": run_id}
        payload.setdefault("created_at", "now()")
        self.client.table("llm_runs").insert(payload).execute()
        return run_id

    def list_llm_runs(self, limit: int = 100) -> List[Dict[str, Any]]:
        res = (
            self.client.table("llm_runs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []

    def insert_rag_run(self, record: Dict[str, Any]) -> str:
        run_id = record.get("id") or str(uuid4())
        payload = {**record, "id": run_id}
        payload.setdefault("created_at", "now()")
        self.client.table("rag_runs").insert(payload).execute()
        return run_id

    def insert_rag_run_chunks(self, run_id: str, chunks: List[Dict[str, Any]]) -> None:
        if not chunks:
            return
        payloads = []
        for chunk in chunks:
            payload = {**chunk, "run_id": run_id}
            payload.setdefault("created_at", "now()")
            payloads.append(payload)
        self.client.table("rag_run_chunks").insert(payloads).execute()

    def list_rag_runs(self, limit: int = 100) -> List[Dict[str, Any]]:
        res = (
            self.client.table("rag_runs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []

    def _count_rows(self, table: str) -> int:
        res = self.client.table(table).select("*").execute()
        return len(res.data or [])
