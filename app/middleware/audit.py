import time
import uuid
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.audit_logger import AuditLogger, AuditEntry
from app.core.auth import get_current_user

import re

_UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")


def _safe_uuid(value: str):
    if value and _UUID_RE.match(value):
        return value
    return None

class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, audit_logger: AuditLogger):
        super().__init__(app)
        self.audit_logger = audit_logger

    async def dispatch(self, request: Request, call_next: Callable):
        start_time = time.time()
        session_id = request.headers.get('X-Session-Id') or str(uuid.uuid4())
        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)

        try:
            user = get_current_user(
                x_preciso_user_id=request.headers.get('x-preciso-user-id'),
                x_preciso_user_role=request.headers.get('x-preciso-user-role'),
            )
            actor_id = _safe_uuid(user.user_id)
            actor_role = user.role
        except Exception:
            actor_id = 'anonymous'
            actor_role = None

        entry = AuditEntry(
            action=f"{request.method} {request.url.path}",
            actor_type='human',
            actor_id=actor_id,
            actor_role=actor_role,
            entity_type='api_call',
            entity_id=session_id,
            context={
                'method': request.method,
                'path': request.url.path,
                'query_params': dict(request.query_params),
                'client_ip': request.client.host if request.client else None,
                'user_agent': request.headers.get('user-agent'),
                'duration_ms': duration_ms,
                'status_code': response.status_code,
            },
            outcome={
                'success': response.status_code < 400,
            },
            session_id=session_id,
            trace_id=getattr(request.state, 'trace_id', None),
        )
        self.audit_logger.append_log(entry)
        return response
