from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from app.services.unified_engine import UnifiedConversionEngine, UnifiedConversionResult
from app.services.domain_schema import normalize_partner_payload
from app.services.partner_registry import PartnerAuthResult, verify_partner_api_key as _verify_partner_api_key


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _events_to_facts(events: List[Dict[str, Any]], partner_id: str) -> List[Dict[str, Any]]:
    facts: List[Dict[str, Any]] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        entity = ev.get("entity") or ev.get("issuer") or ev.get("company")
        event_type = ev.get("event_type") or ev.get("type") or "event"
        announced_at = ev.get("announced_at") or ev.get("date") or ev.get("timestamp")
        related_entity = ev.get("related_entity") or ev.get("counterparty")
        evidence = ev.get("evidence") or {}
        fact = {
            "entity": entity or "unknown",
            "metric": f"event:{event_type}",
            "period": announced_at,
            "value": ev.get("payload") or ev.get("summary") or event_type,
            "unit": "event",
            "related_entity": related_entity,
            "evidence": {
                "document_id": evidence.get("document_id") or f"partner:{partner_id}:event",
                "page": evidence.get("page"),
                "section": evidence.get("section") or "event",
                "snippet": evidence.get("snippet") or str(ev.get("summary") or event_type),
                "method": evidence.get("method") or "partner_api",
                "confidence": evidence.get("confidence", 0.7),
            },
        }
        facts.append(fact)
    return facts

def _ensure_facts(payload: Dict[str, Any], partner_id: str) -> Dict[str, Any]:
    if isinstance(payload.get("facts"), list) and payload.get("facts"):
        return payload
    events = payload.get("events")
    if isinstance(events, list) and events:
        payload["facts"] = _events_to_facts(events, partner_id)
    else:
        payload.setdefault("facts", [])
    return payload

def verify_partner_api_key(
    api_key: Optional[str],
    *,
    db: Optional[Any] = None,
    partner_id: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> PartnerAuthResult:
    """
    Backward-compatible wrapper for partner API key verification.
    Supports env allow-list and DB-backed registry.
    """
    return _verify_partner_api_key(db=db, api_key=api_key, partner_id=partner_id, user_agent=user_agent)


@dataclass
class PartnerIngestResult:
    unified: UnifiedConversionResult
    normalized: Dict[str, Any]
    distill_facts_count: int
    needs_review: bool


async def convert_partner_payload(
    *,
    payload: Dict[str, Any],
    source: str = "partner",
    category: Optional[str] = None,
    document_type: Optional[str] = None,
    partner_id: Optional[str] = None,
) -> PartnerIngestResult:
    """
    Convert a structured partner payload into Preciso normalized/distill/spokes/exports.

    Expected payload shape (minimum):
    - company (str) OR entity (str) OR title (str)
    - facts: list[dict] (recommended; can be empty but will be marked needs_review)
    - tables: optional list[dict]
    - metadata: optional dict
    """
    payload = _ensure_facts(dict(payload), partner_id or "partner")
    payload, quality = normalize_partner_payload(
        payload,
        category=category,
        partner_id=partner_id or "partner",
    )
    document = {
        "content": payload,
        "content_base64": None,
        "file_bytes": None,
    }
    unified = await UnifiedConversionEngine().convert_document(
        document=document,
        source=source,
        filename=payload.get("filename") or "partner_payload.json",
        mime_type="application/json",
        run_snorkel=False,
    )

    normalized = unified.normalized or {}
    meta = (normalized.get("metadata") or {}) if isinstance(normalized, dict) else {}
    if not isinstance(meta, dict):
        meta = {"source": source}
    meta.setdefault("source", source)
    if category:
        meta.setdefault("category", category)
    if document_type:
        meta.setdefault("document_type", document_type)
    meta.setdefault("ingested_at", _utc_now_iso())
    normalized["metadata"] = meta

    fact_count = len(unified.distill.facts or [])
    needs_review = bool(meta.get("needs_review")) or fact_count == 0 or quality.needs_review
    return PartnerIngestResult(
        unified=unified,
        normalized=normalized,
        distill_facts_count=fact_count,
        needs_review=needs_review,
    )
