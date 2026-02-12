from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.tenant_context import get_effective_tenant_id


@dataclass
class OrgUser:
    tenant_id: str
    user_id: str
    email: Optional[str]
    display_name: Optional[str]
    role: str
    status: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrgService:
    """
    Enterprise org directory + role mapping.

    Single-role model (per tenant) for now:
    - org_users.user_id is TEXT and expected to match web session user id.
    """

    def __init__(self, db: Any):
        self.db = db

    def get_user(self, user_id: str, *, tenant_id: Optional[str] = None) -> Optional[OrgUser]:
        tenant_id = tenant_id or get_effective_tenant_id()
        if not user_id:
            return None
        if hasattr(self.db, "client"):
            rows = (
                self.db.client.table("org_users")
                .select("tenant_id,user_id,email,display_name,role,status")
                .eq("tenant_id", tenant_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if not rows:
                return None
            r = rows[0]
            return OrgUser(
                tenant_id=str(r.get("tenant_id") or tenant_id),
                user_id=str(r.get("user_id") or user_id),
                email=r.get("email"),
                display_name=r.get("display_name"),
                role=str(r.get("role") or "viewer"),
                status=str(r.get("status") or "active"),
            )

        # In-memory fallback
        store: Dict[str, Dict[str, Any]] = getattr(self.db, "org_users", {}) or {}
        r = store.get(f"{tenant_id}:{user_id}")
        if not r:
            return None
        return OrgUser(
            tenant_id=tenant_id,
            user_id=user_id,
            email=r.get("email"),
            display_name=r.get("display_name"),
            role=str(r.get("role") or "viewer"),
            status=str(r.get("status") or "active"),
        )

    def resolve_role(self, user_id: str, *, tenant_id: Optional[str] = None) -> Optional[str]:
        u = self.get_user(user_id, tenant_id=tenant_id)
        if not u:
            return None
        if u.status != "active":
            return "viewer"
        return u.role or "viewer"

    def upsert_user(
        self,
        *,
        user_id: str,
        role: str,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
        status: str = "active",
        tenant_id: Optional[str] = None,
    ) -> OrgUser:
        tenant_id = tenant_id or get_effective_tenant_id()
        payload = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "email": email,
            "display_name": display_name,
            "role": role,
            "status": status,
            "updated_at": _utc_now_iso(),
        }
        if hasattr(self.db, "client"):
            # Supabase upsert by unique constraint (tenant_id,user_id)
            self.db.client.table("org_users").upsert(payload, on_conflict="tenant_id,user_id").execute()
            u = self.get_user(user_id, tenant_id=tenant_id)
            if u:
                return u
        else:
            store: Dict[str, Dict[str, Any]] = getattr(self.db, "org_users", None)
            if store is None:
                self.db.org_users = {}
                store = self.db.org_users
            store[f"{tenant_id}:{user_id}"] = payload

        return OrgUser(
            tenant_id=tenant_id,
            user_id=user_id,
            email=email,
            display_name=display_name,
            role=role,
            status=status,
        )

    def list_users(self, *, tenant_id: Optional[str] = None, limit: int = 200) -> list[OrgUser]:
        tenant_id = tenant_id or get_effective_tenant_id()
        if hasattr(self.db, "client"):
            rows = (
                self.db.client.table("org_users")
                .select("tenant_id,user_id,email,display_name,role,status,updated_at")
                .eq("tenant_id", tenant_id)
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
                .data
                or []
            )
            out: list[OrgUser] = []
            for r in rows:
                out.append(
                    OrgUser(
                        tenant_id=str(r.get("tenant_id") or tenant_id),
                        user_id=str(r.get("user_id") or ""),
                        email=r.get("email"),
                        display_name=r.get("display_name"),
                        role=str(r.get("role") or "viewer"),
                        status=str(r.get("status") or "active"),
                    )
                )
            return out

        store: Dict[str, Dict[str, Any]] = getattr(self.db, "org_users", {}) or {}
        out = []
        for key, r in store.items():
            if not key.startswith(f"{tenant_id}:"):
                continue
            out.append(
                OrgUser(
                    tenant_id=tenant_id,
                    user_id=str(r.get("user_id") or ""),
                    email=r.get("email"),
                    display_name=r.get("display_name"),
                    role=str(r.get("role") or "viewer"),
                    status=str(r.get("status") or "active"),
                )
            )
        return out[:limit]

