from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)
        if request.method == "GET" and request.url.path.startswith("/ui/"):
            response.headers.setdefault(
                "Cache-Control",
                "public, max-age=3600, s-maxage=86400, stale-while-revalidate=600",
            )
        return response
