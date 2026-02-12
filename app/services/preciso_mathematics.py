from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        if cleaned == "":
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _parse_period_key(period: str) -> Optional[Tuple[int, int, int]]:
    if not period:
        return None
    text = str(period).strip()
    import re

    match = re.match(r"^(\d{4})[-/]?Q([1-4])$", text, re.IGNORECASE)
    if match:
        year = int(match.group(1))
        quarter = int(match.group(2))
        return (year, quarter * 3, 2)
    match = re.match(r"^Q([1-4])[-/\s]?(\d{4})$", text, re.IGNORECASE)
    if match:
        quarter = int(match.group(1))
        year = int(match.group(2))
        return (year, quarter * 3, 2)
    match = re.match(r"^(\d{4})[-/](\d{1,2})$", text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        return (year, month, 3)
    match = re.match(r"^(\d{4})$", text)
    if match:
        return (int(match.group(1)), 0, 1)
    return None


def _sort_periods(periods: List[str]) -> List[str]:
    annotated: List[Tuple[Optional[Tuple[int, int, int]], str]] = []
    for p in periods:
        annotated.append((_parse_period_key(p), p))

    def key(item: Tuple[Optional[Tuple[int, int, int]], str]) -> Tuple[int, int, int, str]:
        k, raw = item
        if k is None:
            return (9999, 99, 9, raw)
        return (k[0], k[1], k[2], raw)

    annotated.sort(key=key)
    return [raw for _, raw in annotated]


def visibility_graph_edges(values: List[float]) -> List[Tuple[int, int]]:
    """Natural visibility graph (Lacasa 2008). O(n^2) deterministic."""
    edges: List[Tuple[int, int]] = []
    n = len(values)
    for a in range(n):
        ya = values[a]
        for b in range(a + 1, n):
            yb = values[b]
            visible = True
            for c in range(a + 1, b):
                yc = values[c]
                # yc < yb + (ya - yb) * (b - c) / (b - a)
                rhs = yb + (ya - yb) * (b - c) / (b - a)
                if yc >= rhs:
                    visible = False
                    break
            if visible:
                edges.append((a, b))
    return edges


def exponential_gradient_update(weights: List[float], price_relatives: List[float], eta: float = 0.05) -> List[float]:
    """EG update from Online Portfolio Selection survey (Li & Hoi 2012)."""
    if len(weights) != len(price_relatives) or not weights:
        return weights
    denom = sum(w * x for w, x in zip(weights, price_relatives))
    if denom <= 0:
        return weights
    updated = [w * math.exp(eta * (x / denom)) for w, x in zip(weights, price_relatives)]
    z = sum(updated)
    if z <= 0:
        return weights
    return [u / z for u in updated]


@dataclass
class MathematicsAnalysis:
    series: Dict[str, Dict[str, Dict[str, float]]]
    derived: Dict[str, Any]
    visibility_graph: Dict[str, Any]


class PrecisoMathematicsService:
    """
    Apply "Preciso Mathematics" to extracted facts:
    - build time-series by entity/metric/period
    - compute deterministic derived metrics (growth/returns/z-score)
    - convert time-series to visibility graphs for graph/RAG use
    """

    def analyze(self, facts: List[Dict[str, Any]]) -> MathematicsAnalysis:
        series = self._extract_numeric_series(facts)
        derived: Dict[str, Any] = {}
        vg: Dict[str, Any] = {}

        for entity, metrics in series.items():
            for metric, points in metrics.items():
                periods = _sort_periods(list(points.keys()))
                values = [points[p] for p in periods]
                key = f"{entity}::{metric}"

                if len(values) >= 2:
                    derived[key] = {
                        "periods": periods,
                        "values": values,
                        "pct_change": self._pct_changes(values),
                        "log_returns": self._log_returns(values),
                        "zscore": self._zscore(values),
                    }

                if len(values) >= 3:
                    edges = visibility_graph_edges(values)
                    vg[key] = {
                        "nodes": [{"idx": i, "period": periods[i], "value": values[i]} for i in range(len(values))],
                        "edges": [{"src": a, "dst": b} for a, b in edges],
                        "edge_count": len(edges),
                    }

        return MathematicsAnalysis(series=series, derived=derived, visibility_graph=vg)

    def _extract_numeric_series(self, facts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, float]]]:
        series: Dict[str, Dict[str, Dict[str, float]]] = {}
        import re

        def looks_like_financial_metric(text: str, *, source: str = "") -> bool:
            s = (text or "").strip()
            if not s:
                return False
            if len(s) > 80:
                return False
            # Too many words tends to be headers/boilerplate.
            if len(s.split()) > 8:
                return False
            lower = s.lower()
            source_lower = (source or "").lower()

            block = [
                "commission", "pursuant", "section", "form", "address", "suite", "washington",
                "telephone", "phone", "zip", "file", "fiscal year ended", "transition report",
                "annual report", "quarterly report", "part i", "part ii",
                "operating system", "watchos", "ios", "macos", "ipados",
            ]
            if any(b in lower for b in block):
                return False
            # Allow common financial statement line items.
            allow = [
                "revenue", "sales", "income", "profit", "loss", "expense", "assets", "liabilities",
                "equity", "cash", "debt", "interest", "ebit", "ebitda", "margin", "eps",
                "shares", "operating", "dividend", "tax", "capex",
                "total", "net", "current", "noncurrent", "cost", "gross", "cash flow", "free cash",
                "gaap", "non-gaap", "diluted", "basic",
                # Market / macro / technical (enterprise deployment needs these in the same math pipeline)
                "price", "close", "open", "high", "low", "volume", "vix",
                "rate", "yield", "spread", "premium", "open interest",
                "cpi", "ppi", "inflation", "gdp", "unemployment", "fx", "exchange",
                "short interest", "insider", "ownership", "flow",
                "sentiment", "supply chain",
            ]
            if any(a in lower for a in allow):
                return True

            # Provider-specific metric codes (e.g., FRED series IDs) should still be eligible
            # for deterministic derived features, otherwise macro/market spokes miss the math layer.
            if "fred" in source_lower:
                if re.fullmatch(r"[A-Z0-9_]{2,16}", s):
                    return True
            return False

        for fact in facts or []:
            if not isinstance(fact, dict):
                continue
            entity = fact.get("entity") or fact.get("company") or fact.get("issuer") or fact.get("ticker")
            metric = fact.get("metric") or fact.get("label") or fact.get("concept")
            period = (
                fact.get("period_norm")
                or fact.get("period")
                or fact.get("fiscal_period")
                or fact.get("as_of")
                or fact.get("date")
            )
            unit = fact.get("unit")
            source = str(fact.get("source") or "")
            value = None
            for key in ("value", "amount", "number", "metric_value"):
                value = _to_float(fact.get(key))
                if value is not None:
                    break
            if entity and metric and period and value is not None:
                if unit:
                    u = str(unit).strip().lower()
                    # Accept ISO currency codes (usd/krw/eur/...) as currency for derived features,
                    # otherwise time-series math disappears for many realistic payloads.
                    iso_ccy = len(u) == 3 and u.isalpha()
                    if u not in (
                        "currency",
                        "ratio",
                        "shares",
                        "percent",
                        "bps",
                        "points",
                        "index",
                        "count",
                    ) and not iso_ccy:
                        continue
                if not looks_like_financial_metric(str(metric), source=source):
                    continue
                series.setdefault(str(entity), {}).setdefault(str(metric), {})[str(period)] = value
        return series

    def _pct_changes(self, values: List[float]) -> List[Optional[float]]:
        out: List[Optional[float]] = [None]
        for i in range(1, len(values)):
            prev = values[i - 1]
            cur = values[i]
            if prev == 0:
                out.append(None)
            else:
                out.append((cur - prev) / abs(prev))
        return out

    def _log_returns(self, values: List[float]) -> List[Optional[float]]:
        out: List[Optional[float]] = [None]
        for i in range(1, len(values)):
            prev = values[i - 1]
            cur = values[i]
            if prev <= 0 or cur <= 0:
                out.append(None)
            else:
                out.append(math.log(cur / prev))
        return out

    def _zscore(self, values: List[float]) -> List[Optional[float]]:
        if len(values) < 2:
            return [None for _ in values]
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(var)
        if std == 0:
            return [0.0 for _ in values]
        return [(v - mean) / std for v in values]
