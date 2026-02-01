from typing import Dict
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

    def _count_rows(self, table: str) -> int:
        res = self.client.table(table).select("*").execute()
        return len(res.data or [])
