from __future__ import annotations

import re
import logging
from collections import Counter
import math
import random
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.services.types import DecisionResult, DistillResult
from app.services.preciso_mathematics import PrecisoMathematicsService

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "is", "it", "of", "on", "or", "that", "the",
    "to", "was", "were", "with", "this", "these", "those", "its",
}


def _first_present(data: Dict[str, Any], keys: Iterable[str]) -> Optional[str]:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        return str(value)
    return None


def extract_keywords(text: str, max_keywords: int = 12) -> List[str]:
    tokens = re.findall(r"[A-Za-z0-9]{2,}", text.lower())
    tokens = [t for t in tokens if t not in _STOPWORDS]
    if not tokens:
        return []
    counts = Counter(tokens)
    return [token for token, _ in counts.most_common(max_keywords)]


def _fact_to_text(fact: Any) -> str:
    if isinstance(fact, dict):
        parts = []
        for key in sorted(fact.keys()):
            value = fact.get(key)
            parts.append(f"{key}: {value}")
        return " | ".join(parts)
    return str(fact)


def _sanitize_english(text: Optional[str]) -> str:
    if not text:
        return ""
    safe_chars: List[str] = []
    for ch in text:
        if ch in ("\n", "\t"):
            safe_chars.append(ch)
        elif 32 <= ord(ch) < 127:
            safe_chars.append(ch)
        else:
            safe_chars.append(" ")
    sanitized = "".join(safe_chars)
    lines = []
    for line in sanitized.splitlines():
        lines.append(re.sub(r"[ \t]+", " ", line).strip())
    return "\n".join(lines).strip()


