from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.tenant_context import get_effective_tenant_id


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EnterpriseCollabStore:
    """
    Backend-agnostic collaboration + tenant pipeline store.
    Supports:
    - InMemoryDB
    - SupabaseDB (tenant-aware client)
    - PostgresDB (direct SQL helpers)
    """

    def __init__(self, db: Any):
        self.db = db
        self.kind = self._detect_backend(db)
        if self.kind == "memory":
            self._ensure_memory_schema()
        if self.kind == "postgres":
            self._ensure_postgres_schema()

    @staticmethod
    def _detect_backend(db: Any) -> str:
        if hasattr(db, "client"):
            return "supabase"
        if hasattr(db, "_fetchone") and hasattr(db, "_execute"):
            return "postgres"
        return "memory"

    @staticmethod
    def _tenant_id() -> str:
        return get_effective_tenant_id()

    # -------------------------------------------------------------------------
    # Schema bootstrap
    # -------------------------------------------------------------------------
    def _ensure_memory_schema(self) -> None:
        if not hasattr(self.db, "org_users"):
            # org directory store: key = "{tenant_id}:{user_id}"
            self.db.org_users = {}
        if not hasattr(self.db, "collab_contacts"):
            self.db.collab_contacts = []
        if not hasattr(self.db, "collab_invites"):
            self.db.collab_invites = []
        if not hasattr(self.db, "collab_teams"):
            self.db.collab_teams = []
        if not hasattr(self.db, "collab_team_members"):
            self.db.collab_team_members = []
        if not hasattr(self.db, "collab_spaces"):
            self.db.collab_spaces = []
        if not hasattr(self.db, "collab_files"):
            self.db.collab_files = []
        if not hasattr(self.db, "collab_file_acl"):
            self.db.collab_file_acl = []
        if not hasattr(self.db, "collab_transfers"):
            self.db.collab_transfers = []
        if not hasattr(self.db, "tenant_pipeline_profiles"):
            self.db.tenant_pipeline_profiles = []
        if not hasattr(self.db, "tenant_pipeline_quotas"):
            self.db.tenant_pipeline_quotas = []
        if not hasattr(self.db, "pipeline_jobs"):
            self.db.pipeline_jobs = []

    def _ensure_postgres_schema(self) -> None:
        sql = """
        CREATE TABLE IF NOT EXISTS org_users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL DEFAULT 'public',
            user_id TEXT NOT NULL,
            rbac_user_id TEXT,
            display_name TEXT,
            email TEXT,
            role TEXT NOT NULL DEFAULT 'viewer',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (tenant_id, user_id)
        );
        ALTER TABLE org_users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'viewer';
        ALTER TABLE org_users ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';
        CREATE INDEX IF NOT EXISTS idx_org_users_tenant_user ON org_users(tenant_id, user_id);

        CREATE TABLE IF NOT EXISTS collab_contacts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL DEFAULT 'public',
            requester_user_id TEXT NOT NULL,
            target_user_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_collab_contacts_tenant_req ON collab_contacts(tenant_id, requester_user_id);
        CREATE INDEX IF NOT EXISTS idx_collab_contacts_tenant_tgt ON collab_contacts(tenant_id, target_user_id);

        CREATE TABLE IF NOT EXISTS collab_invites (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL DEFAULT 'public',
            code TEXT NOT NULL,
            requester_user_id TEXT NOT NULL,
            target_user_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (tenant_id, code)
        );
        CREATE INDEX IF NOT EXISTS idx_collab_invites_tenant_code ON collab_invites(tenant_id, code);

        CREATE TABLE IF NOT EXISTS collab_teams (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL DEFAULT 'public',
            name TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_collab_teams_tenant_owner ON collab_teams(tenant_id, owner_user_id);

        CREATE TABLE IF NOT EXISTS collab_team_members (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL DEFAULT 'public',
            team_id UUID NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (tenant_id, team_id, user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_collab_team_members_tenant_user ON collab_team_members(tenant_id, user_id);

        CREATE TABLE IF NOT EXISTS collab_spaces (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL DEFAULT 'public',
            type TEXT NOT NULL DEFAULT 'personal',
            owner_user_id TEXT,
            team_id UUID,
            name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_collab_spaces_tenant_owner ON collab_spaces(tenant_id, owner_user_id);
        CREATE INDEX IF NOT EXISTS idx_collab_spaces_tenant_team ON collab_spaces(tenant_id, team_id);

        CREATE TABLE IF NOT EXISTS collab_files (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL DEFAULT 'public',
            space_id UUID NOT NULL,
            owner_user_id TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            version INT NOT NULL DEFAULT 1,
            visibility TEXT NOT NULL DEFAULT 'private',
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_collab_files_tenant_space ON collab_files(tenant_id, space_id);
        CREATE INDEX IF NOT EXISTS idx_collab_files_tenant_owner ON collab_files(tenant_id, owner_user_id);

        CREATE TABLE IF NOT EXISTS collab_file_acl (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL DEFAULT 'public',
            file_id UUID NOT NULL,
            principal_type TEXT NOT NULL,
            principal_id TEXT NOT NULL,
            permission TEXT NOT NULL DEFAULT 'read',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_collab_file_acl_tenant_file ON collab_file_acl(tenant_id, file_id);

        CREATE TABLE IF NOT EXISTS collab_transfers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL DEFAULT 'public',
            sender_user_id TEXT NOT NULL,
            receiver_user_id TEXT NOT NULL,
            file_id UUID NOT NULL,
            message TEXT,
            status TEXT NOT NULL DEFAULT 'sent',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_collab_transfers_tenant_receiver ON collab_transfers(tenant_id, receiver_user_id);

        CREATE TABLE IF NOT EXISTS tenant_pipeline_profiles (
            tenant_id TEXT PRIMARY KEY,
            rag_profile_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            llm_profile_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            rate_limits_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS tenant_pipeline_quotas (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            day DATE NOT NULL,
            rag_queries INT NOT NULL DEFAULT 0,
            llm_tokens BIGINT NOT NULL DEFAULT 0,
            ingest_docs INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (tenant_id, user_id, day)
        );
        CREATE INDEX IF NOT EXISTS idx_tenant_pipeline_quotas_tenant_user_day ON tenant_pipeline_quotas(tenant_id, user_id, day);

        CREATE TABLE IF NOT EXISTS pipeline_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL DEFAULT 'public',
            user_id TEXT NOT NULL,
            job_type TEXT NOT NULL,
            priority INT NOT NULL DEFAULT 10,
            status TEXT NOT NULL DEFAULT 'pending',
            input_ref JSONB NOT NULL DEFAULT '{}'::jsonb,
            output_ref JSONB NOT NULL DEFAULT '{}'::jsonb,
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_tenant_status ON pipeline_jobs(tenant_id, status, priority, created_at);
        """
        self.db._execute(sql)

    # -------------------------------------------------------------------------
    # Generic small helpers
    # -------------------------------------------------------------------------
    def _audit(self, action: str, actor_id: str, context: Optional[Dict[str, Any]] = None) -> None:
        payload = {
            "event_type": "collab_event",
            "payload": {
                "action": action,
                "context": context or {},
                "at": _utc_now_iso(),
            },
            "actor_id": actor_id,
        }
        try:
            self.db.append_audit_log(payload)
        except Exception:
            # Never block business flow on audit failures.
            return

    @staticmethod
    def _id() -> str:
        return str(uuid.uuid4())

    # -------------------------------------------------------------------------
    # Policy helpers (role-based visibility)
    # -------------------------------------------------------------------------
    @staticmethod
    def _normalize_role(role: Optional[str]) -> str:
        r = (role or "viewer").strip().lower()
        if r in {"approver"}:
            return "reviewer"
        if r in {"auditor"}:
            return "auditor"
        return r or "viewer"

    # -------------------------------------------------------------------------
    # Org users
    # -------------------------------------------------------------------------
    def ensure_org_user(self, *, user_id: str, display_name: Optional[str] = None, email: Optional[str] = None) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        if self.kind == "memory":
            key = f"{tenant_id}:{user_id}"
            existing = self.db.org_users.get(key)
            if existing:
                return existing
            row = {
                "id": self._id(),
                "tenant_id": tenant_id,
                "user_id": user_id,
                "rbac_user_id": user_id,
                "display_name": display_name or user_id,
                "email": email,
                "role": "viewer",
                "status": "active",
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            }
            self.db.org_users[key] = row
            return row
        if self.kind == "supabase":
            existing = (
                self.db.client.table("org_users")
                .select("*")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            ).data or []
            if existing:
                return existing[0]
            payload = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "rbac_user_id": user_id,
                "display_name": display_name or user_id,
                "email": email,
                "status": "active",
            }
            inserted = self.db.client.table("org_users").insert(payload).execute().data or []
            return inserted[0] if inserted else payload
        existing = self.db._fetchone(
            "SELECT * FROM org_users WHERE tenant_id=%s AND user_id=%s LIMIT 1",
            (tenant_id, user_id),
        )
        if existing:
            return existing
        sql = """
        INSERT INTO org_users (tenant_id, user_id, rbac_user_id, display_name, email, status)
        VALUES (%s, %s, %s, %s, %s, 'active')
        """
        self.db._execute(sql, (tenant_id, user_id, user_id, display_name or user_id, email))
        return self.db._fetchone(
            "SELECT * FROM org_users WHERE tenant_id=%s AND user_id=%s LIMIT 1",
            (tenant_id, user_id),
        ) or {}

    # -------------------------------------------------------------------------
    # Contacts (friends)
    # -------------------------------------------------------------------------
    def request_contact(self, *, requester_user_id: str, target_user_id: str) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        if requester_user_id == target_user_id:
            raise ValueError("cannot request self")

        self.ensure_org_user(user_id=requester_user_id)
        self.ensure_org_user(user_id=target_user_id)

        if self.kind == "memory":
            for r in self.db.collab_contacts:
                if r["tenant_id"] != tenant_id:
                    continue
                pair = {r["requester_user_id"], r["target_user_id"]}
                if pair == {requester_user_id, target_user_id} and r["status"] in {"pending", "accepted"}:
                    return r
            row = {
                "id": self._id(),
                "tenant_id": tenant_id,
                "requester_user_id": requester_user_id,
                "target_user_id": target_user_id,
                "status": "pending",
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            }
            self.db.collab_contacts.append(row)
            self._audit("friend_request", requester_user_id, {"contact_id": row["id"], "target": target_user_id})
            return row

        if self.kind == "supabase":
            existing = (
                self.db.client.table("collab_contacts")
                .select("*")
                .eq("requester_user_id", requester_user_id)
                .eq("target_user_id", target_user_id)
                .limit(1)
                .execute()
            ).data or []
            if existing and existing[0].get("status") in {"pending", "accepted"}:
                return existing[0]
            reverse = (
                self.db.client.table("collab_contacts")
                .select("*")
                .eq("requester_user_id", target_user_id)
                .eq("target_user_id", requester_user_id)
                .limit(1)
                .execute()
            ).data or []
            if reverse and reverse[0].get("status") in {"pending", "accepted"}:
                return reverse[0]
            payload = {
                "tenant_id": tenant_id,
                "requester_user_id": requester_user_id,
                "target_user_id": target_user_id,
                "status": "pending",
            }
            row = self.db.client.table("collab_contacts").insert(payload).execute().data or [payload]
            self._audit("friend_request", requester_user_id, {"target": target_user_id})
            return row[0]

        existing = self.db._fetchone(
            """
            SELECT * FROM collab_contacts
            WHERE tenant_id=%s
              AND ((requester_user_id=%s AND target_user_id=%s) OR (requester_user_id=%s AND target_user_id=%s))
              AND status IN ('pending', 'accepted')
            LIMIT 1
            """,
            (tenant_id, requester_user_id, target_user_id, target_user_id, requester_user_id),
        )
        if existing:
            return existing
        self.db._execute(
            """
            INSERT INTO collab_contacts (tenant_id, requester_user_id, target_user_id, status)
            VALUES (%s, %s, %s, 'pending')
            """,
            (tenant_id, requester_user_id, target_user_id),
        )
        self._audit("friend_request", requester_user_id, {"target": target_user_id})
        return self.db._fetchone(
            """
            SELECT * FROM collab_contacts
            WHERE tenant_id=%s AND requester_user_id=%s AND target_user_id=%s
            ORDER BY created_at DESC LIMIT 1
            """,
            (tenant_id, requester_user_id, target_user_id),
        ) or {}

    def accept_contact(self, *, current_user_id: str, contact_id: str) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        if self.kind == "memory":
            for r in self.db.collab_contacts:
                if r["tenant_id"] == tenant_id and r["id"] == contact_id:
                    if r["target_user_id"] != current_user_id:
                        raise PermissionError("only target can accept")
                    r["status"] = "accepted"
                    r["updated_at"] = _utc_now_iso()
                    self._audit("friend_accept", current_user_id, {"contact_id": contact_id})
                    return r
            raise KeyError("contact not found")
        if self.kind == "supabase":
            rows = (
                self.db.client.table("collab_contacts")
                .select("*")
                .eq("id", contact_id)
                .limit(1)
                .execute()
            ).data or []
            if not rows:
                raise KeyError("contact not found")
            row = rows[0]
            if row.get("target_user_id") != current_user_id:
                raise PermissionError("only target can accept")
            updated = (
                self.db.client.table("collab_contacts")
                .update({"status": "accepted", "updated_at": _utc_now_iso()})
                .eq("id", contact_id)
                .execute()
            ).data or []
            self._audit("friend_accept", current_user_id, {"contact_id": contact_id})
            return updated[0] if updated else row
        row = self.db._fetchone(
            "SELECT * FROM collab_contacts WHERE tenant_id=%s AND id=%s LIMIT 1",
            (tenant_id, contact_id),
        )
        if not row:
            raise KeyError("contact not found")
        if row.get("target_user_id") != current_user_id:
            raise PermissionError("only target can accept")
        self.db._execute(
            "UPDATE collab_contacts SET status='accepted', updated_at=NOW() WHERE tenant_id=%s AND id=%s",
            (tenant_id, contact_id),
        )
        self._audit("friend_accept", current_user_id, {"contact_id": contact_id})
        return self.db._fetchone(
            "SELECT * FROM collab_contacts WHERE tenant_id=%s AND id=%s LIMIT 1",
            (tenant_id, contact_id),
        ) or {}

    def list_contacts(self, *, current_user_id: str) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        if self.kind == "memory":
            return [
                r
                for r in self.db.collab_contacts
                if r["tenant_id"] == tenant_id and (r["requester_user_id"] == current_user_id or r["target_user_id"] == current_user_id)
            ]
        if self.kind == "supabase":
            req = (
                self.db.client.table("collab_contacts")
                .select("*")
                .eq("requester_user_id", current_user_id)
                .execute()
            ).data or []
            tgt = (
                self.db.client.table("collab_contacts")
                .select("*")
                .eq("target_user_id", current_user_id)
                .execute()
            ).data or []
            dedup: Dict[str, Dict[str, Any]] = {}
            for row in req + tgt:
                dedup[str(row.get("id"))] = row
            return list(dedup.values())
        return self.db._fetchall(
            """
            SELECT * FROM collab_contacts
            WHERE tenant_id=%s AND (requester_user_id=%s OR target_user_id=%s)
            ORDER BY created_at DESC
            """,
            (tenant_id, current_user_id, current_user_id),
        )

    def are_friends(self, *, user_a: str, user_b: str) -> bool:
        for row in self.list_contacts(current_user_id=user_a):
            pair = {row.get("requester_user_id"), row.get("target_user_id")}
            if pair == {user_a, user_b} and row.get("status") == "accepted":
                return True
        return False

    # -------------------------------------------------------------------------
    # Invite codes
    # -------------------------------------------------------------------------
    def _invite_code(self) -> str:
        return uuid.uuid4().hex[:10]

    def create_invite(self, *, requester_user_id: str, target_user_id: Optional[str] = None) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        self.ensure_org_user(user_id=requester_user_id)
        if target_user_id:
            self.ensure_org_user(user_id=target_user_id)

        code = self._invite_code()
        row = {
            "id": self._id(),
            "tenant_id": tenant_id,
            "code": code,
            "requester_user_id": requester_user_id,
            "target_user_id": target_user_id,
            "status": "pending",
            "expires_at": None,
            "created_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
        }
        if self.kind == "memory":
            self.db.collab_invites.append(row)
            self._audit("invite_create", requester_user_id, {"code": code, "target": target_user_id})
            return row
        if self.kind == "supabase":
            inserted = self.db.client.table("collab_invites").insert(row).execute().data or [row]
            self._audit("invite_create", requester_user_id, {"code": code, "target": target_user_id})
            return inserted[0]
        self.db._execute(
            """
            INSERT INTO collab_invites
            (id, tenant_id, code, requester_user_id, target_user_id, status, expires_at)
            VALUES (%s, %s, %s, %s, %s, 'pending', %s)
            """,
            (row["id"], tenant_id, code, requester_user_id, target_user_id, None),
        )
        self._audit("invite_create", requester_user_id, {"code": code, "target": target_user_id})
        return self.db._fetchone(
            "SELECT * FROM collab_invites WHERE tenant_id=%s AND code=%s LIMIT 1",
            (tenant_id, code),
        ) or row

    def accept_invite(self, *, current_user_id: str, code: str) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        if self.kind == "memory":
            for inv in self.db.collab_invites:
                if inv["tenant_id"] == tenant_id and inv["code"] == code and inv["status"] == "pending":
                    if inv.get("target_user_id") and inv.get("target_user_id") != current_user_id:
                        raise PermissionError("invite target mismatch")
                    inv["status"] = "accepted"
                    inv["updated_at"] = _utc_now_iso()
                    self.request_contact(requester_user_id=inv["requester_user_id"], target_user_id=current_user_id)
                    accepted = self.list_contacts(current_user_id=current_user_id)
                    if accepted:
                        self.accept_contact(current_user_id=current_user_id, contact_id=accepted[-1]["id"])
                    self._audit("invite_accept", current_user_id, {"code": code})
                    return inv
            raise KeyError("invite not found")
        if self.kind == "supabase":
            rows = (
                self.db.client.table("collab_invites")
                .select("*")
                .eq("code", code)
                .limit(1)
                .execute()
            ).data or []
            if not rows:
                raise KeyError("invite not found")
            inv = rows[0]
            if inv.get("status") != "pending":
                raise ValueError("invite is not pending")
            if inv.get("target_user_id") and inv.get("target_user_id") != current_user_id:
                raise PermissionError("invite target mismatch")
            updated = (
                self.db.client.table("collab_invites")
                .update({"status": "accepted", "updated_at": _utc_now_iso()})
                .eq("id", inv.get("id"))
                .execute()
            ).data or []
            contact = self.request_contact(
                requester_user_id=inv["requester_user_id"],
                target_user_id=current_user_id,
            )
            if contact.get("status") == "pending":
                self.accept_contact(current_user_id=current_user_id, contact_id=contact["id"])
            self._audit("invite_accept", current_user_id, {"code": code})
            return updated[0] if updated else inv
        inv = self.db._fetchone(
            "SELECT * FROM collab_invites WHERE tenant_id=%s AND code=%s LIMIT 1",
            (tenant_id, code),
        )
        if not inv:
            raise KeyError("invite not found")
        if inv.get("status") != "pending":
            raise ValueError("invite is not pending")
        if inv.get("target_user_id") and inv.get("target_user_id") != current_user_id:
            raise PermissionError("invite target mismatch")
        self.db._execute(
            "UPDATE collab_invites SET status='accepted', updated_at=NOW() WHERE tenant_id=%s AND id=%s",
            (tenant_id, inv.get("id")),
        )
        contact = self.request_contact(
            requester_user_id=inv["requester_user_id"],
            target_user_id=current_user_id,
        )
        if contact.get("status") == "pending":
            self.accept_contact(current_user_id=current_user_id, contact_id=contact["id"])
        self._audit("invite_accept", current_user_id, {"code": code})
        return self.db._fetchone(
            "SELECT * FROM collab_invites WHERE tenant_id=%s AND code=%s LIMIT 1",
            (tenant_id, code),
        ) or inv

    def list_invites(self, *, requester_user_id: str) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        if self.kind == "memory":
            return [i for i in self.db.collab_invites if i["tenant_id"] == tenant_id and i["requester_user_id"] == requester_user_id]
        if self.kind == "supabase":
            return (
                self.db.client.table("collab_invites")
                .select("*")
                .eq("requester_user_id", requester_user_id)
                .execute()
            ).data or []
        return self.db._fetchall(
            "SELECT * FROM collab_invites WHERE tenant_id=%s AND requester_user_id=%s ORDER BY created_at DESC",
            (tenant_id, requester_user_id),
        )

    # -------------------------------------------------------------------------
    # Teams / spaces / files / ACL / transfers
    # -------------------------------------------------------------------------
    def create_team(self, *, owner_user_id: str, name: str) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        self.ensure_org_user(user_id=owner_user_id)
        team_id = self._id()
        row = {
            "id": team_id,
            "tenant_id": tenant_id,
            "name": name.strip() or "Team",
            "owner_user_id": owner_user_id,
            "created_at": _utc_now_iso(),
        }
        if self.kind == "memory":
            self.db.collab_teams.append(row)
            self.db.collab_team_members.append(
                {
                    "id": self._id(),
                    "tenant_id": tenant_id,
                    "team_id": team_id,
                    "user_id": owner_user_id,
                    "role": "owner",
                    "created_at": _utc_now_iso(),
                }
            )
            self._audit("team_create", owner_user_id, {"team_id": team_id, "name": row["name"]})
            return row
        if self.kind == "supabase":
            inserted = self.db.client.table("collab_teams").insert(row).execute().data or [row]
            self.db.client.table("collab_team_members").insert(
                {
                    "tenant_id": tenant_id,
                    "team_id": team_id,
                    "user_id": owner_user_id,
                    "role": "owner",
                }
            ).execute()
            self._audit("team_create", owner_user_id, {"team_id": team_id, "name": row["name"]})
            return inserted[0]
        self.db._execute(
            """
            INSERT INTO collab_teams (id, tenant_id, name, owner_user_id) VALUES (%s, %s, %s, %s)
            """,
            (team_id, tenant_id, row["name"], owner_user_id),
        )
        self.db._execute(
            """
            INSERT INTO collab_team_members (tenant_id, team_id, user_id, role) VALUES (%s, %s, %s, 'owner')
            ON CONFLICT (tenant_id, team_id, user_id) DO NOTHING
            """,
            (tenant_id, team_id, owner_user_id),
        )
        self._audit("team_create", owner_user_id, {"team_id": team_id, "name": row["name"]})
        return self.db._fetchone(
            "SELECT * FROM collab_teams WHERE tenant_id=%s AND id=%s LIMIT 1",
            (tenant_id, team_id),
        ) or row

    def _team_member_role(self, *, team_id: str, user_id: str) -> Optional[str]:
        tenant_id = self._tenant_id()
        if self.kind == "memory":
            for m in self.db.collab_team_members:
                if m["tenant_id"] == tenant_id and m["team_id"] == team_id and m["user_id"] == user_id:
                    return m["role"]
            return None
        if self.kind == "supabase":
            rows = (
                self.db.client.table("collab_team_members")
                .select("*")
                .eq("team_id", team_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            ).data or []
            return rows[0].get("role") if rows else None
        row = self.db._fetchone(
            "SELECT role FROM collab_team_members WHERE tenant_id=%s AND team_id=%s AND user_id=%s LIMIT 1",
            (tenant_id, team_id, user_id),
        )
        return row.get("role") if row else None

    def add_team_member(self, *, actor_user_id: str, team_id: str, user_id: str, role: str = "member") -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        actor_role = self._team_member_role(team_id=team_id, user_id=actor_user_id)
        if actor_role not in {"owner", "admin"}:
            raise PermissionError("team admin required")
        self.ensure_org_user(user_id=user_id)
        payload = {
            "id": self._id(),
            "tenant_id": tenant_id,
            "team_id": team_id,
            "user_id": user_id,
            "role": role if role in {"owner", "admin", "member"} else "member",
            "created_at": _utc_now_iso(),
        }
        if self.kind == "memory":
            for m in self.db.collab_team_members:
                if m["tenant_id"] == tenant_id and m["team_id"] == team_id and m["user_id"] == user_id:
                    return m
            self.db.collab_team_members.append(payload)
            self._audit("team_member_add", actor_user_id, {"team_id": team_id, "user_id": user_id, "role": payload["role"]})
            return payload
        if self.kind == "supabase":
            existing = (
                self.db.client.table("collab_team_members")
                .select("*")
                .eq("team_id", team_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            ).data or []
            if existing:
                return existing[0]
            row = self.db.client.table("collab_team_members").insert(payload).execute().data or [payload]
            self._audit("team_member_add", actor_user_id, {"team_id": team_id, "user_id": user_id, "role": payload["role"]})
            return row[0]
        self.db._execute(
            """
            INSERT INTO collab_team_members (tenant_id, team_id, user_id, role)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (tenant_id, team_id, user_id) DO NOTHING
            """,
            (tenant_id, team_id, user_id, payload["role"]),
        )
        self._audit("team_member_add", actor_user_id, {"team_id": team_id, "user_id": user_id, "role": payload["role"]})
        return self.db._fetchone(
            "SELECT * FROM collab_team_members WHERE tenant_id=%s AND team_id=%s AND user_id=%s LIMIT 1",
            (tenant_id, team_id, user_id),
        ) or payload

    def list_my_teams(self, *, user_id: str) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        if self.kind == "memory":
            memberships = [m for m in self.db.collab_team_members if m["tenant_id"] == tenant_id and m["user_id"] == user_id]
            teams: Dict[str, Dict[str, Any]] = {t["id"]: t for t in self.db.collab_teams if t["tenant_id"] == tenant_id}
            out: List[Dict[str, Any]] = []
            for m in memberships:
                team = teams.get(m["team_id"])
                if team:
                    out.append({**team, "membership_role": m["role"]})
            return out
        if self.kind == "supabase":
            memberships = (
                self.db.client.table("collab_team_members")
                .select("*")
                .eq("user_id", user_id)
                .execute()
            ).data or []
            out: List[Dict[str, Any]] = []
            for m in memberships:
                teams = (
                    self.db.client.table("collab_teams")
                    .select("*")
                    .eq("id", m.get("team_id"))
                    .limit(1)
                    .execute()
                ).data or []
                if teams:
                    out.append({**teams[0], "membership_role": m.get("role")})
            return out
        return self.db._fetchall(
            """
            SELECT t.*, m.role AS membership_role
            FROM collab_teams t
            JOIN collab_team_members m
              ON t.id = m.team_id
             AND t.tenant_id = m.tenant_id
            WHERE t.tenant_id=%s AND m.user_id=%s
            ORDER BY t.created_at DESC
            """,
            (tenant_id, user_id),
        )

    def create_space(self, *, actor_user_id: str, space_type: str, name: str, team_id: Optional[str] = None) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        stype = (space_type or "personal").strip().lower()
        if stype not in {"personal", "team"}:
            raise ValueError("invalid space type")
        if stype == "team":
            if not team_id:
                raise ValueError("team_id required")
            if self._team_member_role(team_id=team_id, user_id=actor_user_id) is None:
                raise PermissionError("team membership required")
        payload = {
            "id": self._id(),
            "tenant_id": tenant_id,
            "type": stype,
            "owner_user_id": actor_user_id if stype == "personal" else None,
            "team_id": team_id if stype == "team" else None,
            "name": name.strip() or ("Personal Space" if stype == "personal" else "Team Space"),
            "created_at": _utc_now_iso(),
        }
        if self.kind == "memory":
            self.db.collab_spaces.append(payload)
            self._audit("space_create", actor_user_id, {"space_id": payload["id"], "type": stype, "team_id": team_id})
            return payload
        if self.kind == "supabase":
            row = self.db.client.table("collab_spaces").insert(payload).execute().data or [payload]
            self._audit("space_create", actor_user_id, {"space_id": payload["id"], "type": stype, "team_id": team_id})
            return row[0]
        self.db._execute(
            """
            INSERT INTO collab_spaces (id, tenant_id, type, owner_user_id, team_id, name)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (payload["id"], tenant_id, stype, payload["owner_user_id"], payload["team_id"], payload["name"]),
        )
        self._audit("space_create", actor_user_id, {"space_id": payload["id"], "type": stype, "team_id": team_id})
        return self.db._fetchone(
            "SELECT * FROM collab_spaces WHERE tenant_id=%s AND id=%s LIMIT 1",
            (tenant_id, payload["id"]),
        ) or payload

    def list_spaces(self, *, user_id: str) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        team_ids = {t["id"] for t in self.list_my_teams(user_id=user_id)}
        if self.kind == "memory":
            out: List[Dict[str, Any]] = []
            for s in self.db.collab_spaces:
                if s["tenant_id"] != tenant_id:
                    continue
                if s["type"] == "personal" and s.get("owner_user_id") == user_id:
                    out.append(s)
                if s["type"] == "team" and s.get("team_id") in team_ids:
                    out.append(s)
            return out
        if self.kind == "supabase":
            rows = self.db.client.table("collab_spaces").select("*").execute().data or []
            out: List[Dict[str, Any]] = []
            for s in rows:
                if s.get("type") == "personal" and s.get("owner_user_id") == user_id:
                    out.append(s)
                if s.get("type") == "team" and s.get("team_id") in team_ids:
                    out.append(s)
            return out
        if not team_ids:
            return self.db._fetchall(
                """
                SELECT * FROM collab_spaces
                WHERE tenant_id=%s AND type='personal' AND owner_user_id=%s
                ORDER BY created_at DESC
                """,
                (tenant_id, user_id),
            )
        return self.db._fetchall(
            """
            SELECT * FROM collab_spaces
            WHERE tenant_id=%s
              AND ((type='personal' AND owner_user_id=%s) OR (type='team' AND team_id = ANY(%s)))
            ORDER BY created_at DESC
            """,
            (tenant_id, user_id, list(team_ids) or [""]),
        )

    def ensure_personal_space(self, *, user_id: str) -> Dict[str, Any]:
        """
        Ensure a personal space exists for user in current tenant.
        Safe to call from ingest pipeline.
        """
        tenant_id = self._tenant_id()
        name = "Personal"
        if self.kind == "memory":
            for s in self.db.collab_spaces:
                if s["tenant_id"] == tenant_id and s.get("type") == "personal" and s.get("owner_user_id") == user_id:
                    return s
            created = {
                "id": self._id(),
                "tenant_id": tenant_id,
                "type": "personal",
                "owner_user_id": user_id,
                "team_id": None,
                "name": name,
                "created_at": _utc_now_iso(),
            }
            self.db.collab_spaces.append(created)
            return created
        if self.kind == "supabase":
            rows = (
                self.db.client.table("collab_spaces")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("type", "personal")
                .eq("owner_user_id", user_id)
                .limit(1)
                .execute()
            ).data or []
            if rows:
                return rows[0]
            payload = {
                "id": self._id(),
                "tenant_id": tenant_id,
                "type": "personal",
                "owner_user_id": user_id,
                "team_id": None,
                "name": name,
                "created_at": _utc_now_iso(),
            }
            created = (self.db.client.table("collab_spaces").insert(payload).execute().data or [payload])[0]
            return created
        existing = self.db._fetchone(
            """
            SELECT * FROM collab_spaces
            WHERE tenant_id=%s AND type='personal' AND owner_user_id=%s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (tenant_id, user_id),
        )
        if existing:
            return existing
        payload_id = self._id()
        self.db._execute(
            """
            INSERT INTO collab_spaces (id, tenant_id, type, owner_user_id, team_id, name)
            VALUES (%s, %s, 'personal', %s, NULL, %s)
            """,
            (payload_id, tenant_id, user_id, name),
        )
        return self.db._fetchone(
            "SELECT * FROM collab_spaces WHERE tenant_id=%s AND id=%s LIMIT 1",
            (tenant_id, payload_id),
        ) or {"id": payload_id, "tenant_id": tenant_id, "type": "personal", "owner_user_id": user_id, "name": name}

    def update_space(self, *, actor_user_id: str, space_id: str, name: Optional[str] = None) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        space = self.get_space(space_id=space_id)
        if not space:
            raise KeyError("space not found")
        allowed = False
        if space.get("type") == "personal" and space.get("owner_user_id") == actor_user_id:
            allowed = True
        if space.get("type") == "team":
            role = self._team_member_role(team_id=str(space.get("team_id")), user_id=actor_user_id)
            allowed = role in {"owner", "admin"}
        if not allowed:
            raise PermissionError("space update denied")
        new_name = (name or "").strip() or space.get("name")
        if self.kind == "memory":
            space["name"] = new_name
            return space
        if self.kind == "supabase":
            rows = (
                self.db.client.table("collab_spaces")
                .update({"name": new_name})
                .eq("id", space_id)
                .execute()
            ).data or []
            return rows[0] if rows else {**space, "name": new_name}
        self.db._execute(
            "UPDATE collab_spaces SET name=%s WHERE tenant_id=%s AND id=%s",
            (new_name, tenant_id, space_id),
        )
        return self.db._fetchone(
            "SELECT * FROM collab_spaces WHERE tenant_id=%s AND id=%s LIMIT 1",
            (tenant_id, space_id),
        ) or {**space, "name": new_name}

    def get_space(self, *, space_id: str) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        if self.kind == "memory":
            for s in self.db.collab_spaces:
                if s["tenant_id"] == tenant_id and s["id"] == space_id:
                    return s
            return {}
        if self.kind == "supabase":
            rows = (
                self.db.client.table("collab_spaces")
                .select("*")
                .eq("id", space_id)
                .limit(1)
                .execute()
            ).data or []
            return rows[0] if rows else {}
        return self.db._fetchone(
            "SELECT * FROM collab_spaces WHERE tenant_id=%s AND id=%s LIMIT 1",
            (tenant_id, space_id),
        ) or {}

    def register_file(
        self,
        *,
        actor_user_id: str,
        space_id: str,
        doc_id: str,
        version: int = 1,
        visibility: str = "private",
    ) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        space = self.get_space(space_id=space_id)
        if not space:
            raise KeyError("space not found")
        if space.get("type") == "personal" and space.get("owner_user_id") != actor_user_id:
            raise PermissionError("not owner of personal space")
        if space.get("type") == "team":
            if self._team_member_role(team_id=str(space.get("team_id")), user_id=actor_user_id) is None:
                raise PermissionError("team membership required")
        payload = {
            "id": self._id(),
            "tenant_id": tenant_id,
            "space_id": space_id,
            "owner_user_id": actor_user_id,
            "doc_id": doc_id,
            "version": int(version or 1),
            "visibility": visibility if visibility in {"private", "team", "direct"} else "private",
            "created_at": _utc_now_iso(),
        }
        if self.kind == "memory":
            self.db.collab_files.append(payload)
            self._audit("file_register", actor_user_id, {"file_id": payload["id"], "doc_id": doc_id})
            return payload
        if self.kind == "supabase":
            rows = self.db.client.table("collab_files").insert(payload).execute().data or [payload]
            self._audit("file_register", actor_user_id, {"file_id": payload["id"], "doc_id": doc_id})
            return rows[0]
        self.db._execute(
            """
            INSERT INTO collab_files (id, tenant_id, space_id, owner_user_id, doc_id, version, visibility)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (payload["id"], tenant_id, space_id, actor_user_id, doc_id, payload["version"], payload["visibility"]),
        )
        self._audit("file_register", actor_user_id, {"file_id": payload["id"], "doc_id": doc_id})
        return self.db._fetchone(
            "SELECT * FROM collab_files WHERE tenant_id=%s AND id=%s LIMIT 1",
            (tenant_id, payload["id"]),
        ) or payload

    def _list_file_acl(self, *, file_id: str) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        if self.kind == "memory":
            return [r for r in self.db.collab_file_acl if r["tenant_id"] == tenant_id and r["file_id"] == file_id]
        if self.kind == "supabase":
            return (
                self.db.client.table("collab_file_acl")
                .select("*")
                .eq("file_id", file_id)
                .execute()
            ).data or []
        return self.db._fetchall(
            "SELECT * FROM collab_file_acl WHERE tenant_id=%s AND file_id=%s",
            (tenant_id, file_id),
        )

    def get_file(self, *, file_id: str) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        if self.kind == "memory":
            for f in self.db.collab_files:
                if f["tenant_id"] == tenant_id and f["id"] == file_id:
                    return f
            return {}
        if self.kind == "supabase":
            rows = (
                self.db.client.table("collab_files")
                .select("*")
                .eq("id", file_id)
                .limit(1)
                .execute()
            ).data or []
            return rows[0] if rows else {}
        return self.db._fetchone(
            "SELECT * FROM collab_files WHERE tenant_id=%s AND id=%s LIMIT 1",
            (tenant_id, file_id),
        ) or {}

    def list_files(self, *, user_id: str, role: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        max_limit = max(1, min(int(limit or 200), 500))
        if self.kind == "memory":
            rows = [f for f in self.db.collab_files if f["tenant_id"] == tenant_id]
        elif self.kind == "supabase":
            rows = (
                self.db.client.table("collab_files")
                .select("*")
                .order("created_at", desc=True)
                .limit(max_limit)
                .execute()
            ).data or []
        else:
            rows = self.db._fetchall(
                """
                SELECT * FROM collab_files
                WHERE tenant_id=%s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (tenant_id, max_limit),
            )
        out: List[Dict[str, Any]] = []
        for row in rows:
            file_id = str(row.get("id") or "")
            if not file_id:
                continue
            if self.can_read_file(user_id=user_id, role=role, file_id=file_id):
                out.append(row)
        return out[:max_limit]

    def can_read_file(self, *, user_id: str, role: Optional[str] = None, file_id: str) -> bool:
        r = self._normalize_role(role)
        file_row = self.get_file(file_id=file_id)
        if not file_row:
            return False
        # Tenant-wide readers (auditor/admin) can read all files within tenant.
        if r in {"admin", "auditor"}:
            return True
        if file_row.get("owner_user_id") == user_id:
            return True
        visibility = file_row.get("visibility", "private")
        # reviewer can read "team" visibility within tenant even without membership
        if r == "reviewer" and visibility == "team":
            return True
        if visibility == "team":
            team_id = self.get_space(space_id=str(file_row.get("space_id"))).get("team_id")
            if team_id and self._team_member_role(team_id=str(team_id), user_id=user_id):
                return True
        acl_rows = self._list_file_acl(file_id=file_id)
        team_ids = {t["id"] for t in self.list_my_teams(user_id=user_id)}
        for acl in acl_rows:
            if acl.get("principal_type") == "user" and acl.get("principal_id") == user_id:
                return True
            if acl.get("principal_type") == "team" and acl.get("principal_id") in team_ids:
                return True
        return False

    def share_file(
        self,
        *,
        actor_user_id: str,
        file_id: str,
        principal_type: str,
        principal_id: str,
        permission: str,
    ) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        file_row = self.get_file(file_id=file_id)
        if not file_row:
            raise KeyError("file not found")
        if file_row.get("owner_user_id") != actor_user_id:
            raise PermissionError("only owner can share")
        ptype = principal_type if principal_type in {"user", "team"} else "user"
        perm = permission if permission in {"read", "comment", "share"} else "read"

        if ptype == "user":
            self.ensure_org_user(user_id=principal_id)
            if not self.are_friends(user_a=actor_user_id, user_b=principal_id):
                raise PermissionError("friend connection required for user share")
        if ptype == "team":
            if self._team_member_role(team_id=principal_id, user_id=actor_user_id) is None:
                # allow sharing to team where actor is not member only if owner/admin role.
                # For now we enforce membership.
                raise PermissionError("must belong to target team")

        payload = {
            "id": self._id(),
            "tenant_id": tenant_id,
            "file_id": file_id,
            "principal_type": ptype,
            "principal_id": principal_id,
            "permission": perm,
            "created_at": _utc_now_iso(),
        }
        if self.kind == "memory":
            self.db.collab_file_acl.append(payload)
            self._audit("team_share" if ptype == "team" else "user_share", actor_user_id, {"file_id": file_id, "principal": principal_id})
            return payload
        if self.kind == "supabase":
            rows = self.db.client.table("collab_file_acl").insert(payload).execute().data or [payload]
            self._audit("team_share" if ptype == "team" else "user_share", actor_user_id, {"file_id": file_id, "principal": principal_id})
            return rows[0]
        self.db._execute(
            """
            INSERT INTO collab_file_acl (id, tenant_id, file_id, principal_type, principal_id, permission)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (payload["id"], tenant_id, file_id, ptype, principal_id, perm),
        )
        self._audit("team_share" if ptype == "team" else "user_share", actor_user_id, {"file_id": file_id, "principal": principal_id})
        return self.db._fetchone(
            "SELECT * FROM collab_file_acl WHERE tenant_id=%s AND id=%s LIMIT 1",
            (tenant_id, payload["id"]),
        ) or payload

    def send_transfer(self, *, sender_user_id: str, receiver_user_id: str, file_id: str, message: Optional[str] = None) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        self.ensure_org_user(user_id=receiver_user_id)
        if not self.are_friends(user_a=sender_user_id, user_b=receiver_user_id):
            raise PermissionError("friend connection required")
        if not self.can_read_file(user_id=sender_user_id, file_id=file_id):
            raise PermissionError("sender cannot access file")
        payload = {
            "id": self._id(),
            "tenant_id": tenant_id,
            "sender_user_id": sender_user_id,
            "receiver_user_id": receiver_user_id,
            "file_id": file_id,
            "message": message or "",
            "status": "sent",
            "created_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
        }
        if self.kind == "memory":
            self.db.collab_transfers.append(payload)
            self._audit("direct_transfer", sender_user_id, {"transfer_id": payload["id"], "file_id": file_id, "receiver": receiver_user_id})
            return payload
        if self.kind == "supabase":
            rows = self.db.client.table("collab_transfers").insert(payload).execute().data or [payload]
            self._audit("direct_transfer", sender_user_id, {"transfer_id": payload["id"], "file_id": file_id, "receiver": receiver_user_id})
            return rows[0]
        self.db._execute(
            """
            INSERT INTO collab_transfers (id, tenant_id, sender_user_id, receiver_user_id, file_id, message, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'sent')
            """,
            (payload["id"], tenant_id, sender_user_id, receiver_user_id, file_id, payload["message"]),
        )
        self._audit("direct_transfer", sender_user_id, {"transfer_id": payload["id"], "file_id": file_id, "receiver": receiver_user_id})
        return self.db._fetchone(
            "SELECT * FROM collab_transfers WHERE tenant_id=%s AND id=%s LIMIT 1",
            (tenant_id, payload["id"]),
        ) or payload

    def list_inbox(self, *, user_id: str) -> List[Dict[str, Any]]:
        tenant_id = self._tenant_id()
        if self.kind == "memory":
            return [t for t in self.db.collab_transfers if t["tenant_id"] == tenant_id and t["receiver_user_id"] == user_id]
        if self.kind == "supabase":
            return (
                self.db.client.table("collab_transfers")
                .select("*")
                .eq("receiver_user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            ).data or []
        return self.db._fetchall(
            """
            SELECT * FROM collab_transfers
            WHERE tenant_id=%s AND receiver_user_id=%s
            ORDER BY created_at DESC
            """,
            (tenant_id, user_id),
        )

    def ack_transfer(self, *, user_id: str, transfer_id: str, status: str) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        allowed = {"read", "accepted", "rejected"}
        next_status = status if status in allowed else "read"
        if self.kind == "memory":
            for t in self.db.collab_transfers:
                if t["tenant_id"] == tenant_id and t["id"] == transfer_id:
                    if t["receiver_user_id"] != user_id:
                        raise PermissionError("receiver only")
                    t["status"] = next_status
                    t["updated_at"] = _utc_now_iso()
                    self._audit("transfer_ack", user_id, {"transfer_id": transfer_id, "status": next_status})
                    return t
            raise KeyError("transfer not found")
        if self.kind == "supabase":
            rows = (
                self.db.client.table("collab_transfers")
                .select("*")
                .eq("id", transfer_id)
                .limit(1)
                .execute()
            ).data or []
            if not rows:
                raise KeyError("transfer not found")
            row = rows[0]
            if row.get("receiver_user_id") != user_id:
                raise PermissionError("receiver only")
            updated = (
                self.db.client.table("collab_transfers")
                .update({"status": next_status, "updated_at": _utc_now_iso()})
                .eq("id", transfer_id)
                .execute()
            ).data or []
            self._audit("transfer_ack", user_id, {"transfer_id": transfer_id, "status": next_status})
            return updated[0] if updated else row
        row = self.db._fetchone(
            "SELECT * FROM collab_transfers WHERE tenant_id=%s AND id=%s LIMIT 1",
            (tenant_id, transfer_id),
        )
        if not row:
            raise KeyError("transfer not found")
        if row.get("receiver_user_id") != user_id:
            raise PermissionError("receiver only")
        self.db._execute(
            "UPDATE collab_transfers SET status=%s, updated_at=NOW() WHERE tenant_id=%s AND id=%s",
            (next_status, tenant_id, transfer_id),
        )
        self._audit("transfer_ack", user_id, {"transfer_id": transfer_id, "status": next_status})
        return self.db._fetchone(
            "SELECT * FROM collab_transfers WHERE tenant_id=%s AND id=%s LIMIT 1",
            (tenant_id, transfer_id),
        ) or {}

    # -------------------------------------------------------------------------
    # Tenant pipeline (single shared engine per tenant)
    # -------------------------------------------------------------------------
    @staticmethod
    def _default_pipeline_profile() -> Dict[str, Any]:
        return {
            "rag_profile_json": {
                "engine": "shared-rag",
                "index": "tenant-default",
                "mode": "single-tenant-shared",
            },
            "llm_profile_json": {
                "provider": os.getenv("TRAINING_PROVIDER", "openai"),
                "model": os.getenv("TRAINING_MODEL", "gpt-4o-mini"),
            },
            "rate_limits_json": {
                "rag_queries_per_user_per_day": 500,
                "ingest_docs_per_user_per_day": 200,
                "llm_tokens_per_user_per_day": 200000,
            },
        }

    def ensure_pipeline_profile(self) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        profile = self.get_pipeline_profile()
        if profile:
            return profile
        defaults = self._default_pipeline_profile()
        if self.kind == "memory":
            row = {"tenant_id": tenant_id, **defaults, "updated_at": _utc_now_iso()}
            self.db.tenant_pipeline_profiles.append(row)
            return row
        if self.kind == "supabase":
            payload = {"tenant_id": tenant_id, **defaults}
            rows = self.db.client.table("tenant_pipeline_profiles").insert(payload).execute().data or [payload]
            return rows[0]
        self.db._execute(
            """
            INSERT INTO tenant_pipeline_profiles (tenant_id, rag_profile_json, llm_profile_json, rate_limits_json)
            VALUES (%s, %s::jsonb, %s::jsonb, %s::jsonb)
            ON CONFLICT (tenant_id) DO NOTHING
            """,
            (
                tenant_id,
                json.dumps(defaults["rag_profile_json"]),
                json.dumps(defaults["llm_profile_json"]),
                json.dumps(defaults["rate_limits_json"]),
            ),
        )
        return self.get_pipeline_profile() or {"tenant_id": tenant_id, **defaults}

    def get_pipeline_profile(self) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        if self.kind == "memory":
            for p in self.db.tenant_pipeline_profiles:
                if p["tenant_id"] == tenant_id:
                    return p
            return {}
        if self.kind == "supabase":
            rows = (
                self.db.client.table("tenant_pipeline_profiles")
                .select("*")
                .eq("tenant_id", tenant_id)
                .limit(1)
                .execute()
            ).data or []
            return rows[0] if rows else {}
        return self.db._fetchone(
            "SELECT * FROM tenant_pipeline_profiles WHERE tenant_id=%s LIMIT 1",
            (tenant_id,),
        ) or {}

    @staticmethod
    def _today() -> str:
        return date.today().isoformat()

    def _get_quota_row(self, *, user_id: str) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        day = self._today()
        if self.kind == "memory":
            for q in self.db.tenant_pipeline_quotas:
                if q["tenant_id"] == tenant_id and q["user_id"] == user_id and q["day"] == day:
                    return q
            row = {
                "id": self._id(),
                "tenant_id": tenant_id,
                "user_id": user_id,
                "day": day,
                "rag_queries": 0,
                "llm_tokens": 0,
                "ingest_docs": 0,
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            }
            self.db.tenant_pipeline_quotas.append(row)
            return row
        if self.kind == "supabase":
            rows = (
                self.db.client.table("tenant_pipeline_quotas")
                .select("*")
                .eq("user_id", user_id)
                .eq("day", day)
                .limit(1)
                .execute()
            ).data or []
            if rows:
                return rows[0]
            payload = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "day": day,
                "rag_queries": 0,
                "llm_tokens": 0,
                "ingest_docs": 0,
            }
            ins = self.db.client.table("tenant_pipeline_quotas").insert(payload).execute().data or [payload]
            return ins[0]
        row = self.db._fetchone(
            "SELECT * FROM tenant_pipeline_quotas WHERE tenant_id=%s AND user_id=%s AND day=%s LIMIT 1",
            (tenant_id, user_id, day),
        )
        if row:
            return row
        self.db._execute(
            """
            INSERT INTO tenant_pipeline_quotas (tenant_id, user_id, day, rag_queries, llm_tokens, ingest_docs)
            VALUES (%s, %s, %s, 0, 0, 0)
            ON CONFLICT (tenant_id, user_id, day) DO NOTHING
            """,
            (tenant_id, user_id, day),
        )
        return self.db._fetchone(
            "SELECT * FROM tenant_pipeline_quotas WHERE tenant_id=%s AND user_id=%s AND day=%s LIMIT 1",
            (tenant_id, user_id, day),
        ) or {}

    def _check_and_bump_quota(self, *, user_id: str, job_type: str) -> Dict[str, Any]:
        profile = self.ensure_pipeline_profile()
        limits = profile.get("rate_limits_json") or {}
        quota = self._get_quota_row(user_id=user_id)
        field = None
        max_allowed = None
        if job_type == "rag":
            field = "rag_queries"
            max_allowed = int(limits.get("rag_queries_per_user_per_day", 500))
        elif job_type == "ingest":
            field = "ingest_docs"
            max_allowed = int(limits.get("ingest_docs_per_user_per_day", 200))

        if not field:
            return quota

        current = int(quota.get(field, 0))
        if current >= int(max_allowed):
            raise PermissionError(f"quota exceeded for {field}")
        next_value = current + 1
        tenant_id = self._tenant_id()
        if self.kind == "memory":
            quota[field] = next_value
            quota["updated_at"] = _utc_now_iso()
            return quota
        if self.kind == "supabase":
            rows = (
                self.db.client.table("tenant_pipeline_quotas")
                .update({field: next_value, "updated_at": _utc_now_iso()})
                .eq("id", quota.get("id"))
                .execute()
            ).data or []
            return rows[0] if rows else {**quota, field: next_value}
        self.db._execute(
            f"UPDATE tenant_pipeline_quotas SET {field}=%s, updated_at=NOW() WHERE tenant_id=%s AND id=%s",
            (next_value, tenant_id, quota.get("id")),
        )
        return self.db._fetchone(
            "SELECT * FROM tenant_pipeline_quotas WHERE tenant_id=%s AND id=%s LIMIT 1",
            (tenant_id, quota.get("id")),
        ) or {**quota, field: next_value}

    def submit_pipeline_job(
        self,
        *,
        user_id: str,
        job_type: str,
        priority: int = 10,
        input_ref: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        normalized_type = (job_type or "rag").strip().lower()
        if normalized_type not in {"ingest", "rag", "approval", "train", "export", "batch"}:
            normalized_type = "rag"

        self._check_and_bump_quota(user_id=user_id, job_type=normalized_type)

        payload = {
            "id": self._id(),
            "tenant_id": tenant_id,
            "user_id": user_id,
            "job_type": normalized_type,
            "priority": int(priority),
            "status": "pending",
            "input_ref": input_ref or {},
            "output_ref": {},
            "error": None,
            "created_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
        }
        if self.kind == "memory":
            self.db.pipeline_jobs.append(payload)
            self._audit("pipeline_job_submit", user_id, {"job_id": payload["id"], "job_type": normalized_type})
            return payload
        if self.kind == "supabase":
            row = self.db.client.table("pipeline_jobs").insert(payload).execute().data or [payload]
            self._audit("pipeline_job_submit", user_id, {"job_id": payload["id"], "job_type": normalized_type})
            return row[0]
        self.db._execute(
            """
            INSERT INTO pipeline_jobs
            (id, tenant_id, user_id, job_type, priority, status, input_ref, output_ref, error)
            VALUES (%s, %s, %s, %s, %s, 'pending', %s::jsonb, %s::jsonb, %s)
            """,
            (
                payload["id"],
                tenant_id,
                user_id,
                normalized_type,
                payload["priority"],
                json.dumps(payload["input_ref"]),
                json.dumps(payload["output_ref"]),
                None,
            ),
        )
        self._audit("pipeline_job_submit", user_id, {"job_id": payload["id"], "job_type": normalized_type})
        return self.get_pipeline_job(job_id=payload["id"]) or payload

    def get_pipeline_job(self, *, job_id: str) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        if self.kind == "memory":
            for j in self.db.pipeline_jobs:
                if j["tenant_id"] == tenant_id and j["id"] == job_id:
                    return j
            return {}
        if self.kind == "supabase":
            rows = (
                self.db.client.table("pipeline_jobs")
                .select("*")
                .eq("id", job_id)
                .limit(1)
                .execute()
            ).data or []
            return rows[0] if rows else {}
        return self.db._fetchone(
            "SELECT * FROM pipeline_jobs WHERE tenant_id=%s AND id=%s LIMIT 1",
            (tenant_id, job_id),
        ) or {}

    def tenant_pipeline_status(self, *, user_id: Optional[str] = None) -> Dict[str, Any]:
        tenant_id = self._tenant_id()
        profile = self.ensure_pipeline_profile()
        if self.kind == "memory":
            jobs = [j for j in self.db.pipeline_jobs if j["tenant_id"] == tenant_id]
        elif self.kind == "supabase":
            jobs = self.db.client.table("pipeline_jobs").select("*").limit(500).execute().data or []
        else:
            jobs = self.db._fetchall(
                "SELECT * FROM pipeline_jobs WHERE tenant_id=%s ORDER BY created_at DESC LIMIT 500",
                (tenant_id,),
            )

        by_status: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        for j in jobs:
            by_status[str(j.get("status"))] = by_status.get(str(j.get("status")), 0) + 1
            by_type[str(j.get("job_type"))] = by_type.get(str(j.get("job_type")), 0) + 1

        quota = None
        if user_id:
            quota = self._get_quota_row(user_id=user_id)

        return {
            "tenant_id": tenant_id,
            "profile": profile,
            "job_counts_by_status": by_status,
            "job_counts_by_type": by_type,
            "queue_depth": by_status.get("pending", 0),
            "today_quota": quota,
        }

    def update_pipeline_job_status(
        self,
        *,
        actor_user_id: str,
        job_id: str,
        status: str,
        output_ref: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Best-effort pipeline job status update. Never raises on missing schema.
        """
        tenant_id = self._tenant_id()
        payload: Dict[str, Any] = {
            "status": status,
            "updated_at": _utc_now_iso(),
        }
        if output_ref is not None:
            payload["output_ref"] = output_ref
        # Allow clearing error by explicitly passing error=None from callers.
        payload["error"] = error

        try:
            if self.kind == "memory":
                for j in self.db.pipeline_jobs:
                    if j["tenant_id"] == tenant_id and j["id"] == job_id:
                        j.update(payload)
                        self._audit(
                            "pipeline_job_update",
                            actor_user_id,
                            {"job_id": job_id, "status": status, "error": error},
                        )
                        return j
                return {}
            if self.kind == "supabase":
                rows = (
                    self.db.client.table("pipeline_jobs")
                    .update(payload)
                    .eq("id", job_id)
                    .execute()
                ).data or []
                self._audit(
                    "pipeline_job_update",
                    actor_user_id,
                    {"job_id": job_id, "status": status, "error": error},
                )
                return rows[0] if rows else {}
            # postgres
            self.db._execute(
                """
                UPDATE pipeline_jobs
                SET status=%s, output_ref=COALESCE(%s::jsonb, output_ref), error=%s, updated_at=NOW()
                WHERE tenant_id=%s AND id=%s
                """,
                (status, json.dumps(output_ref) if output_ref is not None else None, error, tenant_id, job_id),
            )
            self._audit(
                "pipeline_job_update",
                actor_user_id,
                {"job_id": job_id, "status": status, "error": error},
            )
            return self.get_pipeline_job(job_id=job_id) or {}
        except Exception:
            return {}


class TenantPipelineManager:
    """
    Thin orchestration manager for tenant-shared RAG/LLM job flow.
    """

    PRIORITY_MAP = {
        "interactive": 1,
        "approval": 2,
        "ingest": 3,
        "batch": 5,
    }

    def __init__(self, db: Any):
        self.store = EnterpriseCollabStore(db)

    def submit(
        self,
        *,
        user_id: str,
        job_type: str,
        flow: str = "interactive",
        input_ref: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        priority = self.PRIORITY_MAP.get(flow, 10)
        return self.store.submit_pipeline_job(
            user_id=user_id,
            job_type=job_type,
            priority=priority,
            input_ref=input_ref or {},
        )

    def status(self, *, user_id: Optional[str] = None) -> Dict[str, Any]:
        return self.store.tenant_pipeline_status(user_id=user_id)
