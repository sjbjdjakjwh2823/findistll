import uuid
from contextvars import ContextVar
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

trace_id_var: ContextVar[str] = ContextVar('trace_id', default='')


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        trace_id = request.headers.get('X-Trace-Id') or str(uuid.uuid4())
        trace_id_var.set(trace_id)
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers['X-Trace-Id'] = trace_id
        return response
