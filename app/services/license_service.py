from __future__ import annotations

import hashlib
import logging
import os
import platform
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from app.db.client import DBClient

logger = logging.getLogger(__name__)

class LicenseService:
    def __init__(self, db: DBClient) -> None:
        self.db = db

    async def validate(self, license_key: str, user_id: str) -> Dict[str, Any]:
        license_record = self.db.get_license_by_key(license_key, user_id)
        if not license_record:
            return {'status': 'invalid'}

        status = license_record.get('status', 'inactive')
        if status != 'active':
            self.db.record_license_check(license_record['id'], self._device_fingerprint(), status)
            return {'status': status}

        expires_at = license_record.get('expires_at')
        if expires_at:
            try:
                expires = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if expires < datetime.now(timezone.utc):
                    self.db.record_license_check(license_record['id'], self._device_fingerprint(), 'expired')
                    return {'status': 'expired'}
            except Exception as exc:
                logger.warning("License expiration parsing failed: %s", exc)

        if hasattr(self.db, 'client'):
            try:
                activations = (
                    self.db.client.table('license_activations')
                    .select('*')
                    .eq('license_id', license_record['id'])
                    .execute()
                )
                activation_rows = activations.data or []
                max_devices = license_record.get('max_devices') or 1
                device_fp = self._device_fingerprint()
                if len(activation_rows) >= max_devices:
                    if not any(a.get('device_fingerprint') == device_fp for a in activation_rows):
                        self.db.record_license_check(license_record['id'], device_fp, 'device_limit_exceeded')
                        return {'status': 'device_limit_exceeded'}
                self.db.upsert_license_activation(license_record['id'], device_fp)
            except Exception as exc:
                logger.warning("License activation enforcement failed: %s", exc)

        self.db.record_license_check(license_record['id'], self._device_fingerprint(), 'valid')
        return {'status': 'active', 'license': license_record, 'features': license_record.get('features')}

    def _device_fingerprint(self) -> str:
        machine_id = platform.node()
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0, 8 * 6, 8)][::-1])
        raw = f"{machine_id}:{mac}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()
