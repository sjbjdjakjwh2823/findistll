import time
import logging
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.metrics_logger import MetricsLogger

logger = logging.getLogger(__name__)

class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Lightweight request latency/status metrics.
    Stores data in perf_metrics (Supabase) when available.
    """

    async def dispatch(self, request: Request, call_next: Callable):
        start = time.time()
        response = await call_next(request)
        latency_ms = int((time.time() - start) * 1000)

        try:
            MetricsLogger().log(
                "http.request_latency_ms",
                latency_ms,
                {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                },
            )
            MetricsLogger().log(
                "http.request_count",
                1,
                {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                },
            )
        except Exception as exc:
            # Metrics must never affect request outcomes.
            logger.warning("metrics logging failed", exc_info=exc)

        return response
