from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.db.client import DBClient


@dataclass
class AuditEntry:
    action: str
    actor_type: str
    actor_id: Optional[str]
    entity_type: str
    entity_id: str
    context: Dict[str, Any] = field(default_factory=dict)
    outcome: Dict[str, Any] = field(default_factory=dict)
    actor_role: Optional[str] = None
    session_id: Optional[str] = None
    trace_id: Optional[str] = None


class AuditLogger:
    def __init__(self, db: DBClient) -> None:
        self.db = db
        self._last_checksum_by_session: Dict[str, str] = {}
        self._fallback_buffer: list[dict] = []

    def append_log(self, entry: AuditEntry) -> str:
        session_id = entry.session_id or str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        previous_checksum = self._last_checksum_by_session.get(session_id)
        checksum = self._compute_checksum(entry, timestamp, previous_checksum)
        log_id = str(uuid.uuid4())

        payload = {
            "id": log_id,
            "timestamp": timestamp,
            "action": entry.action,
            "actor_type": entry.actor_type,
            "actor_id": entry.actor_id,
            "actor_role": entry.actor_role,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "context": entry.context,
            "outcome": entry.outcome,
            "checksum": checksum,
            "previous_log_checksum": previous_checksum,
            "session_id": session_id,
            "trace_id": entry.trace_id,
        }
        try:
            self.db.append_audit_log(payload)
        except Exception:
            # DB may not be bootstrapped yet (e.g., Supabase schema cache missing).
            # Keep the app functional; store a small in-memory buffer for debugging.
            self._fallback_buffer.append(payload)
            if len(self._fallback_buffer) > 500:
                self._fallback_buffer = self._fallback_buffer[-200:]
        self._last_checksum_by_session[session_id] = checksum
        return log_id

    def _compute_checksum(self, entry: AuditEntry, timestamp: str, previous_checksum: Optional[str]) -> str:
        payload = {
            "timestamp": timestamp,
            "action": entry.action,
            "actor_id": entry.actor_id,
            "actor_type": entry.actor_type,
            "actor_role": entry.actor_role,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "context": entry.context,
            "outcome": entry.outcome,
            "previous_checksum": previous_checksum or "GENESIS",
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()
