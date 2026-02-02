from typing import Dict, List

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

    def upsert_graph_edges(self, case_id: str, edges: List[Dict]) -> None:
        raise NotImplementedError

    def list_graph_edges(self, case_id: str) -> List[Dict]:
        raise NotImplementedError

    def save_audit_event(self, case_id: str, event: Dict) -> None:
        raise NotImplementedError

    def list_audit_events(self, case_id: str) -> List[Dict]:
        raise NotImplementedError


class InMemoryDB(DBClient):
    def __init__(self) -> None:
        self.cases: Dict[str, Dict] = {}
        self.docs: Dict[str, Dict] = {}
        self.graph_edges: Dict[str, List[Dict]] = {}
        self.audit_events: Dict[str, List[Dict]] = {}

    def create_case(self, case_data: Dict) -> str:
        case_id = case_data.get("case_id") or f"case_{len(self.cases)+1}"
        self.cases[case_id] = {
            "case_id": case_id,
            "title": case_data.get("title", "Untitled"),
            "status": "created",
            "documents": [],
            "distill": None,
            "decision": None,
            "graph_edge_count": 0,
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

    def upsert_graph_edges(self, case_id: str, edges: List[Dict]) -> None:
        if not edges:
            return
        bucket = self.graph_edges.setdefault(case_id, [])
        bucket.extend(edges)
        self.cases[case_id]["graph_edge_count"] = len(bucket)

    def list_graph_edges(self, case_id: str) -> List[Dict]:
        return list(self.graph_edges.get(case_id, []))

    def save_audit_event(self, case_id: str, event: Dict) -> None:
        bucket = self.audit_events.setdefault(case_id, [])
        bucket.append(event)

    def list_audit_events(self, case_id: str) -> List[Dict]:
        return list(self.audit_events.get(case_id, []))
