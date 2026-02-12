from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from app.core.tenant_context import get_effective_tenant_id
from app.services.types import DecisionResult, DistillResult


class DBClient:
    def create_case(self, case_data: Dict) -> str:
        raise NotImplementedError

    def add_document(self, case_id: str, document: Dict) -> str:
        raise NotImplementedError

    def save_distill(self, case_id: str, distill: DistillResult) -> None:
        raise NotImplementedError

    def save_decision(self, case_id: str, decision: DecisionResult) -> None:
        raise NotImplementedError

    def get_case(self, case_id: str) -> Dict:
        raise NotImplementedError

    def list_cases(self) -> Dict:
        raise NotImplementedError

    def list_documents(self) -> Dict:
        raise NotImplementedError

    def save_rag_context(self, case_id: str, contexts: List[Dict[str, Any]]) -> None:
        raise NotImplementedError

    def list_rag_context(self, limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def search_rag_context(
        self,
        entity: Optional[str] = None,
        period: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def save_graph_triples(self, case_id: str, triples: List[Dict[str, Any]]) -> None:
        raise NotImplementedError

    def list_graph_triples(self, limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def search_graph_triples(
        self,
        head: Optional[str] = None,
        relation: Optional[str] = None,
        tail: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def save_training_set(self, case_id: str, record: Dict[str, Any]) -> None:
        raise NotImplementedError

    def list_training_sets(self, limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def search_training_sets(
        self,
        case_id: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def save_case_embedding(self, record: Dict[str, Any]) -> None:
        raise NotImplementedError

    def search_case_embeddings(
        self,
        query_embedding: List[float],
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def list_case_embeddings(self, limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def save_evidence_feedback(self, record: Dict[str, Any]) -> None:
        raise NotImplementedError

    def get_feedback_summary(self, case_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def append_audit_log(self, record: Dict[str, Any]) -> None:
        raise NotImplementedError

    def list_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get_license_by_key(self, license_key: str, user_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def upsert_license_activation(self, license_id: str, device_fingerprint: str) -> None:
        raise NotImplementedError

    def record_license_check(self, license_id: str, device_fingerprint: str, result: str) -> None:
        raise NotImplementedError

    def update_case_status(self, case_id: str, status: str, fields: Optional[Dict[str, Any]] = None) -> None:
        raise NotImplementedError

    # -------------------------------------------------------------------------
    # Spoke A/B downstream consumption (WS8)
    # -------------------------------------------------------------------------
    def get_or_create_active_dataset_version(self, name_hint: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def seal_dataset_version(self, dataset_version_id: str) -> None:
        raise NotImplementedError

    def list_dataset_versions(self, limit: int = 50) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def insert_spoke_a_sample(self, record: Dict[str, Any]) -> str:
        raise NotImplementedError

    def list_spoke_a_samples(self, dataset_version_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def insert_spoke_b_artifact(self, record: Dict[str, Any]) -> str:
        raise NotImplementedError

    def get_spoke_b_artifact(self, doc_id: str, kind: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    # -------------------------------------------------------------------------
    # Console / Model Registry / Run Logs
    # -------------------------------------------------------------------------
    def list_model_registry(self, limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def upsert_model_registry(self, record: Dict[str, Any]) -> str:
        raise NotImplementedError

    def insert_llm_run(self, record: Dict[str, Any]) -> str:
        raise NotImplementedError

    def list_llm_runs(self, limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def insert_rag_run(self, record: Dict[str, Any]) -> str:
        raise NotImplementedError

    def insert_rag_run_chunks(self, run_id: str, chunks: List[Dict[str, Any]]) -> None:
        raise NotImplementedError

    def list_rag_runs(self, limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError


class InMemoryDB(DBClient):
    def __init__(self) -> None:
        self.cases: Dict[str, Dict] = {}
        self.docs: Dict[str, Dict] = {}
        # DataForge raw_documents table emulation (id -> payload).
        self.raw_documents: Dict[str, Dict[str, Any]] = {}
        self.rag_contexts: List[Dict[str, Any]] = []
        self.graph_triples: List[Dict[str, Any]] = []
        self.training_sets: List[Dict[str, Any]] = []
        self.case_embeddings: List[Dict[str, Any]] = []
        self.evidence_feedback: List[Dict[str, Any]] = []
        self.audit_logs: List[Dict[str, Any]] = []
        self.licenses: Dict[str, Dict[str, Any]] = {}
        self.license_activations: List[Dict[str, Any]] = []
        self.license_checks: List[Dict[str, Any]] = []
        self.dataset_versions: List[Dict[str, Any]] = []
        self.spoke_a_samples: List[Dict[str, Any]] = []
        self.spoke_b_artifacts: List[Dict[str, Any]] = []
        self.model_registry: List[Dict[str, Any]] = []
        self.llm_runs: List[Dict[str, Any]] = []
        self.rag_runs: List[Dict[str, Any]] = []
        self.rag_run_chunks: List[Dict[str, Any]] = []

    def _tenant_id(self) -> str:
        return get_effective_tenant_id()

    def create_case(self, case_data: Dict) -> str:
        case_id = case_data.get("case_id") or f"case_{len(self.cases)+1}"
        self.cases[case_id] = {
            "case_id": case_id,
            "title": case_data.get("title", "Untitled"),
            "status": "created",
            "documents": [],
            "distill": None,
            "decision": None,
            "tenant_id": self._tenant_id(),
        }
        return case_id

    def add_document(self, case_id: str, document: Dict) -> str:
        doc_id = document.get("doc_id") or f"doc_{len(self.docs)+1}"
        record = {"doc_id": doc_id, "tenant_id": self._tenant_id(), **document}
        self.docs[doc_id] = record
        case = self.cases.get(case_id)
        if case and case.get("tenant_id") == self._tenant_id():
            case["documents"].append(doc_id)
        return doc_id

    def save_distill(self, case_id: str, distill: DistillResult) -> None:
        self.cases[case_id]["distill"] = distill
        self.cases[case_id]["status"] = "distilled"

    def save_decision(self, case_id: str, decision: DecisionResult) -> None:
        self.cases[case_id]["decision"] = decision
        self.cases[case_id]["status"] = "decided"

    def get_case(self, case_id: str) -> Dict:
        case = self.cases.get(case_id)
        if case and case.get("tenant_id") == self._tenant_id():
            return case
        return {}

    def list_cases(self) -> Dict:
        tenant_id = self._tenant_id()
        return [case for case in self.cases.values() if case.get("tenant_id") == tenant_id]

    def list_documents(self) -> Dict:
        tenant_id = self._tenant_id()
        return [doc for doc in self.docs.values() if doc.get("tenant_id") == tenant_id]

    def save_rag_context(self, case_id: str, contexts: List[Dict[str, Any]]) -> None:
        for context in contexts:
            record = {**context, "case_id": case_id, "tenant_id": self._tenant_id()}
            self.rag_contexts.append(record)

    def list_rag_context(self, limit: int = 100) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        filtered = [record for record in self.rag_contexts if record.get("tenant_id") == tenant_id]
        return filtered[:limit]

    def search_rag_context(
        self,
        entity: Optional[str] = None,
        period: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for context in self.rag_contexts:
            if context.get("tenant_id") != self._tenant_id():
                continue
            if entity and str(context.get("entity", "")).lower() != entity.lower():
                continue
            if period and str(context.get("period", "")).lower() != period.lower():
                continue
            if keyword:
                kw = keyword.lower()
                text = str(context.get("text_content", "")).lower()
                keywords = [str(k).lower() for k in context.get("keywords", [])]
                if kw not in text and kw not in keywords:
                    continue
            results.append(context)
            if len(results) >= limit:
                break
        return results

    def save_graph_triples(self, case_id: str, triples: List[Dict[str, Any]]) -> None:
        for triple in triples:
            record = {**triple, "case_id": case_id, "tenant_id": self._tenant_id()}
            self.graph_triples.append(record)

    def list_graph_triples(self, limit: int = 100) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        filtered = [record for record in self.graph_triples if record.get("tenant_id") == tenant_id]
        return filtered[:limit]

    def search_graph_triples(
        self,
        head: Optional[str] = None,
        relation: Optional[str] = None,
        tail: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for triple in self.graph_triples:
            if triple.get("tenant_id") != self._tenant_id():
                continue
            if head and str(triple.get("head_node", "")).lower() != head.lower():
                continue
            if relation and str(triple.get("relation", "")).lower() != relation.lower():
                continue
            if tail and str(triple.get("tail_node", "")).lower() != tail.lower():
                continue
            results.append(triple)
            if len(results) >= limit:
                break
        return results

    def save_training_set(self, case_id: str, record: Dict[str, Any]) -> None:
        payload = {**record, "case_id": case_id, "tenant_id": self._tenant_id()}
        self.training_sets.append(payload)

    def list_training_sets(self, limit: int = 100) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        filtered = [record for record in self.training_sets if record.get("tenant_id") == tenant_id]
        return filtered[:limit]

    def search_training_sets(
        self,
        case_id: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for record in self.training_sets:
            if record.get("tenant_id") != self._tenant_id():
                continue
            if case_id and record.get("case_id") != case_id:
                continue
            if keyword:
                kw = keyword.lower()
                prompt = str(record.get("training_prompt", "")).lower()
                narrative = str(record.get("output_narrative", "")).lower()
                if kw not in prompt and kw not in narrative:
                    continue
            results.append(record)
            if len(results) >= limit:
                break
        return results

    def save_case_embedding(self, record: Dict[str, Any]) -> None:
        record = {**record, "tenant_id": self._tenant_id()}
        self.case_embeddings.append(record)

    def search_case_embeddings(
        self,
        query_embedding: List[float],
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not query_embedding:
            return []
        results = []
        for record in self.case_embeddings:
            if record.get("tenant_id") != self._tenant_id():
                continue
            if filters:
                skip = False
                for key, value in filters.items():
                    if value is None:
                        continue
                    if str(record.get(key)) != str(value):
                        skip = True
                        break
                if skip:
                    continue
            embedding = record.get("embedding") or []
            if not embedding:
                continue
            similarity = _cosine_similarity(query_embedding, embedding)
            results.append({**record, "similarity": similarity})
        results.sort(key=lambda r: r.get("similarity", 0), reverse=True)
        return results[:limit]

    def list_case_embeddings(self, limit: int = 100) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        filtered = [record for record in self.case_embeddings if record.get("tenant_id") == tenant_id]
        return filtered[:limit]

    def save_evidence_feedback(self, record: Dict[str, Any]) -> None:
        record = {**record, "tenant_id": self._tenant_id()}
        self.evidence_feedback.append(record)

    def get_feedback_summary(self, case_id: str) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        relevant = [
            r
            for r in self.evidence_feedback
            if r.get("case_id") == case_id and r.get("tenant_id") == tenant_id
        ]
        scores = [r.get("score", 0) for r in relevant]
        total = len(relevant)
        positive = len([s for s in scores if s > 0])
        negative = len([s for s in scores if s < 0])
        avg = sum(scores) / total if total else 0
        return {
            "case_id": case_id,
            "total_feedback": total,
            "positive": positive,
            "negative": negative,
            "average_score": avg,
        }

    def append_audit_log(self, record: Dict[str, Any]) -> None:
        record = {**record, "tenant_id": self._tenant_id()}
        self.audit_logs.append(record)

    def list_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        filtered = [record for record in reversed(self.audit_logs) if record.get("tenant_id") == tenant_id]
        return filtered[:limit]

    def get_license_by_key(self, license_key: str, user_id: str) -> Optional[Dict[str, Any]]:
        license_record = self.licenses.get(license_key)
        if license_record and license_record.get("user_id") == user_id:
            if license_record.get("tenant_id") == self._tenant_id():
                return license_record
        return None

    def upsert_license_activation(self, license_id: str, device_fingerprint: str) -> None:
        for activation in self.license_activations:
            if activation["license_id"] == license_id and activation["device_fingerprint"] == device_fingerprint:
                activation["last_heartbeat"] = "now"
                return
        self.license_activations.append({
            "license_id": license_id,
            "device_fingerprint": device_fingerprint,
            "last_heartbeat": "now",
            "tenant_id": self._tenant_id(),
        })

    def record_license_check(self, license_id: str, device_fingerprint: str, result: str) -> None:
        self.license_checks.append({
            "license_id": license_id,
            "device_fingerprint": device_fingerprint,
            "result": result,
            "tenant_id": self._tenant_id(),
        })

    def update_case_status(self, case_id: str, status: str, fields: Optional[Dict[str, Any]] = None) -> None:
        if case_id not in self.cases:
            return
        if self.cases[case_id].get("tenant_id") != self._tenant_id():
            return
        self.cases[case_id]["status"] = status
        if fields:
            self.cases[case_id].update(fields)

    # -------------------------------------------------------------------------
    # WS8: dataset versions + Spoke A/B artifacts
    # -------------------------------------------------------------------------
    def get_or_create_active_dataset_version(self, name_hint: Optional[str] = None) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        for v in self.dataset_versions:
            if v.get("tenant_id") == tenant_id and v.get("status") == "active":
                return v
        version_id = f"ds_{len(self.dataset_versions) + 1}"
        record = {
            "id": version_id,
            "name": name_hint or version_id,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tenant_id": tenant_id,
        }
        self.dataset_versions.append(record)
        return record

    def seal_dataset_version(self, dataset_version_id: str) -> None:
        tenant_id = self._tenant_id()
        for v in self.dataset_versions:
            if v.get("tenant_id") == tenant_id and v.get("id") == dataset_version_id:
                v["status"] = "sealed"
                v["sealed_at"] = datetime.now(timezone.utc).isoformat()
                return

    def list_dataset_versions(self, limit: int = 50) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        items = [v for v in self.dataset_versions if v.get("tenant_id") == tenant_id]
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return items[:limit]

    def insert_spoke_a_sample(self, record: Dict[str, Any]) -> str:
        tenant_id = self._tenant_id()
        sample_id = record.get("id") or f"spoke_a_{len(self.spoke_a_samples) + 1}"
        payload = {**record, "id": sample_id, "tenant_id": tenant_id}
        payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        self.spoke_a_samples.append(payload)
        return sample_id

    def list_spoke_a_samples(self, dataset_version_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        items = [
            s
            for s in self.spoke_a_samples
            if s.get("tenant_id") == tenant_id and s.get("dataset_version_id") == dataset_version_id
        ]
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return items[:limit]

    def insert_spoke_b_artifact(self, record: Dict[str, Any]) -> str:
        tenant_id = self._tenant_id()
        artifact_id = record.get("id") or f"spoke_b_{len(self.spoke_b_artifacts) + 1}"
        payload = {**record, "id": artifact_id, "tenant_id": tenant_id}
        payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        self.spoke_b_artifacts.append(payload)
        return artifact_id

    def get_spoke_b_artifact(self, doc_id: str, kind: str) -> Optional[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        for a in reversed(self.spoke_b_artifacts):
            if a.get("tenant_id") != tenant_id:
                continue
            if a.get("doc_id") == doc_id and a.get("kind") == kind:
                return a
        return None

    # Console / Model Registry / Run Logs
    def list_model_registry(self, limit: int = 100) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        items = [m for m in self.model_registry if m.get("tenant_id") == tenant_id]
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return items[:limit]

    def upsert_model_registry(self, record: Dict[str, Any]) -> str:
        model_id = record.get("id") or f"model_{len(self.model_registry) + 1}"
        payload = {**record, "id": model_id, "tenant_id": self._tenant_id()}
        payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        self.model_registry = [m for m in self.model_registry if m.get("id") != model_id]
        self.model_registry.append(payload)
        return model_id

    def insert_llm_run(self, record: Dict[str, Any]) -> str:
        run_id = record.get("id") or f"llm_{len(self.llm_runs) + 1}"
        payload = {**record, "id": run_id, "tenant_id": self._tenant_id()}
        payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        self.llm_runs.append(payload)
        return run_id

    def list_llm_runs(self, limit: int = 100) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        items = [r for r in self.llm_runs if r.get("tenant_id") == tenant_id]
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return items[:limit]

    def insert_rag_run(self, record: Dict[str, Any]) -> str:
        run_id = record.get("id") or f"rag_{len(self.rag_runs) + 1}"
        payload = {**record, "id": run_id, "tenant_id": self._tenant_id()}
        payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        self.rag_runs.append(payload)
        return run_id

    def insert_rag_run_chunks(self, run_id: str, chunks: List[Dict[str, Any]]) -> None:
        for chunk in chunks:
            payload = {**chunk, "run_id": run_id, "tenant_id": self._tenant_id()}
            payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())
            self.rag_run_chunks.append(payload)

    def list_rag_runs(self, limit: int = 100) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        items = [r for r in self.rag_runs if r.get("tenant_id") == tenant_id]
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return items[:limit]


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