def _normalize_id(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", text.strip().lower()).strip("-")
    return cleaned or "unknown"


def _node_id(node_type: str, name: str) -> str:
    return f"{node_type.lower()}:{_normalize_id(name)}"


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


def _sort_periods(periods: Iterable[str]) -> List[str]:
    annotated = []
    for period in periods:
        key = _parse_period_key(period)
        annotated.append((key, period))
    def _sort_key(item: Tuple[Optional[Tuple[int, int, int]], str]) -> Tuple[int, int, int, str]:
        key, raw = item
        if key is None:
            return (9999, 99, 9, raw)
        return (key[0], key[1], key[2], raw)
    annotated.sort(key=_sort_key)
    return [raw for _, raw in annotated]


def _pearson_corr(xs: List[float], ys: List[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    num = 0.0
    denom_x = 0.0
    denom_y = 0.0
    for x, y in zip(xs, ys):
        dx = x - mean_x
        dy = y - mean_y
        num += dx * dy
        denom_x += dx * dx
        denom_y += dy * dy
    denom = math.sqrt(denom_x * denom_y)
    if denom == 0:
        return 0.0
    return num / denom


def _bootstrap_confidence(xs: List[float], ys: List[float], samples: int = 40) -> float:
    if len(xs) < 3:
        return 0.0
    rng = random.Random(42)
    correlations = []
    n = len(xs)
    for _ in range(samples):
        idxs = [rng.randrange(n) for _ in range(n)]
        sample_xs = [xs[i] for i in idxs]
        sample_ys = [ys[i] for i in idxs]
        correlations.append(_pearson_corr(sample_xs, sample_ys))
    mean = sum(correlations) / len(correlations)
    variance = sum((c - mean) ** 2 for c in correlations) / len(correlations)
    std = math.sqrt(variance)
    confidence = max(0.0, min(1.0, 1.0 - std))
    return confidence


def _extract_numeric_series(facts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, float]]]:
    series: Dict[str, Dict[str, Dict[str, float]]] = {}
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        entity = _first_present(fact, ["entity", "company", "issuer", "name", "ticker"])
        metric = _first_present(fact, ["metric", "fact", "type", "name", "label"])
        period = _first_present(fact, ["period", "fiscal_period", "date", "as_of"])
        value = None
        for key in ["value", "amount", "number", "metric_value"]:
            value = _to_float(fact.get(key))
            if value is not None:
                break
        if entity and metric and period and value is not None:
            series.setdefault(entity, {}).setdefault(metric, {})[str(period)] = value
    return series


def _normalize_relation(relation: str) -> str:
    lower = relation.lower()
    if any(token in lower for token in ["subsidiary", "parent", "segment", "region", "part of", "division"]):
        return "part_of"
    if any(token in lower for token in ["acquire", "merge", "partner", "owns", "owned by"]):
        return "affects"
    if any(token in lower for token in ["reported", "filed", "disclosed"]):
        return "reported_in"
    if any(token in lower for token in ["metric", "kpi", "ratio"]):
        return "has_metric"
    return "affects"


def _extract_rationales(text: str) -> List[str]:
    if not text:
        return []
    segments = re.split(r"(?<=[.!?])\s+", text.strip())
    return [seg.strip() for seg in segments if seg.strip()]


def build_rag_context(distill: DistillResult, case_id: str) -> List[Dict[str, Any]]:
    contexts: List[Dict[str, Any]] = []
    metadata = distill.metadata or {}

    for idx, fact in enumerate(distill.facts):
        if not isinstance(fact, dict):
            continue
        text_content = _fact_to_text(fact)
        entity = _first_present(fact, ["entity", "company", "issuer", "name", "ticker"])
        # Prefer normalized periods when present so downstream date alignment works.
        period = _first_present(fact, ["period_norm", "period", "fiscal_period", "date", "as_of"])
        source = _first_present(fact, ["source"]) or metadata.get("source", "distill")
        evidence = fact.get("evidence") if isinstance(fact, dict) else None
        keywords = extract_keywords(text_content)
        contexts.append(
            {
                "chunk_id": f"{case_id}-fact-{idx}",
                "entity": entity,
                "period": period,
                "source": source,
                "text_content": text_content,
                "keywords": keywords,
                "metadata": {
                    "evidence": evidence,
                    "doc_id": metadata.get("doc_id"),
                    "case_id": case_id,
                    "period_norm": fact.get("period_norm") or period,
                },
            }
        )

    if distill.cot_markdown:
        paragraphs = [p.strip() for p in distill.cot_markdown.split("\n\n") if p.strip()]
        for idx, paragraph in enumerate(paragraphs):
            text_content = paragraph
            entity = metadata.get("entity") or metadata.get("title")
            period = metadata.get("period") or metadata.get("fiscal_period")
            keywords = extract_keywords(text_content)
            contexts.append(
                {
                    "chunk_id": f"{case_id}-cot-{idx}",
                    "entity": entity,
                    "period": period,
                    "source": "cot",
                    "text_content": text_content,
                    "keywords": keywords,
                    "metadata": {
                        "doc_id": metadata.get("doc_id"),
                        "case_id": case_id,
                        "section": "cot",
                    },
                }
            )

    # Preciso Mathematics: numeric series + derived features as a dedicated evidence chunk.
    # This makes Spoke C useful for downstream quant/RAG consumers without requiring Parquet reads.
    try:
        analysis = PrecisoMathematicsService().analyze(distill.facts or [])
        derived = analysis.derived or {}
        if derived:
            keys = sorted(list(derived.keys()))[:12]
            for idx, key in enumerate(keys):
                payload = derived.get(key) or {}
                # key = "{entity}::{metric}"
                try:
                    entity, metric = key.split("::", 1)
                except ValueError:
                    entity, metric = metadata.get("entity") or metadata.get("title"), key
                periods = payload.get("periods") or []
                values = payload.get("values") or []
                pct = payload.get("pct_change") or []
                logret = payload.get("log_returns") or []
                z = payload.get("zscore") or []

                tail_n = 6
                tail = {
                    "periods": periods[-tail_n:],
                    "values": values[-tail_n:],
                    "pct_change": pct[-tail_n:] if pct else [],
                    "log_returns": logret[-tail_n:] if logret else [],
                    "zscore": z[-tail_n:] if z else [],
                }
                text_content = _sanitize_english(
                    "\n".join(
                        [
                            "Preciso Mathematics (Derived Time-Series)",
                            f"entity: {entity}",
                            f"metric: {metric}",
                            f"periods_tail: {tail['periods']}",
                            f"values_tail: {tail['values']}",
                            f"pct_change_tail: {tail['pct_change']}",
                            f"log_returns_tail: {tail['log_returns']}",
                            f"zscore_tail: {tail['zscore']}",
                        ]
                    )
                )
                contexts.append(
                    {
                        "chunk_id": f"{case_id}-math-{idx}",
                        "entity": entity,
                        "period": (periods[-1] if periods else None),
                        "source": "preciso_mathematics",
                        "text_content": text_content,
                        "keywords": extract_keywords(text_content),
                        "metadata": {
                            "doc_id": metadata.get("doc_id"),
                            "case_id": case_id,
                            "metric": metric,
                            "series_key": key,
                        },
                    }
                )
    except Exception:
        # Math evidence must never break RAG context generation.
        logger.warning("math evidence generation failed", exc_info=True)

    return contexts


def extract_graph_triples(distill: DistillResult) -> List[Dict[str, Any]]:
    triples: List[Dict[str, Any]] = []
    seen = set()

    for fact in distill.facts:
        if not isinstance(fact, dict):
            continue
        head = _first_present(fact, ["entity", "company", "issuer", "name", "ticker"])
        relation = _first_present(fact, ["relation", "relationship", "metric", "fact", "type"])
        tail = _first_present(
            fact,
            [
                "counterparty",
                "subsidiary",
                "parent",
                "segment",
                "region",
                "product",
                "customer",
                "vendor",
                "related_entity",
            ],
        )
        if tail is None and fact.get("value") is not None:
            tail = str(fact.get("value"))
        if head and relation and tail:
            properties: Dict[str, Any] = {}
            # Prefer normalized period for time alignment.
            if fact.get("period_norm") or fact.get("period"):
                properties["period"] = fact.get("period_norm") or fact.get("period")
            if fact.get("unit"):
                properties["unit"] = fact.get("unit")
            if fact.get("source"):
                properties["source"] = fact.get("source")
            if fact.get("evidence"):
                properties["evidence"] = fact.get("evidence")
            key = (head, relation, tail)
            if key in seen:
                continue
            seen.add(key)
            triples.append(
                {
                    "head_node": head,
                    "relation": relation,
                    "tail_node": tail,
                    "properties": properties or None,
                }
            )

    if distill.cot_markdown:
        pattern = re.compile(
            r"([A-Z][A-Za-z0-9&().\- ]{2,})\s+(acquired|acquires|merged with|subsidiary of|partnered with|owns|owned by)\s+([A-Z][A-Za-z0-9&().\- ]{2,})",
            re.IGNORECASE,
        )
        for match in pattern.finditer(distill.cot_markdown):
            head, relation, tail = match.groups()
            head = head.strip()
            tail = tail.strip()
            relation = relation.strip().lower()
            key = (head, relation, tail)
            if key in seen:
                continue
            seen.add(key)
            triples.append(
                {
                    "head_node": head,
                    "relation": relation,
                    "tail_node": tail,
                    "properties": {"source": "cot"},
                }
            )

    # Preciso Mathematics: emit derived-series triples so Spoke D can carry quantitative evidence.
    try:
        analysis = PrecisoMathematicsService().analyze(distill.facts or [])
        derived = analysis.derived or {}
        for key in sorted(list(derived.keys()))[:30]:
            payload = derived.get(key) or {}
            try:
                entity, metric = key.split("::", 1)
            except ValueError:
                continue
            periods = payload.get("periods") or []
            values = payload.get("values") or []
            pct = payload.get("pct_change") or []
            z = payload.get("zscore") or []
            if not periods or not values:
                continue

            series_node = f"series:{entity}::{metric}"
            latest_period = periods[-1]
            latest_value = values[-1]
            latest_pct = pct[-1] if pct else None
            latest_z = z[-1] if z else None

            candidates = [
                (entity, "has_series", series_node, {"source": "preciso_mathematics", "metric": metric}),
                (series_node, "latest_period", str(latest_period), {"source": "preciso_mathematics"}),
                (series_node, "latest_value", str(latest_value), {"source": "preciso_mathematics"}),
            ]
            if latest_pct is not None:
                candidates.append((series_node, "latest_pct_change", str(latest_pct), {"source": "preciso_mathematics"}))
            if latest_z is not None:
                candidates.append((series_node, "latest_zscore", str(latest_z), {"source": "preciso_mathematics"}))

            for head, rel, tail, props in candidates:
                k = (head, rel, tail)
                if k in seen:
                    continue
                seen.add(k)
                triples.append(
                    {
                        "head_node": head,
                        "relation": rel,
                        "tail_node": tail,
                        "properties": props,
                    }
                )
    except Exception as exc:
        logger.warning("swallowed exception", exc_info=exc)

    # Causal template triples: add domain-specific causal edges with weights.
    try:
        template_edges = _build_causal_template_triples(distill)
        for t in template_edges:
            key = (t.get("head_node"), t.get("relation"), t.get("tail_node"))
            if key in seen:
                continue
            seen.add(key)
            triples.append(t)
    except Exception as exc:
        logger.warning("swallowed exception", exc_info=exc)

    return triples


def _build_causal_template_triples(distill: DistillResult) -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    facts = [f for f in (distill.facts or []) if isinstance(f, dict)]
    if not facts:
        return edges

    def _add(head: str, rel: str, tail: str, *, weight: float, category: str, evidence: Optional[Dict[str, Any]] = None) -> None:
        props: Dict[str, Any] = {"weight": weight, "category": category}
        if evidence:
            props["evidence"] = evidence
        edges.append({"head_node": head, "relation": rel, "tail_node": tail, "properties": props})

    # Macro triggers
    for f in facts:
        metric = str(f.get("metric") or f.get("concept") or "").lower()
        if "fedfunds" in metric or "policy rate" in metric or "interest rate" in metric:
            _add("Fed Rate", "causal_affects", "Discount Rate", weight=0.85, category="macro", evidence=f.get("evidence"))
            _add("Discount Rate", "causal_affects", "DCF Valuation", weight=0.88, category="macro", evidence=f.get("evidence"))
        if "10y" in metric or "treasury" in metric or "yield" in metric:
            _add("10Y Treasury Yield", "causal_affects", "Discount Rate", weight=0.82, category="macro", evidence=f.get("evidence"))
        if "dxy" in metric or "dollar index" in metric:
            _add("DXY Strength", "causal_affects", "FX Loss Risk", weight=0.74, category="macro", evidence=f.get("evidence"))

    # Fundamentals erosion
    for f in facts:
        metric = str(f.get("metric") or f.get("concept") or "").lower()
        if "interest" in metric and ("expense" in metric or "cost" in metric):
            _add("High Interest", "causal_affects", "ICR (Interest Coverage)", weight=0.70, category="fundamentals", evidence=f.get("evidence"))
        if "capex" in metric or "capital expenditure" in metric:
            _add("High Interest", "causal_affects", "Capex", weight=0.68, category="fundamentals", evidence=f.get("evidence"))

    # Supply chain chokehold
    for f in facts:
        rel = str(f.get("metric") or f.get("relation") or "").lower()
        vendor = f.get("vendor") or f.get("customer") or f.get("counterparty") or f.get("related_entity")
        entity = f.get("entity") or f.get("company")
        if entity and vendor and any(k in rel for k in ("vendor", "supplier", "customer", "supply")):
            _add(str(entity), "causal_affects", str(vendor), weight=0.80, category="supply_chain", evidence=f.get("evidence"))

    # Market panic
    for f in facts:
        metric = str(f.get("metric") or f.get("concept") or "").lower()
        if "vix" in metric or "volatility" in metric:
            _add("VIX Spike", "causal_affects", "Market Panic", weight=0.83, category="market", evidence=f.get("evidence"))
        if "margin" in metric and "call" in metric:
            _add("Margin Call", "causal_affects", "Forced Liquidation", weight=0.86, category="market", evidence=f.get("evidence"))

    return edges


def build_training_set(case_id: str, distill: DistillResult, decision: DecisionResult) -> Dict[str, Any]:
    rag_contexts = build_rag_context(distill, case_id)
    graph_triples = extract_graph_triples(distill)
    numeric_series = _extract_numeric_series(distill.facts)
    causal_candidates: List[Dict[str, Any]] = []
    causal_edges: List[Dict[str, Any]] = []
    for entity, metrics in numeric_series.items():
        metric_names = list(metrics.keys())
        for cause_metric in metric_names:
            for effect_metric in metric_names:
                if cause_metric == effect_metric:
                    continue
                cause_series = metrics.get(cause_metric, {})
                effect_series = metrics.get(effect_metric, {})
                common_periods = [p for p in cause_series.keys() if p in effect_series]
                if len(common_periods) < 4:
                    continue
                ordered_periods = _sort_periods(common_periods)
                if len(ordered_periods) < 4:
                    continue
                base_xs = [cause_series[p] for p in ordered_periods]
                base_ys = [effect_series[p] for p in ordered_periods]
                base_corr = _pearson_corr(base_xs, base_ys)
                max_lag = min(3, len(ordered_periods) - 1)
                for lag in range(1, max_lag + 1):
                    xs = []
                    ys = []
                    for idx in range(lag, len(ordered_periods)):
                        xs.append(cause_series[ordered_periods[idx - lag]])
                        ys.append(effect_series[ordered_periods[idx]])
                    if len(xs) < 3:
                        continue
                    corr = _pearson_corr(xs, ys)
                    granger_score = abs(corr) - abs(base_corr)
                    score = abs(corr) + max(0.0, granger_score)
                    confidence = _bootstrap_confidence(xs, ys)
                    candidate = {
                        "entity": entity,
                        "cause_metric": cause_metric,
                        "effect_metric": effect_metric,
                        "lag": lag,
                        "correlation": corr,
                        "granger_score": granger_score,
                        "score": score,
                        "confidence": confidence,
                    }
                    causal_candidates.append(candidate)
                    causal_edges.append(
                        {
                            "source": _node_id("Metric", cause_metric),
                            "relation": "affects",
                            "target": _node_id("Metric", effect_metric),
                            "confidence": confidence,
                            "attributes": {
                                "entity": entity,
                                "lag": lag,
                                "score": score,
                            },
                        }
                    )

    ontology_nodes: Dict[str, Dict[str, Any]] = {}
    ontology_edges: List[Dict[str, Any]] = []

    def add_node(node_type: str, name: str, attributes: Optional[Dict[str, Any]] = None) -> str:
        node_key = _node_id(node_type, name)
        if node_key not in ontology_nodes:
            ontology_nodes[node_key] = {
                "id": node_key,
                "type": node_type,
                "name": name,
                "attributes": attributes or {},
            }
        elif attributes:
            ontology_nodes[node_key]["attributes"].update(attributes)
        return node_key

    def add_edge(source: str, relation: str, target: str, attributes: Optional[Dict[str, Any]] = None, confidence: Optional[float] = None) -> None:
        edge = {
            "source": source,
            "relation": relation,
            "target": target,
            "attributes": attributes or {},
        }
        if confidence is not None:
            edge["confidence"] = confidence
        ontology_edges.append(edge)

    decision_event_id = add_node("Event", f"Decision: {decision.decision}", {"decision": decision.decision})

    for fact in distill.facts:
        if not isinstance(fact, dict):
            continue
        entity = _first_present(fact, ["entity", "company", "issuer", "name", "ticker"])
        metric = _first_present(fact, ["metric", "fact", "type", "name", "label"])
        period = _first_present(fact, ["period", "fiscal_period", "date", "as_of"])
        source = _first_present(fact, ["source"]) or (distill.metadata or {}).get("source")
        if entity:
            entity_id = add_node("Entity", entity)
            if metric:
                metric_id = add_node("Metric", metric)
                add_edge(entity_id, "has_metric", metric_id, {"fact": fact})
                add_edge(metric_id, "affects", decision_event_id, {"derived_from": "decision"})
                if period:
                    period_id = add_node("Period", str(period))
                    add_edge(metric_id, "reported_in", period_id)
                if source:
                    source_id = add_node("Source", str(source))
                    add_edge(metric_id, "reported_in", source_id)
        segment = _first_present(fact, ["segment", "region", "subsidiary", "parent"])
        if entity and segment:
            segment_id = add_node("Entity", segment)
            add_edge(segment_id, "part_of", add_node("Entity", entity))

    for triple in graph_triples:
        head = triple.get("head_node")
        tail = triple.get("tail_node")
        relation = triple.get("relation") or "affects"
        if not head or not tail:
            continue
        head_id = add_node("Entity", str(head))
        tail_id = add_node("Entity", str(tail))
        add_edge(head_id, _normalize_relation(str(relation)), tail_id, triple.get("properties") or {})

    for context in rag_contexts:
        entity = context.get("entity")
        period = context.get("period")
        source = context.get("source")
        if entity:
            entity_id = add_node("Entity", str(entity))
            if period:
                period_id = add_node("Period", str(period))
                add_edge(entity_id, "reported_in", period_id, {"chunk_id": context.get("chunk_id")})
            if source:
                source_id = add_node("Source", str(source))
                add_edge(entity_id, "reported_in", source_id, {"chunk_id": context.get("chunk_id")})

    for edge in causal_edges:
        add_edge(edge["source"], edge["relation"], edge["target"], edge.get("attributes") or {}, edge.get("confidence"))

    evidence_paths: List[Dict[str, Any]] = []
    for fact in distill.facts:
        if not isinstance(fact, dict):
            continue
        entity = _first_present(fact, ["entity", "company", "issuer", "name", "ticker"])
        metric = _first_present(fact, ["metric", "fact", "type", "name", "label"])
        if not entity or not metric:
            continue
        evidence_paths.append(
            {
                "entity": entity,
                "metric": metric,
                "decision": decision.decision,
                "triples": [
                    {"head": entity, "relation": "has_metric", "tail": metric},
                    {"head": metric, "relation": "affects", "tail": decision.decision},
                ],
            }
        )

    metadata = {
        "case_id": case_id,
        "source": distill.metadata.get("source") if distill.metadata else None,
        "doc_id": distill.metadata.get("doc_id") if distill.metadata else None,
    }
    input_features = {
        "facts": distill.facts,
        "metadata": distill.metadata,
        "rag_contexts": rag_contexts,
        "graph_triples": graph_triples,
    }
    reasoning_chain = {
        "cot_markdown": distill.cot_markdown,
        "rationales": _extract_rationales(decision.rationale),
    }
    output_narrative = _sanitize_english(decision.rationale)
    training_prompt = _sanitize_english(
        "Facts:\n"
        f"{distill.facts}\n\n"
        "Reasoning:\n"
        f"{distill.cot_markdown}\n\n"
        "Decision:\n"
        f"{decision.decision}\n"
        "Ontology:\n"
        f"{list(ontology_nodes.values())}\n\n"
        "Causal Candidates:\n"
        f"{causal_candidates}\n"
    )
    return {
        "metadata": metadata,
        "input_features": input_features,
        "ontology": {
            "nodes": list(ontology_nodes.values()),
            "edges": ontology_edges,
            "schema": {
                "node_types": ["Entity", "Metric", "Event", "Period", "Source"],
                "relations": ["has_metric", "affects", "part_of", "reported_in"],
            },
        },
        "predictive_signals": {
            "causal_candidates": sorted(causal_candidates, key=lambda item: item["score"], reverse=True),
            "method": "lag_correlation_granger_style",
            "confidence_method": "bootstrap_correlation",
        },
        "reasoning_chain": reasoning_chain,
        "evidence_paths": evidence_paths,
        "output_narrative": output_narrative,
        "training_prompt": training_prompt,
    }
