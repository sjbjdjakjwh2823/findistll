import os
import re
from contextvars import ContextVar
from typing import Optional

_TENANT_ID: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)
_TENANT_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def get_default_tenant_id() -> str:
    return os.getenv("DEFAULT_TENANT_ID", "public")


def sanitize_tenant_id(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if not _TENANT_ID_RE.match(candidate):
        return None
    return candidate


def set_tenant_id(tenant_id: Optional[str]) -> None:
    _TENANT_ID.set(tenant_id)


def get_tenant_id() -> Optional[str]:
    return _TENANT_ID.get()


def get_effective_tenant_id(default: Optional[str] = None) -> str:
    return get_tenant_id() or default or get_default_tenant_id()


def clear_tenant_id() -> None:
    _TENANT_ID.set(None)
