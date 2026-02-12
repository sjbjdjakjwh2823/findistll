import os

import pytest

from app.core.auth import get_current_user
from app.core.rbac import has_permission


def test_has_permission_matrix():
    assert has_permission("viewer", "case", "read") is True
    assert has_permission("viewer", "case", "create") is False
    assert has_permission("analyst", "case", "create") is True
    assert has_permission("reviewer", "decision", "approve") is False
    assert has_permission("approver", "decision", "approve") is True
    assert has_permission("admin", "case", "delete") is True


def test_get_current_user_defaults(monkeypatch):
    monkeypatch.delenv("RBAC_ENFORCED", raising=False)
    user = get_current_user(x_preciso_user_id=None, x_preciso_user_role=None)
    assert user.user_id == "anonymous"
    assert user.role == "viewer"


def test_get_current_user_enforced(monkeypatch):
    monkeypatch.setenv("RBAC_ENFORCED", "1")
    with pytest.raises(Exception):
        get_current_user(x_preciso_user_id=None, x_preciso_user_role=None)

    user = get_current_user(x_preciso_user_id="user-1", x_preciso_user_role="analyst")
    assert user.user_id == "user-1"
    assert user.role == "analyst"
