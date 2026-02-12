import os
import time
from typing import Callable, Dict

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.license_service import LicenseService
from app.services.feature_flags import get_flag


class LicenseGuard(BaseHTTPMiddleware):
    EXEMPT_PATHS = {
        '/health',
        '/api/license/validate',
        '/api/license/status',
    }

    def __init__(self, app, license_service: LicenseService, cache_ttl: int = 300):
        super().__init__(app)
        self.license_service = license_service
        self.cache_ttl = cache_ttl
        self.cache: Dict[str, Dict[str, float]] = {}

    async def dispatch(self, request: Request, call_next: Callable):
        if not get_flag("license_check_enabled"):
            return await call_next(request)

        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        license_key = os.getenv('LICENSE_KEY') or request.headers.get('x-preciso-license-key')
        user_id = request.headers.get('x-preciso-user-id', 'anonymous')
        if not license_key:
            raise HTTPException(status_code=401, detail='Missing license key')

        cache_key = f'{user_id}:{license_key}'
        cached = self.cache.get(cache_key)
        now = time.time()
        if cached and (now - cached['timestamp']) < self.cache_ttl:
            if cached['status'] != 'active':
                raise HTTPException(status_code=403, detail=f"License is {cached['status']}")
        else:
            result = await self.license_service.validate(license_key, user_id)
            self.cache[cache_key] = {
                'status': result['status'],
                'timestamp': now,
            }
            if result['status'] != 'active':
                raise HTTPException(status_code=403, detail=f"License is {result['status']}")

        return await call_next(request)
