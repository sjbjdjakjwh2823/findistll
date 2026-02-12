from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.date_utils import normalize_period_loose


@dataclass
class DomainQuality:
    needs_review: bool = False
    reasons: List[str] = field(default_factory=list)

    def mark(self, reason: str) -> None:
        if reason not in self.reasons:
            self.reasons.append(reason)
        self.needs_review = True


def _normalize_period(period: Optional[str]) -> Optional[str]:
    return normalize_period_loose(period)


def _is_number_like(value: Any) -> bool:
    if value is None:
        return False
    try:
        if isinstance(value, (int, float)):
            return True
        txt = str(value).strip()
        if not txt:
            return False
        txt = txt.replace(",", "").replace("$", "").replace("USD", "").replace("KRW", "").replace("%", "").strip()
        txt = txt.replace("(", "").replace(")", "").strip()
        if not txt:
            return False
        float(txt)
        return True
    except Exception:
        return False


def _normalize_unit(unit: Optional[str]) -> Optional[str]:
    if not unit:
        return None
    u = str(unit).strip()
    if not u:
        return None
    lower = u.lower()
    if lower in ("%", "pct", "percent"):
        return "percent"
    if lower in ("ratio", "multiple"):
        return "ratio"
    if lower in ("usd", "krw", "eur", "jpy"):
        return u.upper()
    return u


def _default_unit(metric: str) -> Tuple[Optional[str], Optional[str]]:
    m = (metric or "").lower()
    if any(k in m for k in ("price", "close", "open", "high", "low")):
        return "USD", "USD"
    if "volume" in m:
        return "shares", None
    if any(k in m for k in ("rate", "yield", "percent", "pct")):
        return "percent", None
    if any(k in m for k in ("icr", "ratio", "multiple")):
        return "ratio", None
    if "event:" in m:
        return "event", None
    return None, None


