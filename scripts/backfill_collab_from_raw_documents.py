#!/usr/bin/env python3
"""
Backfill Collaboration visibility records (collab_files) for raw_documents rows.

Why:
- RAG scoping + UI "My Files" depend on collab_files.
- Older documents (or documents created by non-UI paths) may exist without collab_files rows.

How it works:
- For each raw_documents row, look for metadata.owner_user_id.
- If present: ensure personal space and ensure (owner_user_id, doc_id) is registered as private.
- If missing: skip (cannot safely infer owner).

Safe:
- Idempotent: skips when collab file already exists for (tenant_id, owner_user_id, doc_id).
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional


def _get_db():
    from app.db.registry import get_db as _get_db

    return _get_db()


def _detect_kind(db: Any) -> str:
    if hasattr(db, "client"):
        return "supabase"
    if hasattr(db, "_fetchone") and hasattr(db, "_execute"):
        return "postgres"
    return "memory"


def _select_raw_documents(db: Any, *, limit: int, offset: int) -> list[Dict[str, Any]]:
    kind = _detect_kind(db)
    if kind == "memory":
        rows = list((getattr(db, "raw_documents", {}) or {}).values())
        return rows[offset : offset + limit]
    if kind == "supabase":
        res = (
            db.client.table("raw_documents")
            .select("id, tenant_id, metadata")
            .order("ingested_at", desc=False)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return res.data or []
    # postgres
    return db._fetchall(
        "SELECT id, tenant_id, metadata FROM raw_documents ORDER BY ingested_at ASC OFFSET %s LIMIT %s",
        (offset, limit),
    ) or []


def _collab_file_exists(db: Any, *, tenant_id: str, owner_user_id: str, doc_id: str) -> bool:
    kind = _detect_kind(db)
    if kind == "memory":
        rows = getattr(db, "collab_files", []) or []
        return any(
            r.get("tenant_id") == tenant_id and r.get("owner_user_id") == owner_user_id and str(r.get("doc_id")) == str(doc_id)
            for r in rows
        )
    if kind == "supabase":
        rows = (
            db.client.table("collab_files")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("owner_user_id", owner_user_id)
            .eq("doc_id", doc_id)
            .limit(1)
            .execute()
        ).data or []
        return bool(rows)
    row = db._fetchone(
        "SELECT id FROM collab_files WHERE tenant_id=%s AND owner_user_id=%s AND doc_id=%s LIMIT 1",
        (tenant_id, owner_user_id, doc_id),
    )
    return bool(row)


def main() -> int:
    from app.core.tenant_context import set_tenant_id, clear_tenant_id
    from app.services.enterprise_collab import EnterpriseCollabStore

    db = _get_db()
    store = EnterpriseCollabStore(db)

    batch_size = int(os.getenv("BACKFILL_BATCH_SIZE", "200"))
    max_rows = int(os.getenv("BACKFILL_MAX_ROWS", "50000"))

    seen = 0
    created = 0
    skipped_no_owner = 0
    skipped_exists = 0
    errors = 0

    offset = 0
    while True:
        if seen >= max_rows:
            break
        rows = _select_raw_documents(db, limit=batch_size, offset=offset)
        if not rows:
            break

        for r in rows:
            seen += 1
            tenant_id = str(r.get("tenant_id") or "public")
            metadata = r.get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}
            owner_user_id = metadata.get("owner_user_id")
            doc_id = str(r.get("id") or "")
            if not doc_id:
                continue
            if not owner_user_id:
                skipped_no_owner += 1
                continue
            owner_user_id = str(owner_user_id)

            try:
                set_tenant_id(tenant_id)
                if _collab_file_exists(db, tenant_id=tenant_id, owner_user_id=owner_user_id, doc_id=doc_id):
                    skipped_exists += 1
                    continue
                space = store.ensure_personal_space(user_id=owner_user_id)
                space_id = str(space.get("id") or "")
                if not space_id:
                    errors += 1
                    continue
                store.register_file(actor_user_id=owner_user_id, space_id=space_id, doc_id=doc_id, visibility="private")
                created += 1
            except Exception:
                errors += 1
            finally:
                clear_tenant_id()

        offset += len(rows)

    print(
        f"backfill done: seen={seen} created={created} skipped_exists={skipped_exists} skipped_no_owner={skipped_no_owner} errors={errors}"
    )
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

