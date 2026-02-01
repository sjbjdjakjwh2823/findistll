from typing import Dict
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


class InMemoryDB(DBClient):
    def __init__(self) -> None:
        self.cases: Dict[str, Dict] = {}
        self.docs: Dict[str, Dict] = {}

    def create_case(self, case_data: Dict) -> str:
        case_id = case_data.get("case_id") or f"case_{len(self.cases)+1}"
        self.cases[case_id] = {
            "case_id": case_id,
            "title": case_data.get("title", "Untitled"),
            "status": "created",
            "documents": [],
            "distill": None,
            "decision": None
        }
        return case_id

    def add_document(self, case_id: str, document: Dict) -> str:
        doc_id = document.get("doc_id") or f"doc_{len(self.docs)+1}"
        record = {"doc_id": doc_id, **document}
        self.docs[doc_id] = record
        self.cases[case_id]["documents"].append(doc_id)
        return doc_id

    def save_distill(self, case_id: str, distill: DistillResult) -> None:
        self.cases[case_id]["distill"] = distill
        self.cases[case_id]["status"] = "distilled"

    def save_decision(self, case_id: str, decision: DecisionResult) -> None:
        self.cases[case_id]["decision"] = decision
        self.cases[case_id]["status"] = "decided"

    def get_case(self, case_id: str) -> Dict:
        return self.cases.get(case_id, {})

    def list_cases(self) -> Dict:
        return list(self.cases.values())

    def list_documents(self) -> Dict:
        return list(self.docs.values())
