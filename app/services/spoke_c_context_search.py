from __future__ import annotations

from typing import Any, Dict, List, Optional


def search_spoke_c_context(
    *,
    db: Optional[Any],
    query: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    DBClient-backed fallback search for Spoke C contexts.

    This intentionally avoids vector embeddings so on-prem (non-Supabase) deployments
    still get evidence retrieval via the canonical `spoke_c_rag_context` store.
    """
    if not db or not query:
        return []
    try:
        return db.search_rag_context(keyword=query, limit=limit) or []
    except Exception:
        return []


def search_spoke_c_context_supabase(
    *,
    client: Optional[Any],
    query: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Supabase-backed fallback search for Spoke C contexts.
    """
    if not client or not query:
        return []
    try:
        res = (
            client.table("spoke_c_rag_context")
            .select("chunk_id,entity,period,source,text_content,metadata,created_at")
            .ilike("text_content", f"%{query}%")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def format_spoke_c_context(rows: List[Dict[str, Any]]) -> str:
    lines: List[str] = ["[Spoke C Context (keyword fallback)]"]
    for idx, row in enumerate(rows or [], 1):
        chunk_id = row.get("chunk_id")
        entity = row.get("entity")
        period = row.get("period")
        source = row.get("source")
        content = (row.get("text_content") or "").strip()
        if len(content) > 700:
            content = content[:700] + " ..."
        lines.append(f"{idx}. chunk_id={chunk_id} entity={entity} period={period} source={source}")
        lines.append(content)
        lines.append("")
    return "\n".join(lines).strip()

