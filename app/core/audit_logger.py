
import os
import re
import logging
from copy import deepcopy
from datetime import datetime
import json
from uuid import uuid5, NAMESPACE_URL
from typing import Any, Optional

logger = logging.getLogger(__name__)

class AuditLogger:
    _local_logs = []

    def __init__(self):
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        self.supabase: Optional[Any] = None

        if not self.supabase_url or not self.supabase_key:
            logger.warning("AuditLogger running without Supabase credentials; logs will be stored locally only.")
        else:
            self.supabase = self._create_client(self.supabase_url, self.supabase_key)
        self.table_name = "audit_logs"

    def _create_client(self, url: str, key: str) -> Any:
        mode = (os.getenv("SUPABASE_CLIENT_MODE") or "rest").strip().lower()
        if mode == "sdk":
            try:
                from supabase import create_client as _create_client  # type: ignore
                return _create_client(url, key)
            except Exception as exc:
                logger.warning("Supabase SDK init failed; falling back to REST client.", exc_info=exc)
        from app.db.supabase_rest_client import create_client as _create_client
        return _create_client(url, key)

    def log_action(
        self,
        actor_type: str,
        actor_id: str,
        action_type: str,
        entity_type: str,
        entity_id: str,
        details: dict = None
    ):
        """
        Logs an auditable action to Supabase.

        Args:
            actor_type (str): Type of the entity performing the action (e.g., 'human', 'ai', 'system').
            actor_id (str): Identifier of the entity performing the action.
            action_type (str): The type of action performed (e.g., 'create', 'read', 'update', 'delete', 'login').
            entity_type (str): The type of entity being acted upon (e.g., 'user', 'document', 'model', 'configuration').
            entity_id (str): The identifier of the entity being acted upon.
            details (dict, optional): Additional JSON details about the action,
                                       e.g., {'old_value': '...', 'new_value': '...'} or {'query_params': '...'}.
                                       Defaults to None.
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "actor_type": actor_type,
            "actor_id": actor_id,
            "action_type": action_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details if details is not None else {},
            "is_immutable": True  # Explicitly mark as immutable
        }
        # Always keep a local copy for resilience in test/dev environments
        self._local_logs.append(deepcopy(log_entry))
        self._insert_with_fallback(log_entry, store_local=False)

    def _insert_with_fallback(self, log_entry: dict, store_local: bool = True):
        """
        Insert log entry with compatibility fallbacks for legacy schemas.
        - If a column is missing, move it into details and retry.
        - If UUID type mismatch occurs, store a deterministic UUID and keep
          original string in details for reverse mapping.
        """
        attempts = 0
        while attempts < 3:
            try:
                if self.supabase is None:
                    return
                response = self.supabase.table(self.table_name).insert(log_entry).execute()
                response.data
                return
            except Exception as e:
                msg = self._extract_error_message(e)
                # Missing column in schema cache (legacy schema)
                missing_col = self._extract_missing_column(msg)
                if missing_col and missing_col in log_entry:
                    details = dict(log_entry.get("details") or {})
                    details[f"_legacy_{missing_col}"] = log_entry[missing_col]
                    log_entry = {k: v for k, v in log_entry.items() if k != missing_col}
                    log_entry["details"] = details
                    attempts += 1
                    continue

                # UUID mismatch: attempt deterministic UUID + store original string
                if "invalid input syntax for type uuid" in msg:
                    details = dict(log_entry.get("details") or {})
                    if "actor_id" in log_entry:
                        details["_actor_id_text"] = log_entry["actor_id"]
                        log_entry["actor_id"] = str(uuid5(NAMESPACE_URL, log_entry["actor_id"]))
                    if "entity_id" in log_entry:
                        details["_entity_id_text"] = log_entry["entity_id"]
                        log_entry["entity_id"] = str(uuid5(NAMESPACE_URL, log_entry["entity_id"]))
                    log_entry["details"] = details
                    attempts += 1
                    continue

                # As a last resort, try minimal insert
                minimal = {
                    "timestamp": log_entry.get("timestamp"),
                    "details": log_entry.get("details") or {},
                    "is_immutable": log_entry.get("is_immutable", True),
                }
                for key in ("actor_id", "entity_id"):
                    if key in log_entry:
                        minimal[key] = log_entry[key]
                try:
                    response = self.supabase.table(self.table_name).insert(minimal).execute()
                    response.data
                    return
                except Exception as e2:
                    print(f"Error logging audit action: {e2}")
                    if store_local:
                        self._local_logs.append(log_entry)
                    return
        print("Error logging audit action: exceeded retry attempts")
        if store_local:
            self._local_logs.append(log_entry)

    @staticmethod
    def _extract_missing_column(error_str: str):
        if not error_str:
            return None
        match = re.search(r"Could not find the ['\"]([^'\"]+)['\"] column", error_str)
        return match.group(1) if match else None

    @staticmethod
    def _extract_error_message(error: Exception) -> str:
        if hasattr(error, "message"):
            return str(getattr(error, "message"))
        if hasattr(error, "args") and error.args:
            if isinstance(error.args[0], dict) and "message" in error.args[0]:
                return str(error.args[0]["message"])
            return str(error.args[0])
        return str(error)

    @staticmethod
    def _normalize_row(row: dict):
        details = row.get("details") or {}
        # Restore legacy fields from details if missing
        for key in ("action_type", "actor_type", "entity_type"):
            legacy_key = f"_legacy_{key}"
            if key not in row and legacy_key in details:
                row[key] = details.get(legacy_key)
        # Restore text IDs if UUIDs were stored
        if "_actor_id_text" in details:
            row["actor_id"] = details["_actor_id_text"]
        if "_entity_id_text" in details:
            row["entity_id"] = details["_entity_id_text"]
        return row

    def get_audit_logs(self, limit: int = 100, offset: int = 0):
        """
        Retrieves audit logs.

        Args:
            limit (int): Maximum number of logs to retrieve.
            offset (int): Offset for pagination.

        Returns:
            list: A list of audit log entries.
        """
        try:
            response = self.supabase.table(self.table_name).select("*").order("timestamp", desc=True).limit(limit).offset(offset).execute()
            rows = [self._normalize_row(row) for row in response.data]
            if rows:
                return rows
            return list(reversed(self._local_logs))[:limit]
        except Exception as e:
            print(f"Error retrieving audit logs: {e}")
            return list(reversed(self._local_logs))[:limit]

    def get_audit_logs_by_actor(self, actor_id: str, actor_type: str = None, limit: int = 100, offset: int = 0):
        """
        Retrieves audit logs filtered by actor_id and optionally actor_type.
        """
        try:
            query = self.supabase.table(self.table_name).select("*")
            query = query.eq("actor_id", actor_id)
            if actor_type:
                query = query.eq("actor_type", actor_type)
            response = query.order("timestamp", desc=True).limit(limit).offset(offset).execute()
            rows = [self._normalize_row(row) for row in response.data]
            if rows:
                return rows
            return [r for r in reversed(self._local_logs) if r.get("actor_id") == actor_id and (not actor_type or r.get("actor_type") == actor_type)][:limit]
        except Exception as e:
            err = str(e)
            print(f"Error retrieving audit logs by actor: {e}")
            # Fallback: fetch recent logs and filter client-side
            if "invalid input syntax for type uuid" in err:
                try:
                    response = self.supabase.table(self.table_name).select("*").order("timestamp", desc=True).limit(limit).offset(offset).execute()
                    rows = [self._normalize_row(row) for row in response.data]
                    filtered = [r for r in rows if r.get("actor_id") == actor_id and (not actor_type or r.get("actor_type") == actor_type)]
                    if filtered:
                        return filtered
                except Exception as e2:
                    print(f"Error retrieving audit logs by actor (fallback): {e2}")
            return [r for r in reversed(self._local_logs) if r.get("actor_id") == actor_id and (not actor_type or r.get("actor_type") == actor_type)][:limit]

    def get_audit_logs_by_entity(self, entity_id: str, entity_type: str = None, limit: int = 100, offset: int = 0):
        """
        Retrieves audit logs filtered by entity_id and optionally entity_type.
        """
        try:
            query = self.supabase.table(self.table_name).select("*")
            query = query.eq("entity_id", entity_id)
            if entity_type:
                query = query.eq("entity_type", entity_type)
            response = query.order("timestamp", desc=True).limit(limit).offset(offset).execute()
            rows = [self._normalize_row(row) for row in response.data]
            if rows:
                return rows
            return [r for r in reversed(self._local_logs) if r.get("entity_id") == entity_id and (not entity_type or r.get("entity_type") == entity_type)][:limit]
        except Exception as e:
            err = str(e)
            print(f"Error retrieving audit logs by entity: {e}")
            # Fallback: fetch recent logs and filter client-side
            if "invalid input syntax for type uuid" in err:
                try:
                    response = self.supabase.table(self.table_name).select("*").order("timestamp", desc=True).limit(limit).offset(offset).execute()
                    rows = [self._normalize_row(row) for row in response.data]
                    filtered = [r for r in rows if r.get("entity_id") == entity_id and (not entity_type or r.get("entity_type") == entity_type)]
                    if filtered:
                        return filtered
                except Exception as e2:
                    print(f"Error retrieving audit logs by entity (fallback): {e2}")
            return [r for r in reversed(self._local_logs) if r.get("entity_id") == entity_id and (not entity_type or r.get("entity_type") == entity_type)][:limit]
