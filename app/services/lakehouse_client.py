from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests

from app.core.tenant_context import get_effective_tenant_id
from app.services.feature_flags import get_flag


class LakehouseClient:
    def __init__(self, db: Any) -> None:
        self.db = db
        self.enabled = os.getenv("LAKEHOUSE_ENABLED", "0") == "1"
        self.delta_root = os.getenv("DELTA_ROOT_URI", "s3a://preciso-lakehouse")
        self.spark_api_url = (os.getenv("SPARK_API_URL") or "").rstrip("/")
        self.mlflow_tracking_uri = (os.getenv("MLFLOW_TRACKING_URI") or "").rstrip("/")
        self.uc_api_url = (os.getenv("UNITY_CATALOG_API_URL") or "").rstrip("/")
        self.minio_endpoint = (os.getenv("MINIO_ENDPOINT") or "").rstrip("/")

    def health(self) -> Dict[str, Any]:
        if not get_flag("lakehouse_enabled"):
            return {
                "enabled": False,
                "delta_root": self.delta_root,
                "spark": {"configured": False, "reachable": False},
                "mlflow": {"configured": False, "reachable": False},
                "unity_catalog": {"configured": False, "reachable": False},
                "minio": {"configured": False, "reachable": False},
                "note": "Lakehouse disabled via feature flag",
            }
        return {
            "enabled": self.enabled,
            "delta_root": self.delta_root,
            "spark": self._probe(self.spark_api_url),
            "mlflow": self._probe(self.mlflow_tracking_uri),
            "unity_catalog": self._probe(self.uc_api_url),
            "minio": self._probe(self.minio_endpoint),
        }

    def table_history(self, layer: str, table: str, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        tenant = tenant_id or get_effective_tenant_id()
        table_fqn = f"{layer}.{table}"
        if hasattr(self.db, "client"):
            res = (
                self.db.client.table("lakehouse_table_versions")
                .select("*")
                .eq("tenant_id", tenant)
                .eq("table_fqn", table_fqn)
                .order("created_at", desc=True)
                .limit(200)
                .execute()
            )
            return res.data or []
        rows = getattr(self.db, "lakehouse_table_versions", []) or []
        out = [r for r in rows if r.get("tenant_id") == tenant and r.get("table_fqn") == table_fqn]
        out.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return out

    def append_table_version(
        self,
        layer: str,
        table: str,
        *,
        delta_version: str,
        operation: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        tenant = get_effective_tenant_id()
        payload = {
            "tenant_id": tenant,
            "layer": layer,
            "table_name": table,
            "table_fqn": f"{layer}.{table}",
            "delta_version": delta_version,
            "operation": operation,
            "metadata": metadata or {},
        }
        if hasattr(self.db, "client"):
            self.db.client.table("lakehouse_table_versions").insert(payload).execute()
            return
        rows = getattr(self.db, "lakehouse_table_versions", None)
        if rows is None:
            rows = []
            setattr(self.db, "lakehouse_table_versions", rows)
        rows.append(payload)

    def time_travel_query(
        self,
        layer: str,
        table: str,
        *,
        delta_version: Optional[str] = None,
        sql: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        if not get_flag("lakehouse_enabled"):
            return {
                "table": f"{layer}.{table}",
                "delta_version": delta_version,
                "rows": [],
                "source": "disabled",
                "note": "Lakehouse disabled via feature flag",
            }
        table_fqn = f"{layer}.{table}"
        if self.spark_api_url:
            try:
                resp = requests.post(
                    f"{self.spark_api_url}/v1/time-travel-query",
                    json={
                        "table": table_fqn,
                        "delta_version": delta_version,
                        "sql": sql,
                        "limit": limit,
                        "tenant_id": get_effective_tenant_id(),
                    },
                    timeout=20,
                )
                if resp.ok:
                    payload = resp.json()
                    return {
                        "table": table_fqn,
                        "delta_version": payload.get("delta_version") or delta_version,
                        "rows": payload.get("rows") or [],
                        "source": "spark_api",
                    }
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("Spark time-travel query failed", exc_info=exc)
        return {
            "table": table_fqn,
            "delta_version": delta_version,
            "rows": [],
            "source": "local_stub",
            "note": "SPARK_API_URL not configured or unavailable.",
        }

    def _probe(self, url: str) -> Dict[str, Any]:
        if not url:
            return {"configured": False, "reachable": False}
        try:
            r = requests.get(url, timeout=3)
            return {"configured": True, "reachable": r.status_code < 500, "status_code": r.status_code}
        except Exception:
            return {"configured": True, "reachable": False}
