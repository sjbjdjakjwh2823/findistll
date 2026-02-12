"""
RBAC helper utilities.
"""

from typing import Dict, Tuple

ROLE_HIERARCHY = ["viewer", "analyst", "reviewer", "approver", "admin"]

PERMISSIONS: Dict[Tuple[str, str], list] = {
    ("case", "read"): ["viewer", "analyst", "reviewer", "approver", "admin"],
    ("case", "create"): ["analyst", "reviewer", "approver", "admin"],
    ("case", "update"): ["analyst", "reviewer", "approver", "admin"],
    ("decision", "create"): ["analyst", "reviewer", "approver", "admin"],
    ("decision", "approve"): ["approver", "admin"],
    ("decision", "reject"): ["reviewer", "approver", "admin"],
}


def has_permission(role: str, resource: str, action: str) -> bool:
    roles = PERMISSIONS.get((resource, action), [])
    return role in roles or role == "admin"
