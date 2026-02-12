import os
from typing import Any, Dict


class MetricsLogger:
    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if os.getenv("METRICS_LOGGING_ENABLED", "1") == "0":
            return None
        if self._client is None:
            try:
                from app.core.config import load_settings
                from app.db.tenant_scoped_client import create_tenant_aware_client
                url = os.getenv("SUPABASE_URL")
                key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                if url and key:
                    settings = load_settings()
                    self._client = create_tenant_aware_client(
                        url,
                        key,
                        default_tenant_id=settings.default_tenant_id,
                    )
            except Exception:
                self._client = None
        return self._client

    def log(self, name: str, value: float, tags: Dict[str, Any] | None = None) -> None:
        client = self._get_client()
        if not client:
            return
        payload = {
            "name": name,
            "value": float(value),
            "tags": tags or {},
        }
        client.table("perf_metrics").insert(payload).execute()
