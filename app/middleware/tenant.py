from typing import Callable, Optional

import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.tenant_context import (
    clear_tenant_id,
    get_default_tenant_id,
    sanitize_tenant_id,
    set_tenant_id,
)


_TENANT_HEADERS = (
    "x-tenant-id",
    "x-preciso-tenant",
    "x-org-id",
    "x-institution-id",
)


def _extract_tenant_id(request: Request) -> Optional[str]:
    app_env = (os.getenv("APP_ENV", "dev") or "dev").lower()
    strict_prod = app_env == "prod"
    headers = ("x-tenant-id",) if strict_prod else _TENANT_HEADERS
    for header in headers:
        value = request.headers.get(header)
        tenant_id = sanitize_tenant_id(value)
        if tenant_id:
            return tenant_id
    return None


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        tenant_required = os.getenv("TENANT_HEADER_REQUIRED", "0") == "1"
        tenant_id = _extract_tenant_id(request)
        if tenant_required and not tenant_id:
            return JSONResponse(status_code=401, content={"detail": "missing X-Tenant-Id"})
        tenant_id = tenant_id or get_default_tenant_id()
        set_tenant_id(tenant_id)
        request.state.tenant_id = tenant_id
        response = None
        try:
            response = await call_next(request)
        finally:
            clear_tenant_id()
        if response is not None:
            response.headers["X-Tenant-Id"] = tenant_id
        return response
