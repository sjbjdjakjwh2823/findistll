"""
Decision State Machine - Phase 3
Implements lifecycle transitions, permission checks, and business rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


CaseStatus = str


TRANSITIONS: Dict[CaseStatus, List[CaseStatus]] = {
    "draft": ["ai_generated", "cancelled"],
    "ai_generated": ["under_review", "cancelled"],
    "under_review": ["edited", "pending_approval", "rejected", "cancelled"],
    "edited": ["under_review", "pending_approval"],
    "pending_approval": ["revision_requested", "approved", "rejected"],
    "revision_requested": ["under_review"],
    "approved": ["closed"],
    "rejected": ["closed"],
    "closed": [],
    "cancelled": [],
}

ROLE_PERMISSIONS: Dict[CaseStatus, List[str]] = {
    "ai_generated": ["analyst", "reviewer", "approver", "admin"],
    "under_review": ["analyst", "reviewer", "approver", "admin"],
    "edited": ["analyst", "reviewer", "admin"],
    "pending_approval": ["analyst", "reviewer", "admin"],
    "revision_requested": ["approver", "admin"],
    "approved": ["approver", "admin"],
    "rejected": ["reviewer", "approver", "admin"],
    "closed": ["approver", "admin"],
    "cancelled": ["analyst", "admin"],
}


@dataclass
class TransitionData:
    user_id: str
    user_role: str
    reason: Optional[str] = None
    evidence_reviewed: Optional[List[str]] = None
    revision_requests: Optional[List[Dict[str, str]]] = None
    assigned_approver_id: Optional[str] = None


class DecisionStateMachine:
    @staticmethod
    def can_transition(current_status: CaseStatus, target_status: CaseStatus) -> bool:
        return target_status in TRANSITIONS.get(current_status, [])

    @staticmethod
    def validate_permission(
        current_status: CaseStatus,
        target_status: CaseStatus,
        data: TransitionData,
    ) -> None:
        required_roles = ROLE_PERMISSIONS.get(target_status, [])
        if required_roles and data.user_role not in required_roles:
            raise PermissionError(
                f"Role '{data.user_role}' cannot transition to '{target_status}'"
            )

        if target_status == "approved" and data.assigned_approver_id:
            if data.user_id != data.assigned_approver_id and data.user_role != "admin":
                raise PermissionError("Only assigned approver can approve")

    @staticmethod
    def validate_business_rules(target_status: CaseStatus, data: TransitionData) -> None:
        if target_status == "approved":
            if not data.reason or len(data.reason) < 20:
                raise ValueError("Approval reason must be at least 20 characters")
            if not data.evidence_reviewed:
                raise ValueError("Must review at least one piece of evidence")
        if target_status == "rejected":
            if not data.reason or len(data.reason) < 50:
                raise ValueError("Rejection reason must be at least 50 characters")
        if target_status == "revision_requested":
            if not data.revision_requests:
                raise ValueError("Must specify at least one revision request")

    @staticmethod
    def transition(
        current_status: CaseStatus,
        target_status: CaseStatus,
        data: TransitionData,
    ) -> None:
        if not DecisionStateMachine.can_transition(current_status, target_status):
            raise ValueError(
                f"Cannot transition from {current_status} to {target_status}"
            )
        DecisionStateMachine.validate_permission(current_status, target_status, data)
        DecisionStateMachine.validate_business_rules(target_status, data)
