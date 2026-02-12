"""
OpsGraph API - Phase 3
Case management, entity graph, and feedback loop endpoints.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.services.opsgraph_service import OpsGraphService
from app.core.auth import get_current_user
from app.core.rbac import has_permission

router = APIRouter(prefix="/opsgraph", tags=["OpsGraph"])

_SERVICE_CACHE = None

def _get_service():
    global _SERVICE_CACHE
    if _SERVICE_CACHE is not None:
        return _SERVICE_CACHE
    try:
        _SERVICE_CACHE = OpsGraphService()
        return _SERVICE_CACHE
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"OpsGraph unavailable: {exc}")


class EntityCreateRequest(BaseModel):
    entity_type: str = Field(..., description="Entity type: company, person, risk, event")
    name: str = Field(..., description="Entity name")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict)


class EntityCreateResponse(BaseModel):
    entity_id: str
    status: str


class EntityLinkRequest(BaseModel):
    source_id: str
    target_id: str
    relationship_type: str
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict)
    confidence: float = 0.5


class EntityGraphResponse(BaseModel):
    nodes: list
    relationships: list


class CaseCreateRequest(BaseModel):
    title: str
    entity_id: Optional[str] = None
    priority: str = Field("medium", description="low | medium | high")
    ai_recommendation: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CaseCreateResponse(BaseModel):
    case_id: str
    status: str


class CaseTransitionRequest(BaseModel):
    target_status: str
    user_id: Optional[str] = None
    user_role: Optional[str] = None
    reason: Optional[str] = None
    evidence_reviewed: Optional[list] = None
    revision_requests: Optional[list] = None


class CaseResolveRequest(BaseModel):
    decision: Dict[str, Any]
    agreed_with_ai: bool
    reasoning: Optional[str] = None


class CaseResolveResponse(BaseModel):
    status: str


@router.post("/entities", response_model=EntityCreateResponse)
def create_entity(payload: EntityCreateRequest):
    entity_id = _get_service().create_entity(
        entity_type=payload.entity_type,
        name=payload.name,
        properties=payload.properties,
    )
    return {"entity_id": entity_id, "status": "created"}


@router.post("/entities/link")
def link_entities(payload: EntityLinkRequest):
    rel_id = _get_service().link_entities(
        source_id=payload.source_id,
        target_id=payload.target_id,
        relationship_type=payload.relationship_type,
        properties=payload.properties,
        confidence=payload.confidence,
    )
    return {"relationship_id": rel_id, "status": "created"}


@router.get("/entities/{entity_id}/graph", response_model=EntityGraphResponse)
def get_entity_graph(entity_id: str):
    entity = _get_service().get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="entity not found")
    graph = _get_service().get_entity_graph(entity_id)
    return graph


@router.post("/cases", response_model=CaseCreateResponse)
def create_case(payload: CaseCreateRequest, current_user = Depends(get_current_user)):
    if not has_permission(current_user.role, "case", "create"):
        raise HTTPException(status_code=403, detail="Requires case:create")
    case_id = _get_service().create_case(
        title=payload.title,
        entity_id=payload.entity_id,
        priority=payload.priority,
        ai_recommendation=payload.ai_recommendation,
    )
    return {"case_id": case_id, "status": "created"}


@router.get("/cases")
def list_cases(status: Optional[str] = None, limit: int = 50):
    return {"cases": _get_service().list_cases(status=status, limit=limit)}


@router.get("/inbox/prioritized")
def list_prioritized_cases(status: Optional[str] = None, limit: int = 50):
    return {"cases": _get_service().list_prioritized_cases(status=status, limit=limit)}


@router.post("/kg/rebuild")
def rebuild_knowledge_graph(current_user = Depends(get_current_user)):
    if not has_permission(current_user.role, "case", "update"):
        raise HTTPException(status_code=403, detail="Requires case:update")
    return _get_service().build_knowledge_graph()


@router.get("/kg/risk/{entity_id}")
def get_entity_risk(entity_id: str, current_user = Depends(get_current_user)):
    if not has_permission(current_user.role, "case", "read"):
        raise HTTPException(status_code=403, detail="Requires case:read")
    return _get_service().predict_entity_risk(entity_id)


@router.post("/ontology/rebuild")
def rebuild_ontology(current_user = Depends(get_current_user)):
    if not has_permission(current_user.role, "case", "update"):
        raise HTTPException(status_code=403, detail="Requires case:update")
    return _get_service().build_ontology()


@router.get("/cases/{case_id}")
def get_case(case_id: str):
    case = _get_service().get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    return case


@router.get("/cases/{case_id}/evidence-diff")
def get_evidence_diff(case_id: str, current_user = Depends(get_current_user)):
    if not has_permission(current_user.role, "case", "read"):
        raise HTTPException(status_code=403, detail="Requires case:read")
    case = _get_service().get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    from app.services.evidence_diff import diff_decisions
    ai = case.get("ai_recommendation", {}) or {}
    human = (case.get("human_decision") or {}).get("decision", {})
    return {"diffs": diff_decisions(ai, human)}


@router.get("/audit")
def list_audit_logs(limit: int = 50):
    return {"audit_logs": _get_service().list_audit_logs(limit=limit)}


@router.post("/cases/{case_id}/transition")
def transition_case(case_id: str, payload: CaseTransitionRequest, current_user = Depends(get_current_user)):
    if not has_permission(current_user.role, "case", "update"):
        raise HTTPException(status_code=403, detail="Requires case:update")
    return _get_service().transition_case(
        case_id=case_id,
        target_status=payload.target_status,
        user_id=payload.user_id or current_user.user_id,
        user_role=payload.user_role or current_user.role,
        reason=payload.reason,
        evidence_reviewed=payload.evidence_reviewed,
        revision_requests=payload.revision_requests,
    )


@router.post("/cases/{case_id}/resolve", response_model=CaseResolveResponse)
def resolve_case(case_id: str, payload: CaseResolveRequest, current_user = Depends(get_current_user)):
    if not has_permission(current_user.role, "case", "update"):
        raise HTTPException(status_code=403, detail="Requires case:update")
    case = _get_service().get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")

    _get_service().resolve_case(
        case_id=case_id,
        decision=payload.decision,
        agreed_with_ai=payload.agreed_with_ai,
        human_reasoning=payload.reasoning,
    )
    return {"status": "resolved"}
