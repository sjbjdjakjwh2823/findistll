from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class SpokesEngine:
    """Builds and time-gates graph edges from extracted facts (Spoke D)."""

    def build_graph_edges(
        self,
        case_id: str,
        facts: List[Dict[str, Any]],
        document: Optional[Dict[str, Any]] = None,
        self_reflection: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        edges: List[Dict[str, Any]] = []
        doc_id = (document or {}).get("doc_id")
        reflection_context = self._build_reflection_context(self_reflection)

        for fact in facts:
            edge = self._fact_to_edge(
                case_id=case_id,
                doc_id=doc_id,
                fact=fact,
                reflection_context=reflection_context,
            )
            if edge:
                edges.append(edge)

        return self._dedupe_edges(edges)

    def gate_edges_as_of(self, edges: List[Dict[str, Any]], as_of: datetime) -> List[Dict[str, Any]]:
        """TimeGate-style filter: keep only edges valid at as_of."""
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)

        visible: List[Dict[str, Any]] = []
        for edge in edges:
            valid_from = self._safe_parse_dt(edge.get("valid_from"))
            valid_to = self._safe_parse_dt(edge.get("valid_to"))

            if valid_from and valid_from > as_of:
                continue
            if valid_to and valid_to < as_of:
                continue
            visible.append(edge)
        return visible

    def _fact_to_edge(
        self,
        case_id: str,
        doc_id: Optional[str],
        fact: Dict[str, Any],
        reflection_context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        head = self._as_str(fact.get("head_node") or fact.get("entity") or fact.get("subject"))
        relation = self._as_str(fact.get("relation") or fact.get("metric") or fact.get("predicate"))
        tail_raw = fact.get("tail_node") or fact.get("value") or fact.get("object")
        tail = self._as_str(tail_raw)

        if not head or not relation or not tail:
            statement = self._as_str(fact.get("statement"))
            if not statement:
                return None
            head = head or self._as_str(fact.get("entity") or "unknown_entity")
            relation = relation or "states"
            tail = tail or statement

        temporal = self._extract_temporal_fields(fact)
        temporal_quality = self._score_temporal_quality(temporal)
        reflection_quality = self._score_reflection_quality(fact, reflection_context)
        edge_weight = self._compose_edge_weight(fact, temporal_quality, reflection_quality)

        properties = dict(fact)
        properties.pop("head_node", None)
        properties.pop("relation", None)
        properties.pop("tail_node", None)
        properties["temporal_quality"] = temporal_quality
        properties["reflection_quality"] = reflection_quality
        properties["edge_weight"] = edge_weight

        return {
            "case_id": case_id,
            "doc_id": doc_id,
            "head_node": head,
            "relation": relation,
            "tail_node": tail,
            "properties": properties,
            "event_time": temporal.get("event_time"),
            "valid_from": temporal.get("valid_from"),
            "valid_to": temporal.get("valid_to"),
            "observed_at": temporal.get("observed_at"),
            "time_source": temporal.get("time_source"),
            "time_granularity": temporal.get("time_granularity"),
        }

    def _build_reflection_context(self, self_reflection: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        raw = self_reflection or {}
        output_count = raw.get("output_count")
        input_count = raw.get("input_count")
        issues_sum = 0
        for row in raw.get("history", []):
            issues_sum += int(row.get("issues_found", 0))

        repair_ratio = 0.0
        if isinstance(output_count, int) and isinstance(input_count, int) and input_count > 0:
            repair_ratio = max(min(output_count / input_count, 1.0), 0.0)

        return {
            "rounds_executed": int(raw.get("rounds_executed", 0)),
            "issues_found": issues_sum,
            "repair_ratio": repair_ratio,
        }

    def _score_temporal_quality(self, temporal: Dict[str, Any]) -> float:
        score = 0.2
        if temporal.get("event_time"):
            score += 0.35
        if temporal.get("valid_from"):
            score += 0.25
        if temporal.get("valid_to"):
            score += 0.1
        if temporal.get("time_granularity") in ("quarter", "month", "day"):
            score += 0.1
        return max(0.0, min(score, 1.0))

    def _score_reflection_quality(self, fact: Dict[str, Any], reflection_context: Dict[str, Any]) -> float:
        score = 0.5

        confidence = self._as_str(fact.get("confidence")).lower()
        if confidence == "high":
            score += 0.25
        elif confidence == "medium":
            score += 0.15
        elif confidence == "low":
            score += 0.05

        issues = fact.get("reflection_issues")
        if isinstance(issues, list):
            score -= min(len(issues) * 0.08, 0.24)

        rounds_executed = int(reflection_context.get("rounds_executed", 0))
        if rounds_executed > 0:
            score += min(rounds_executed * 0.03, 0.09)

        repair_ratio = reflection_context.get("repair_ratio")
        if isinstance(repair_ratio, (int, float)):
            score += float(repair_ratio) * 0.06

        return max(0.0, min(score, 1.0))

    def _compose_edge_weight(self, fact: Dict[str, Any], temporal_quality: float, reflection_quality: float) -> float:
        base = 0.25
        if fact.get("statement"):
            base += 0.1
        if fact.get("validation_status") == "reflected":
            base += 0.05
        total = base + (temporal_quality * 0.3) + (reflection_quality * 0.3)
        return round(max(0.05, min(total, 0.98)), 4)

    def _extract_temporal_fields(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        event_time = self._safe_parse_dt(
            fact.get("event_time")
            or fact.get("date")
            or fact.get("as_of")
            or fact.get("timestamp")
            or fact.get("observed_at")
        )
        valid_from = self._safe_parse_dt(
            fact.get("valid_from")
            or fact.get("start_date")
            or fact.get("period_start")
        )
        valid_to = self._safe_parse_dt(
            fact.get("valid_to")
            or fact.get("end_date")
            or fact.get("period_end")
        )

        if not event_time:
            period = self._as_str(fact.get("period"))
            event_time = self._parse_period_to_dt(period)

        if not valid_from and event_time:
            valid_from = event_time
        # Keep open-ended validity unless an explicit end is provided.
        # This avoids dropping point-in-time facts immediately after event_time.
        if valid_from and not valid_to:
            valid_to = None

        source_key = "period"
        if any(fact.get(k) for k in ("event_time", "date", "as_of", "timestamp", "observed_at")):
            source_key = "event_time"
        elif any(fact.get(k) for k in ("valid_from", "start_date", "period_start")):
            source_key = "valid_from"

        granularity = self._infer_time_granularity(fact)

        return {
            "event_time": self._to_iso(event_time),
            "valid_from": self._to_iso(valid_from),
            "valid_to": self._to_iso(valid_to),
            "observed_at": self._to_iso(datetime.now(timezone.utc)),
            "time_source": source_key,
            "time_granularity": granularity,
        }

    def _infer_time_granularity(self, fact: Dict[str, Any]) -> str:
        period = self._as_str(fact.get("period"))
        if not period:
            return "day"
        low = period.lower()
        if "q" in low and any(ch.isdigit() for ch in low):
            return "quarter"
        if "-" not in period and len(period) == 4 and period.isdigit():
            return "year"
        if len(period) >= 7 and period[4:5] in ("-", "/"):
            return "month"
        return "day"

    def _parse_period_to_dt(self, period: str) -> Optional[datetime]:
        if not period:
            return None
        text = period.strip()

        if len(text) == 4 and text.isdigit():
            return datetime(int(text), 1, 1, tzinfo=timezone.utc)

        quarter_map = {"Q1": "01-01", "Q2": "04-01", "Q3": "07-01", "Q4": "10-01"}
        for q, suffix in quarter_map.items():
            if q in text.upper():
                year = "".join(ch for ch in text if ch.isdigit())[:4]
                if len(year) == 4:
                    return self._safe_parse_dt(f"{year}-{suffix}")

        return self._safe_parse_dt(text)

    def _safe_parse_dt(self, value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None

        candidates = [
            text,
            text.replace("Z", "+00:00"),
        ]
        for cand in candidates:
            try:
                parsed = datetime.fromisoformat(cand)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y/%m", "%Y%m%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        return None

    def _to_iso(self, dt: Optional[datetime]) -> Optional[str]:
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()

    def _dedupe_edges(self, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        deduped: List[Dict[str, Any]] = []

        for edge in edges:
            sig = "|".join(
                [
                    self._as_str(edge.get("case_id")),
                    self._as_str(edge.get("doc_id")),
                    self._as_str(edge.get("head_node")),
                    self._as_str(edge.get("relation")),
                    self._as_str(edge.get("tail_node")),
                    self._as_str(edge.get("valid_from")),
                    self._as_str(edge.get("valid_to")),
                ]
            )
            if sig in seen:
                continue
            seen.add(sig)
            deduped.append(edge)

        return deduped

    def _as_str(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()
