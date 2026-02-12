from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import requests

from app.core.tenant_context import get_effective_tenant_id


class UnityCatalogService:
    def __init__(self, db: Any) -> None:
        self.db = db
        self.uc_api_url = (os.getenv("UNITY_CATALOG_API_URL") or "").rstrip("/")

    def list_policies(self) -> List[Dict[str, Any]]:
        tenant_id = get_effective_tenant_id()
        if hasattr(self.db, "client"):
            res = (
                self.db.client.table("governance_policies")
                .select("*")
                .eq("tenant_id", tenant_id)
                .order("created_at", desc=True)
                .limit(200)
                .execute()
            )
            return res.data or []
        rows = getattr(self.db, "governance_policies", []) or []
        return [r for r in rows if r.get("tenant_id") == tenant_id]

    def apply_policy(
        self,
        *,
        domain: str,
        principal: str,
        role: str,
        effect: str,
        rules: Optional[Dict[str, Any]] = None,
        requested_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        tenant_id = get_effective_tenant_id()
        row = {
            "id": str(uuid4()),
            "tenant_id": tenant_id,
            "domain": domain,
            "principal": principal,
            "role": role,
            "effect": effect,
            "rules": rules or {},
            "requested_by": requested_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        source = "db_only"
        if self.uc_api_url:
            try:
                resp = requests.post(
                    f"{self.uc_api_url}/api/2.1/unity-catalog/permissions/{domain}",
                    json={
                        "principal": principal,
                        "add": [{"privilege": role}],
                    },
                    timeout=10,
                )
                if resp.ok:
                    source = "unity_catalog"
            except Exception:
                source = "db_fallback"
        row["source"] = source

        if hasattr(self.db, "client"):
            self.db.client.table("governance_policies").insert(row).execute()
        else:
            rows = getattr(self.db, "governance_policies", None)
            if rows is None:
                rows = []
                setattr(self.db, "governance_policies", rows)
            rows.append(row)
        return row

    def list_lineage(self, limit: int = 200) -> List[Dict[str, Any]]:
        tenant_id = get_effective_tenant_id()
        if hasattr(self.db, "client"):
            res = (
                self.db.client.table("governance_lineage_events")
                .select("*")
                .eq("tenant_id", tenant_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []
        rows = getattr(self.db, "governance_lineage_events", []) or []
        return [r for r in rows if r.get("tenant_id") == tenant_id][:limit]