def normalize_partner_payload(
    payload: Dict[str, Any],
    *,
    category: Optional[str],
    partner_id: str,
    default_currency: str = "USD",
) -> Tuple[Dict[str, Any], DomainQuality]:
    quality = DomainQuality()
    out = dict(payload)
    meta = out.get("metadata") if isinstance(out.get("metadata"), dict) else {}
    meta = dict(meta)
    meta.setdefault("schema_version", "domain_v1")
    if category:
        meta["category"] = category
    meta.setdefault("source", meta.get("source") or "partner_api")
    out["metadata"] = meta

    entity = out.get("company") or out.get("entity") or out.get("title")
    if not entity:
        quality.mark("missing_entity")
        entity = "unknown"

    facts = out.get("facts")
    if not isinstance(facts, list):
        facts = []
    normalized_facts: List[Dict[str, Any]] = []
    required_fields_by_category = {
        "market": ["entity", "metric", "period_norm", "value", "unit", "evidence"],
        "fundamentals": ["entity", "metric", "period_norm", "value", "unit", "currency", "evidence"],
        "macro": ["entity", "metric", "period_norm", "value", "unit", "evidence"],
        "event": ["entity", "event_type", "announced_at", "effective_at", "evidence"],
        "alternative": ["entity", "metric", "period_norm", "value", "evidence"],
    }
    for f in facts:
        if not isinstance(f, dict):
            quality.mark("invalid_fact_type")
            continue
        fact = dict(f)
        fact_needs_review = False
        fact.setdefault("entity", entity)
        if category:
            fact.setdefault("category", category)
        metric = fact.get("metric") or fact.get("concept") or fact.get("label")
        if not metric:
            quality.mark("missing_metric")
            fact_needs_review = True
            metric = "unknown_metric"
        fact["metric"] = metric

        value = fact.get("value")
        if value is None:
            quality.mark("missing_value")
            fact_needs_review = True
        if category in ("market", "fundamentals", "macro") and value is not None and not _is_number_like(value):
            quality.mark("non_numeric_value")
            fact_needs_review = True

        period = fact.get("period") or fact.get("date") or fact.get("as_of")
        period_norm = fact.get("period_norm") or _normalize_period(period)
        if not period_norm:
            quality.mark("missing_period")
            fact_needs_review = True
        fact["period"] = period or period_norm
        if period_norm:
            fact["period_norm"] = period_norm

        unit = _normalize_unit(fact.get("unit"))
        currency = fact.get("currency")
        if not unit:
            unit, inferred_currency = _default_unit(metric)
            if unit:
                fact["unit"] = unit
            if not currency and inferred_currency:
                currency = inferred_currency
            if not unit:
                quality.mark("missing_unit")
                fact_needs_review = True
        else:
            fact["unit"] = unit
        if not currency and unit in ("USD", "currency"):
            currency = default_currency
        if currency:
            fact["currency"] = currency

        evidence = fact.get("evidence") if isinstance(fact.get("evidence"), dict) else {}
        evidence = dict(evidence)
        evidence.setdefault("document_id", evidence.get("document_id") or f"partner:{partner_id}:{category or 'payload'}")
        evidence.setdefault("method", evidence.get("method") or "partner_api")
        if not evidence.get("snippet"):
            evidence["snippet"] = f"{metric}={value}"
            quality.mark("evidence_snippet_generated")
            fact_needs_review = True
        evidence.setdefault("confidence", evidence.get("confidence", 0.7))
        try:
            conf = float(evidence.get("confidence", 0.7))
            if conf < 0.5:
                quality.mark("low_confidence")
                fact_needs_review = True
        except Exception:
            quality.mark("invalid_confidence")
            fact_needs_review = True
        fact["evidence"] = evidence

        if not evidence.get("snippet"):
            quality.mark("missing_evidence_snippet")
            fact_needs_review = True
        if fact_needs_review:
            fact["needs_review"] = True
        normalized_facts.append(fact)

    out["facts"] = normalized_facts
    if not normalized_facts:
        quality.mark("empty_facts")

    # Validate events list if present (event domain schema)
    events = out.get("events")
    if isinstance(events, list) and events:
        normalized_events = []
        for ev in events:
            if not isinstance(ev, dict):
                quality.mark("invalid_event_type")
                continue
            ev_row = dict(ev)
            ev_row.setdefault("entity", entity)
            ev_row.setdefault("category", category or "event")
            if not ev_row.get("event_type"):
                quality.mark("missing_event_type")
                ev_row["needs_review"] = True
            if not ev_row.get("announced_at"):
                quality.mark("missing_announced_at")
                ev_row["needs_review"] = True
            if not ev_row.get("effective_at"):
                quality.mark("missing_effective_at")
                ev_row["needs_review"] = True
            evidence = ev_row.get("evidence") if isinstance(ev_row.get("evidence"), dict) else {}
            evidence = dict(evidence)
            evidence.setdefault("document_id", evidence.get("document_id") or f"partner:{partner_id}:event")
            evidence.setdefault("method", evidence.get("method") or "partner_api")
            if not evidence.get("snippet"):
                evidence["snippet"] = f"{ev_row.get('event_type', 'event')}"
                quality.mark("evidence_snippet_generated")
                ev_row["needs_review"] = True
            ev_row["evidence"] = evidence
            normalized_events.append(ev_row)
        out["events"] = normalized_events

    # Apply required field checks by domain.
    domain = (category or "").lower() if category else None
    required = required_fields_by_category.get(domain or "", [])
    for fact in normalized_facts:
        for key in required:
            if key == "evidence":
                if not isinstance(fact.get("evidence"), dict):
                    quality.mark("missing_evidence")
                    fact["needs_review"] = True
                continue
            if key == "period_norm" and not fact.get("period_norm"):
                quality.mark("missing_period")
                fact["needs_review"] = True
                continue
            if fact.get(key) in (None, ""):
                quality.mark(f"missing_{key}")
                fact["needs_review"] = True

    if quality.needs_review:
        meta["needs_review"] = True
        meta["quality_reasons"] = quality.reasons
    out["metadata"] = meta
    return out, quality
