from __future__ import annotations

from typing import Any, Dict, Optional


def infer_category(fact: Dict[str, Any]) -> Optional[str]:
    metric = str(fact.get("metric") or fact.get("concept") or "").lower()
    unit = str(fact.get("unit") or "").lower()
    source = str(fact.get("source") or "").lower()
    entity = str(fact.get("entity") or "").strip()

    if not metric and not entity:
        return None

    # Events / corporate actions / disclosures
    if metric.startswith("event_") or unit == "event":
        return "event"

    # Ownership / technical flows
    if any(k in metric for k in ["short interest", "insider", "ownership", "13f", "flow", "buyback", "split"]):
        return "ownership"

    # Alternative data signals
    if any(k in metric for k in ["sentiment", "supply chain", "satellite", "esg", "geospatial"]):
        return "alternative"

    # Market data
    if any(k in metric for k in ["price", "open", "high", "low", "close", "ohlc", "volume", "order book", "vix", "option", "future", "open interest", "iv"]):
        return "market"

    # Macro (including FRED series)
    if "fred" in source:
        return "macro"
    if entity.isupper() and entity.replace("_", "").isalnum() and len(entity) <= 16 and unit in {"percent", "bps", "points", "index", "ratio"}:
        return "macro"

    # Fundamentals (default for classic statements/ratios)
    if any(k in metric for k in ["revenue", "sales", "income", "profit", "loss", "assets", "liabilities", "equity", "cash", "debt", "eps", "dividend", "roe", "pe", "guidance"]):
        return "fundamentals"

    return None


def apply_canonical_fields(fact: Dict[str, Any]) -> Dict[str, Any]:
    """
    Non-destructive canonicalization. Adds:
    - category (market/fundamentals/macro/event/alternative/ownership)

    Keeps existing fields unchanged for backward compatibility.
    """
    payload = dict(fact)
    if not payload.get("category"):
        cat = infer_category(payload)
        if cat:
            payload["category"] = cat
    return payload

