from typing import Dict, List

from supabase import Client, create_client

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

    def upsert_graph_edges(self, case_id: str, edges: List[Dict]) -> None:
        if not edges:
            return
        payload = []
        for edge in edges:
            payload.append(
                {
                    "case_id": case_id,
                    "doc_id": edge.get("doc_id"),
                    "head_node": edge.get("head_node"),
                    "relation": edge.get("relation"),
                    "tail_node": edge.get("tail_node"),
                    "properties": edge.get("properties", {}),
                    "event_time": edge.get("event_time"),
                    "valid_from": edge.get("valid_from"),
                    "valid_to": edge.get("valid_to"),
                    "observed_at": edge.get("observed_at"),
                    "time_source": edge.get("time_source"),
                    "time_granularity": edge.get("time_granularity"),
                }
            )
        self.client.table("spoke_d_graph").insert(payload).execute()

    def list_graph_edges(self, case_id: str) -> List[Dict]:
        res = self.client.table("spoke_d_graph").select("*").eq("case_id", case_id).execute()
        return res.data or []

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

    def _count_rows(self, table: str) -> int:
        res = self.client.table(table).select("*").execute()
        return len(res.data or [])
