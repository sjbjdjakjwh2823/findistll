from typing import Any, Dict, List, Optional
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


class InMemoryDB(DBClient):
    def __init__(self) -> None:
        self.cases: Dict[str, Dict] = {}
        self.docs: Dict[str, Dict] = {}
        self.rag_contexts: List[Dict[str, Any]] = []
        self.graph_triples: List[Dict[str, Any]] = []
        self.training_sets: List[Dict[str, Any]] = []

    def create_case(self, case_data: Dict) -> str:
        case_id = case_data.get("case_id") or f"case_{len(self.cases)+1}"
        self.cases[case_id] = {
            "case_id": case_id,
            "title": case_data.get("title", "Untitled"),
            "status": "created",
            "documents": [],
            "distill": None,
            "decision": None,
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

    def save_rag_context(self, case_id: str, contexts: List[Dict[str, Any]]) -> None:
        for context in contexts:
            record = {**context, "case_id": case_id}
            self.rag_contexts.append(record)

    def list_rag_context(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.rag_contexts[:limit]

    def search_rag_context(
        self,
        entity: Optional[str] = None,
        period: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for context in self.rag_contexts:
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
            record = {**triple, "case_id": case_id}
            self.graph_triples.append(record)

    def list_graph_triples(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.graph_triples[:limit]

    def search_graph_triples(
        self,
        head: Optional[str] = None,
        relation: Optional[str] = None,
        tail: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for triple in self.graph_triples:
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
        payload = {**record, "case_id": case_id}
        self.training_sets.append(payload)

    def list_training_sets(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.training_sets[:limit]

    def search_training_sets(
        self,
        case_id: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for record in self.training_sets:
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
