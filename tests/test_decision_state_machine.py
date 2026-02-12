import pytest

from app.services.decision_state_machine import DecisionStateMachine, TransitionData


def test_valid_transition():
    data = TransitionData(user_id="u1", user_role="analyst")
    DecisionStateMachine.transition("draft", "ai_generated", data)


def test_invalid_transition():
    data = TransitionData(user_id="u1", user_role="analyst")
    with pytest.raises(ValueError):
        DecisionStateMachine.transition("draft", "approved", data)


def test_permission_denied():
    data = TransitionData(user_id="u1", user_role="viewer")
    with pytest.raises(PermissionError):
        DecisionStateMachine.transition("draft", "ai_generated", data)


def test_approval_requires_reason_and_evidence():
    data = TransitionData(user_id="u1", user_role="approver")
    with pytest.raises(ValueError):
        DecisionStateMachine.transition("pending_approval", "approved", data)

    data = TransitionData(
        user_id="u1",
        user_role="approver",
        reason="This is a valid approval reason.",
        evidence_reviewed=["e1"],
    )
    DecisionStateMachine.transition("pending_approval", "approved", data)
