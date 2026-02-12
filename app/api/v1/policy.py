from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.policy_engine import PolicyEngine


router = APIRouter(prefix="/policy", tags=["Policy"])


class PolicyCheckIn(BaseModel):
    payload: str = Field(..., description="Payload to evaluate for egress policy.")
    metadata: Optional[Dict[str, Any]] = None
    destination: str = Field(default="external_api")


@router.post("/check")
def check_policy(payload: PolicyCheckIn):
    engine = PolicyEngine()
    decision = engine.check_egress(
        payload.payload,
        metadata=payload.metadata or {},
        destination=payload.destination,
    )
    return {
        "action": decision.action,
        "reason": decision.reason,
        "sensitive_hits": decision.sensitive_hits,
        "requires_approval": decision.requires_approval,
    }
