from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class CaseCreate(BaseModel):
    title: str


class DocumentCreate(BaseModel):
    source: str = "upload"
    filename: str = "document.txt"
    mime_type: str = "text/plain"
    content: Optional[str] = None
    content_base64: Optional[str] = None
    facts: List[Dict[str, Any]] = []
    cot_markdown: Optional[str] = None


class DistillResponse(BaseModel):
    facts: List[Dict[str, Any]]
    cot_markdown: str
    metadata: Dict[str, Any]


class DecisionResponse(BaseModel):
    decision: str
    rationale: str
    actions: List[Dict[str, Any]]
    approvals: List[Dict[str, Any]]


class PipelineResponse(BaseModel):
    case_id: str
    distill: DistillResponse
    decision: DecisionResponse
