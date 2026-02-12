from __future__ import annotations

import os
import time
from typing import Callable, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.tenant_context import get_effective_tenant_id
from app.db.registry import get_db
from app.services.feature_flags import get_flag


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple Redis-backed fixed-window rate limiting.
    Disabled by default unless RATE_LIMIT_ENABLED=1.
    """

    def __init__(self, app) -> None:
        super().__init__(app)
        self.redis_url = os.getenv("REDIS_URL", "")
        self.limit_per_min = _env_int("RATE_LIMIT_PER_MINUTE", 60)
        self.partner_limit_per_min = _env_int("RATE_LIMIT_PARTNER_PER_MINUTE", 30)

    async def dispatch(self, request: Request, call_next: Callable):
        if not get_flag("rate_limit_enabled") or not self.redis_url:
            return await call_next(request)

        try:
            import redis  # type: ignore
        except Exception:
            return await call_next(request)

        tenant_id = get_effective_tenant_id()
        partner_key = request.headers.get("X-Partner-API-Key")
        api_key = partner_key or request.headers.get("X-API-Key") or "anonymous"
        route_group = "partner" if partner_key else "api"
        limit_per_min = self.partner_limit_per_min if partner_key else self.limit_per_min

        key = f"rl:{tenant_id}:{route_group}:{api_key}"
        now = int(time.time())
        window = now // 60
        window_key = f"{key}:{window}"

        client = redis.Redis.from_url(self.redis_url)
        count = client.incr(window_key)
        if count == 1:
            client.expire(window_key, 60)

        if count > limit_per_min:
            try:
                db = get_db()
                db.append_audit_log(
                    {
                        "event_type": "rate_limit",
                        "tenant_id": tenant_id,
                        "route_group": route_group,
                        "api_key_prefix": api_key[:8],
                        "count": count,
                        "limit_per_minute": limit_per_min,
                    }
                )
            except Exception:
                # Do not break request path, but log for ops.
                import logging
                logging.getLogger(__name__).warning("rate limit audit logging failed", exc_info=True)
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded", "limit_per_minute": limit_per_min},
            )

        return await call_next(request)
