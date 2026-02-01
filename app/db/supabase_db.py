from typing import Any, Dict, List, Optional
from supabase import create_client, Client
from app.services.types import DecisionResult, DistillResult


class SupabaseDB:
    def __init__(self, url: str, service_key: str) -> None:
        self.client: Client = create_client(url, service_key)

    def create_case(self, case_data: Dict) -> str:
        case_id = case_data.get("case_id") or f"case_{self._count_rows('cases')+1}"
        payload = {
            "case_id": case_id,
            "title": case_data.get("title", "Untitled"),
            "status": "created",
        }
        self.client.table("cases").upsert(payload).execute()
        return case_id

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

    def _count_rows(self, table: str) -> int:
        res = self.client.table(table).select("*").execute()
        return len(res.data or [])
