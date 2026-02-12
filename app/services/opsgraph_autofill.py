from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple


_NS_ENTITIES = uuid.UUID("7f7d1b0a-91e5-4df7-8f11-2d4d3fd2c7b6")
_NS_CASES = uuid.UUID("dfe0b56d-0af9-4e3c-bf4c-1a1b5a7443ae")
_NS_RELS = uuid.UUID("c2b04ea7-773c-4ab4-86c9-9e6941d4ee35")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_uuid(namespace: uuid.UUID, name: str) -> str:
    return str(uuid.uuid5(namespace, name))


def _safe_str(v: Any) -> str:
    try:
        return str(v).strip()
    except Exception:
        return ""


def _extract_counterparties(fact: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Extract (relationship_type, counterparty_name) pairs from a fact.
    """
    pairs: List[Tuple[str, str]] = []

    vendor = _safe_str(fact.get("vendor") or fact.get("supplier"))
    if vendor:
        pairs.append(("supplied_by", vendor))

    customer = _safe_str(fact.get("customer"))
    if customer:
        pairs.append(("supplies", customer))

    parent = _safe_str(fact.get("parent"))
    if parent:
        pairs.append(("subsidiary_of", parent))

    sub = _safe_str(fact.get("subsidiary"))
    if sub:
        pairs.append(("parent_of", sub))

    related = _safe_str(fact.get("related_entity") or fact.get("counterparty"))
    if related:
        pairs.append(("related_to", related))

    region = _safe_str(fact.get("region"))
    if region:
        pairs.append(("operates_in", region))

    segment = _safe_str(fact.get("segment"))
    if segment:
        pairs.append(("has_segment", segment))

    return pairs


def ensure_ops_entity(
    *,
    client: Any,
    tenant_id: str,
    entity_type: str,
    name: str,
    properties: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Idempotently ensure an ops_entities row exists and return its UUID.
    Uses deterministic UUIDv5 to avoid duplicates without relying on a unique constraint.
    """
    name = _safe_str(name)
    entity_type = _safe_str(entity_type) or "entity"
    if not name:
        raise ValueError("name is required")

    ent_id = stable_uuid(_NS_ENTITIES, f"{tenant_id}:{entity_type}:{name.lower()}")
    payload = {
        "id": ent_id,
        "entity_type": entity_type,
        "name": name,
        "properties": properties or {},
        "updated_at": _utc_now_iso(),
    }
    # Upsert on primary key (id) is supported.
    client.table("ops_entities").upsert(payload).execute()
    return ent_id


def ensure_ops_relationship(
    *,
    client: Any,
    tenant_id: str,
    source_id: str,
    target_id: str,
    relationship_type: str,
    properties: Optional[Dict[str, Any]] = None,
    confidence: float = 0.5,
) -> str:
    rel_key = f"{tenant_id}:{source_id}:{target_id}:{relationship_type}"
    rel_id = stable_uuid(_NS_RELS, rel_key)
    payload = {
        "id": rel_id,
        "source_id": source_id,
        "target_id": target_id,
        "relationship_type": relationship_type,
        "properties": properties or {},
        "confidence": float(confidence or 0.5),
        "created_at": _utc_now_iso(),
    }
    client.table("ops_relationships").upsert(payload).execute()
    return rel_id


def ensure_ops_case(
    *,
    client: Any,
    tenant_id: str,
    case_id: str,
    title: str,
    entity_id: Optional[str],
    priority: str = "medium",
    status: str = "open",
) -> str:
    """
    Bridge DataForge `cases(case_id TEXT)` to OpsGraph `ops_cases(id UUID)`.
    """
    stable_id = stable_uuid(_NS_CASES, f"{tenant_id}:{case_id}")
    payload: Dict[str, Any] = {
        "id": stable_id,
        "title": title or "Untitled",
        "status": status or "open",
        "priority": priority or "medium",
        "entity_id": entity_id,
        "updated_at": _utc_now_iso(),
    }
    client.table("ops_cases").upsert(payload).execute()
    return stable_id


def autofill_opsgraph(
    *,
    client: Any,
    tenant_id: str,
    case_id: str,
    title: str,
    company: str,
    facts: List[Dict[str, Any]],
    graph_triples: List[Dict[str, Any]],
) -> Dict[str, int]:
    """
    Populate OpsGraph tables from Distill facts + extracted triples.
    This enables Supabase 3-hop graph reasoning (`kg_relationships`) to become non-empty.
    """
    counts = {"entities": 0, "relationships": 0, "ops_cases": 0}

    company_id = ensure_ops_entity(
        client=client,
        tenant_id=tenant_id,
        entity_type="company",
        name=company,
        properties={},
    )
    counts["entities"] += 1

    ensure_ops_case(
        client=client,
        tenant_id=tenant_id,
        case_id=case_id,
        title=title or company,
        entity_id=company_id,
        priority="medium",
        status="open",
    )
    counts["ops_cases"] += 1

    # Facts -> relationships
    for fact in facts or []:
        if not isinstance(fact, dict):
            continue
        for rel_type, counterparty in _extract_counterparties(fact):
            try:
                cp_id = ensure_ops_entity(
                    client=client,
                    tenant_id=tenant_id,
                    entity_type="company" if rel_type not in {"operates_in", "has_segment"} else "event",
                    name=counterparty,
                    properties={"source": fact.get("source"), "metric": fact.get("metric")},
                )
                counts["entities"] += 1
                ensure_ops_relationship(
                    client=client,
                    tenant_id=tenant_id,
                    source_id=company_id,
                    target_id=cp_id,
                    relationship_type=rel_type,
                    properties={"evidence": fact.get("evidence"), "metric": fact.get("metric")},
                    confidence=float(fact.get("confidence_score") or (fact.get("evidence") or {}).get("confidence") or 0.6),
                )
                counts["relationships"] += 1
            except Exception:
                continue

        # Events as first-class nodes
        metric = _safe_str(fact.get("metric") or fact.get("concept"))
        unit = _safe_str(fact.get("unit"))
        if metric.startswith("event_") or unit == "event":
            event_name = _safe_str(fact.get("value") or metric) or metric
            period = _safe_str(fact.get("period_norm") or fact.get("period"))
            ev_id = ensure_ops_entity(
                client=client,
                tenant_id=tenant_id,
                entity_type="event",
                name=f"{metric}:{period}:{event_name}" if period else f"{metric}:{event_name}",
                properties={"metric": metric, "period": period, "evidence": fact.get("evidence")},
            )
            counts["entities"] += 1
            ensure_ops_relationship(
                client=client,
                tenant_id=tenant_id,
                source_id=company_id,
                target_id=ev_id,
                relationship_type="has_event",
                properties={"metric": metric, "period": period},
                confidence=float((fact.get("evidence") or {}).get("confidence") or 0.7),
            )
            counts["relationships"] += 1

    # Triples -> relationships (lightweight mapping)
    for triple in graph_triples or []:
        head = _safe_str(triple.get("head_node"))
        tail = _safe_str(triple.get("tail_node"))
        rel = _safe_str(triple.get("relation")) or "related_to"
        if not head or not tail:
            continue
        # Prefer using company as anchor to avoid generating huge graphs from numeric tails.
        if head.lower() != company.lower() and tail.lower() != company.lower():
            continue
        try:
            other = tail if head.lower() == company.lower() else head
            other_id = ensure_ops_entity(
                client=client,
                tenant_id=tenant_id,
                entity_type="company",
                name=other,
                properties={"source": (triple.get("properties") or {}).get("source")},
            )
            counts["entities"] += 1
            ensure_ops_relationship(
                client=client,
                tenant_id=tenant_id,
                source_id=company_id,
                target_id=other_id,
                relationship_type=rel,
                properties=triple.get("properties") or {},
                confidence=float((triple.get("properties") or {}).get("confidence") or 0.6),
            )
            counts["relationships"] += 1
        except Exception:
            continue

    return counts

