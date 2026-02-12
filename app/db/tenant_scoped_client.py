import os
from typing import Any, Optional

from app.core.tenant_context import get_effective_tenant_id


class TenantAwareTable:
    def __init__(self, table: Any, tenant_id: Optional[str]) -> None:
        self._table = table
        self._tenant_id = tenant_id

    def _inject_tenant(self, payload: Any) -> Any:
        if not self._tenant_id:
            return payload
        if isinstance(payload, dict):
            payload.setdefault("tenant_id", self._tenant_id)
        elif isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    item.setdefault("tenant_id", self._tenant_id)
        return payload

    def _scope(self, builder: Any) -> Any:
        if self._tenant_id:
            return builder.eq("tenant_id", self._tenant_id)
        return builder

    def select(self, *args, **kwargs) -> Any:
        builder = self._table.select(*args, **kwargs)
        return self._scope(builder)

    def insert(self, payload: Any, **kwargs) -> Any:
        payload = self._inject_tenant(payload)
        return self._table.insert(payload, **kwargs)

    def upsert(self, payload: Any, **kwargs) -> Any:
        payload = self._inject_tenant(payload)
        return self._table.upsert(payload, **kwargs)

    def update(self, payload: Any, **kwargs) -> Any:
        builder = self._table.update(payload, **kwargs)
        return self._scope(builder)

    def delete(self, **kwargs) -> Any:
        builder = self._table.delete(**kwargs)
        return self._scope(builder)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._table, name)


class TenantAwareSupabaseClient:
    def __init__(self, client: Any, default_tenant_id: Optional[str] = None) -> None:
        self._client = client
        self._default_tenant_id = default_tenant_id

    def _tenant_id(self) -> str:
        return get_effective_tenant_id(self._default_tenant_id)

    def table(self, name: str) -> TenantAwareTable:
        return TenantAwareTable(self._client.table(name), self._tenant_id())

    def rpc(self, function: str, params: Optional[dict] = None) -> Any:
        return self._client.rpc(function, params or {})

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def create_tenant_aware_client(url: str, key: str, default_tenant_id: Optional[str] = None) -> TenantAwareSupabaseClient:
    mode = (os.getenv("SUPABASE_CLIENT_MODE") or "rest").strip().lower()
    client = None
    if mode == "sdk":
        try:
            from supabase import create_client as _create_client  # type: ignore
            client = _create_client(url, key)
        except Exception:
            client = None
    if client is None:
        from app.db.supabase_rest_client import create_client as _create_client
        client = _create_client(url, key)
    return TenantAwareSupabaseClient(client, default_tenant_id=default_tenant_id)
