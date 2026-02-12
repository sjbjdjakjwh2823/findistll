from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx


@dataclass
class _ExecResult:
    data: Any = None


def _encode_filter(op: str, value: Any) -> str:
    # PostgREST expects strings in query params; JSON is for bodies.
    if value is None:
        v = "null"
    elif isinstance(value, bool):
        v = "true" if value else "false"
    else:
        v = str(value)
    return f"{op}.{v}"


class _TableQuery:
    def __init__(self, client: "SupabaseRestClient", table: str) -> None:
        self._client = client
        self._table = table
        self._select = "*"
        self._filters: List[Tuple[str, str]] = []
        self._order: Optional[str] = None
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._payload: Any = None
        self._method: str = "GET"
        self._prefer: List[str] = []

    def select(self, columns: str = "*") -> "_TableQuery":
        self._select = columns
        self._method = "GET"
        return self

    def eq(self, column: str, value: Any) -> "_TableQuery":
        self._filters.append((column, _encode_filter("eq", value)))
        return self

    def ilike(self, column: str, pattern: str) -> "_TableQuery":
        self._filters.append((column, _encode_filter("ilike", pattern)))
        return self

    def contains(self, column: str, value: Dict[str, Any]) -> "_TableQuery":
        # JSONB contains operator in PostgREST is "cs" with JSON value.
        self._filters.append((column, f"cs.{json.dumps(value, ensure_ascii=False)}"))
        return self

    def in_(self, column: str, values: List[Any]) -> "_TableQuery":
        inner = ",".join([str(v) for v in values])
        self._filters.append((column, f"in.({inner})"))
        return self

    def or_(self, expr: str) -> "_TableQuery":
        # expr should already be PostgREST OR expression, e.g. "a.eq.1,b.eq.2"
        self._filters.append(("or", f"({expr})"))
        return self

    def order(self, column: str, desc: bool = False) -> "_TableQuery":
        self._order = f"{column}.{'desc' if desc else 'asc'}"
        return self

    def limit(self, n: int) -> "_TableQuery":
        self._limit = int(n)
        return self

    def range(self, start: int, end: int) -> "_TableQuery":
        start_i = int(start)
        end_i = int(end)
        if end_i < start_i:
            self._offset = start_i
            self._limit = 0
        else:
            self._offset = start_i
            self._limit = (end_i - start_i) + 1
        return self

    def insert(self, payload: Any, **_: Any) -> "_TableQuery":
        self._method = "POST"
        self._payload = payload
        self._prefer = ["return=representation"]
        return self

    def upsert(self, payload: Any, **_: Any) -> "_TableQuery":
        self._method = "POST"
        self._payload = payload
        self._prefer = ["return=representation", "resolution=merge-duplicates"]
        return self

    def update(self, payload: Any, **_: Any) -> "_TableQuery":
        self._method = "PATCH"
        self._payload = payload
        self._prefer = ["return=representation"]
        return self

    def delete(self, **_: Any) -> "_TableQuery":
        self._method = "DELETE"
        self._prefer = ["return=representation"]
        return self

    def execute(self) -> _ExecResult:
        url = f"{self._client.base_url}/rest/v1/{self._table}"
        params: Dict[str, str] = {}
        if self._method == "GET":
            params["select"] = self._select

        for k, v in self._filters:
            # "or" is a special param in PostgREST.
            if k == "or":
                params["or"] = v
            else:
                params[k] = v

        if self._order:
            params["order"] = self._order
        if self._limit is not None:
            params["limit"] = str(self._limit)
        if self._offset is not None:
            params["offset"] = str(self._offset)

        headers = dict(self._client.headers)
        if self._prefer:
            headers["Prefer"] = ", ".join(self._prefer)

        r = self._client._request(self._method, url, params=params, headers=headers, json_body=self._payload)
        # PostgREST returns list or dict depending on endpoint; normalize to .data
        try:
            data = r.json()
        except Exception:
            data = None
        return _ExecResult(data=data)


class _RpcQuery:
    def __init__(self, client: "SupabaseRestClient", fn: str, params: Dict[str, Any]) -> None:
        self._client = client
        self._fn = fn
        self._params = params

    def execute(self) -> _ExecResult:
        url = f"{self._client.base_url}/rest/v1/rpc/{self._fn}"
        headers = dict(self._client.headers)
        headers["Content-Type"] = "application/json"
        r = self._client._request("POST", url, params=None, headers=headers, json_body=self._params)
        try:
            data = r.json()
        except Exception:
            data = None
        return _ExecResult(data=data)


class SupabaseRestClient:
    """
    Minimal PostgREST client compatible with the small subset of supabase-py APIs
    used by Preciso. This avoids heavyweight SDK dependencies in constrained envs.
    """

    def __init__(self, base_url: str, service_role_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
        }
        self._timeout_s = float(25.0)

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, str]],
        headers: Dict[str, str],
        json_body: Any,
    ) -> httpx.Response:
        with httpx.Client(timeout=self._timeout_s) as client:
            r = client.request(method, url, params=params, headers=headers, json=json_body)
            r.raise_for_status()
            return r

    def table(self, name: str) -> _TableQuery:
        return _TableQuery(self, name)

    def rpc(self, function: str, params: Optional[dict] = None) -> _RpcQuery:
        return _RpcQuery(self, function, params or {})


def create_client(url: str, key: str) -> SupabaseRestClient:
    return SupabaseRestClient(url, key)

