from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.types import DistillResult
from app.services.date_utils import to_date_ymd
from app.services.graph_reasoning_local import find_three_hop_paths_from_triples
from app.services.spokes import extract_graph_triples
from app.services.market_data import market_data_service
from app.services.oracle import fed_shock_analyzer

logger = logging.getLogger(__name__)


_SUPPLY_REL_HINTS = (
    "supplier",
    "suppl",
    "vendor",
    "customer",
    "client",
    "distributor",
    "manufacturer",
    "supplies_to",
    "vendor_of",
    "customer_of",
    "supply_chain",
)


def _parse_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    txt = str(value).strip()
    if not txt:
        return None
    neg = "(" in txt and ")" in txt
    txt = txt.replace(",", "").replace("$", "").replace("USD", "").replace("KRW", "").strip()
    txt = txt.replace("(", "").replace(")", "").strip()
    if not txt:
        return None
    try:
        d = Decimal(txt)
    except (InvalidOperation, ValueError):
        return None
    return -d if neg else d


def _infer_as_of(distill: DistillResult) -> Optional[str]:
    meta = distill.metadata or {}
    for k in ("document_date", "as_of", "period_norm", "period", "fiscal_period"):
        d = to_date_ymd(meta.get(k))
        if d:
            return d

    # Try from facts: prefer period_norm, then period.
    dates: List[str] = []
    for f in distill.facts or []:
        if not isinstance(f, dict):
            continue
        d = to_date_ymd(f.get("period_norm")) or to_date_ymd(f.get("period")) or to_date_ymd(f.get("date"))
        if d:
            dates.append(d)
    if dates:
        # latest as-of
        return sorted(dates)[-1]
    return None


def _looks_supply_relation(relation: str) -> bool:
    r = (relation or "").lower()
    return any(h in r for h in _SUPPLY_REL_HINTS)


def _pick_entity(distill: DistillResult, entity_hint: Optional[str]) -> str:
    meta = distill.metadata or {}
    entity = (
        entity_hint
        or meta.get("company")
        or meta.get("entity")
        or meta.get("ticker")
        or meta.get("title")
        or "Unknown"
    )
    return str(entity)


def _fact_refs(distill: DistillResult, *, limit: int = 60) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    for f in distill.facts or []:
        if not isinstance(f, dict):
            continue
        entity = f.get("entity") or f.get("company") or f.get("ticker") or f.get("issuer")
        metric = f.get("metric") or f.get("concept") or f.get("label")
        period_norm = f.get("period_norm") or f.get("period")
        if entity and metric and period_norm and f.get("value") is not None:
            refs.append({"entity": str(entity), "metric": str(metric), "period_norm": str(period_norm)})
        if len(refs) >= limit:
            break
    return refs


@dataclass
class CausalStoryStep:
    step_type: str  # "fact"|"inference"|"hypothesis"
    category: str  # macro|fundamentals|supply_chain|market|event
    claim: str
    confidence: float = 0.6
    evidence_chunk_ids: List[str] = field(default_factory=list)
    fact_refs: List[Dict[str, Any]] = field(default_factory=list)
    as_of: Optional[str] = None
    debug: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CausalEdge:
    source: str
    predicate: str
    target: str
    weight: float
    category: str
    evidence_chunk_ids: List[str] = field(default_factory=list)
    fact_refs: List[Dict[str, Any]] = field(default_factory=list)
    as_of: Optional[str] = None
    debug: Dict[str, Any] = field(default_factory=dict)


class CausalStoryService:
    """
    Build an evidence-grounded causal chain across multi-domain inputs:
    macro -> fundamentals -> supply-chain -> market, with date alignment.

    This intentionally avoids "free facts":
    - External signals are labeled as hypothesis unless directly evidenced in Spoke B/C.
    - All steps try to attach Spoke C chunk IDs and fact refs.
    """

    def __init__(self, db: Any):
        self.db = db

    async def build_story(
        self,
        *,
        distill: DistillResult,
        entity_hint: Optional[str] = None,
        as_of: Optional[str] = None,
        horizon_days: int = 30,
        max_graph_triples: int = 1200,
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        entity = _pick_entity(distill, entity_hint)
        as_of = to_date_ymd(as_of) or _infer_as_of(distill)
        if not as_of:
            return {
                "status": "needs_review",
                "reason": "missing_as_of_date",
                "entity": entity,
                "steps": [],
            }

        steps: List[CausalStoryStep] = []
        fact_refs = _fact_refs(distill)

        # 1) Macro (Fed funds / rates) as-of date
        macro = await self._macro_step(as_of=as_of)
        if macro:
            macro.fact_refs = fact_refs[:20]
            macro.as_of = as_of
            macro.evidence_chunk_ids = self._find_evidence_chunks(entity=entity, as_of=as_of, keywords=["FEDFUNDS", "rate", "interest", "yield", "treasury"])
            steps.append(macro)

        # 2) Fundamentals impact (scenario) - deterministic text using FedShockAnalyzer if we have usable inputs
        fundamentals = await self._fundamentals_step(distill=distill, entity=entity, as_of=as_of)
        if fundamentals:
            fundamentals.fact_refs = fact_refs[:40]
            fundamentals.evidence_chunk_ids = self._find_evidence_chunks(entity=entity, as_of=as_of, keywords=["debt", "interest", "net income", "discount", "cash flow", "liability", "rate"])
            steps.append(fundamentals)

        # 3) Supply chain propagation (3-hop) from Spoke D triples
        supply = await self._supply_chain_step(distill=distill, entity=entity, limit=max_graph_triples)
        if supply:
            supply.as_of = as_of
            supply.fact_refs = fact_refs[:50]
            supply.evidence_chunk_ids = self._find_evidence_chunks(entity=entity, as_of=as_of, keywords=["supplier", "vendor", "customer", "supply", "default", "liquidity"])
            steps.append(supply)

        # 4) Market effect: if market facts exist, keep as fact; else hypothesis
        market = self._market_step(distill=distill, entity=entity, as_of=as_of)
        if market:
            market.fact_refs = fact_refs[:60]
            market.evidence_chunk_ids = self._find_evidence_chunks(entity=entity, as_of=as_of, keywords=["price", "close", "volume", "volatility", "drawdown", "spread"])
            steps.append(market)

        # 5) What happened that day: event timeline (if present)
        events = self._events_for_date(entity=entity, as_of=as_of)
        if events:
            steps.append(
                CausalStoryStep(
                    step_type="fact",
                    category="event",
                    claim=f"As-of {as_of}, relevant events were observed (count={len(events)}).",
                    confidence=0.7,
                    evidence_chunk_ids=[e.get("chunk_id") for e in events if e.get("chunk_id")][:10],
                    as_of=as_of,
                    debug={"events_preview": events[:5]},
                )
            )

        # 6) Next-step scenario (explicitly hypothesis, returned separately)
        forecast = None
        if steps:
            hyp = self._next_step_hypothesis(steps=steps, as_of=as_of, horizon_days=horizon_days)
            if hyp:
                forecast = hyp.__dict__

        cause_effect = self._build_cause_effect(steps=steps, entity=entity, as_of=as_of)

        result = {
            "status": "ok",
            "entity": entity,
            "as_of": as_of,
            "horizon_days": horizon_days,
            "steps": [s.__dict__ for s in steps],
            "cause_effect": [e.__dict__ for e in cause_effect],
            "forecast": forecast,
        }

        if document_id:
            try:
                os.makedirs("artifacts", exist_ok=True)
                path = os.path.join("artifacts", f"causal_story_{document_id}.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "entity": entity,
                            "as_of": as_of,
                            "cause_effect": result.get("cause_effect"),
                            "forecast": result.get("forecast"),
                        },
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
                result["forecast_file"] = path
            except Exception as exc:
                result.setdefault("warnings", []).append(f"failed_to_write_causal_file: {exc}")

        return result

    def _build_cause_effect(self, *, steps: List[CausalStoryStep], entity: str, as_of: str) -> List[CausalEdge]:
        edges: List[CausalEdge] = []
        cat_map = {s.category: s for s in steps}

        def _edge(source: str, predicate: str, target: str, weight: float, category: str, ref_key: Optional[str] = None) -> CausalEdge:
            step = cat_map.get(ref_key or category)
            return CausalEdge(
                source=source,
                predicate=predicate,
                target=target,
                weight=weight,
                category=category,
                evidence_chunk_ids=(step.evidence_chunk_ids if step else []),
                fact_refs=(step.fact_refs if step else []),
                as_of=as_of,
                debug={"step_type": step.step_type if step else None},
            )

        # Template edges based on requested macro->fundamentals->supply->market chain.
        edges.append(_edge("Fed Rate", "negative_impacts", "Growth Stock Valuation", 0.85, "macro"))
        edges.append(_edge("10Y Treasury Yield", "raises", "Discount Rate", 0.82, "macro"))
        edges.append(_edge("Discount Rate", "decreases", "DCF Valuation", 0.88, "macro"))
        edges.append(_edge("DXY Strength", "increases", "FX Loss Risk", 0.74, "macro"))
        edges.append(_edge("High Interest", "decreases", "ICR (Interest Coverage)", 0.70, "fundamentals"))
        edges.append(_edge("High Interest", "reduces", "Capex", 0.68, "fundamentals"))
        edges.append(_edge("Liquidity Shift", "drains", "Equity Market Liquidity", 0.66, "fundamentals"))
        edges.append(_edge("Big Tech (Tier 1)", "cancels_order", "Supplier (Tier 2)", 0.92, "supply_chain"))
        edges.append(_edge("Supplier (Tier 2)", "reduces", "Working Capital", 0.84, "supply_chain"))
        edges.append(_edge("Credit Spread Widening", "increases", "Default Risk", 0.80, "supply_chain"))
        edges.append(_edge("Tier 2 Default", "triggers", "Sector-wide Sell-off", 0.95, "market"))
        edges.append(_edge("Margin Call", "forces", "Liquidation", 0.86, "market"))
        edges.append(_edge("VIX Spike", "amplifies", "Market Panic", 0.83, "market"))

        # Connect to observed entity when we have explicit steps.
        if "macro" in cat_map and "fundamentals" in cat_map:
            edges.append(_edge("Policy Tightening", "raises_discount_rate", f"{entity} Valuation", 0.75, "macro"))
        if "fundamentals" in cat_map and "supply_chain" in cat_map:
            edges.append(_edge(f"{entity} Capex Reduction", "reduces_orders", "Supplier Revenue", 0.80, "supply_chain"))
        if "supply_chain" in cat_map and "market" in cat_map:
            edges.append(_edge("Supply Chain Stress", "increases", "Market Volatility", 0.78, "market"))

        return edges

    async def _macro_step(self, *, as_of: str) -> Optional[CausalStoryStep]:
        try:
            end = as_of
            obs = await market_data_service.fetch_fred_series("FEDFUNDS", limit=2, observation_end=end, db=self.db)
            if not obs:
                return CausalStoryStep(
                    step_type="hypothesis",
                    category="macro",
                    claim="Macro context (Fed Funds rate) was not available from FRED; if rates increased, downstream impacts should be evaluated.",
                    confidence=0.35,
                    debug={"reason": "missing_fred"},
                    as_of=as_of,
                )
            latest = _parse_decimal(obs[0].get("value"))
            prev = _parse_decimal(obs[1].get("value")) if len(obs) > 1 else None
            latest_date = to_date_ymd(obs[0].get("date"))
            delta_bps = None
            if latest is not None and prev is not None:
                delta_bps = int((latest - prev) * Decimal("100"))
            if latest is None:
                raise ValueError("FEDFUNDS latest value not numeric")

            if delta_bps is not None and abs(delta_bps) >= 10:
                direction = "increased" if delta_bps > 0 else "decreased"
                return CausalStoryStep(
                    step_type="fact",
                    category="macro",
                    claim=f"Fed Funds rate {direction} by ~{abs(delta_bps)} bps (as-of {latest_date or as_of}).",
                    confidence=0.85,
                    debug={"series": "FEDFUNDS", "latest": str(latest), "prev": str(prev), "delta_bps": delta_bps, "as_of_obs": latest_date},
                    as_of=as_of,
                )

            return CausalStoryStep(
                step_type="fact",
                category="macro",
                claim=f"Fed Funds rate was {str(latest)}% (as-of {latest_date or as_of}).",
                confidence=0.75,
                debug={"series": "FEDFUNDS", "latest": str(latest), "as_of_obs": latest_date},
                as_of=as_of,
            )
        except Exception as exc:
            return CausalStoryStep(
                step_type="hypothesis",
                category="macro",
                claim="Macro policy rate context could not be fetched; treat macro step as unknown and rely on ingested macro facts.",
                confidence=0.25,
                debug={"error": str(exc)},
                as_of=as_of,
            )

    async def _fundamentals_step(self, *, distill: DistillResult, entity: str, as_of: str) -> Optional[CausalStoryStep]:
        # Use Oracle/FedShockAnalyzer text if we can find a usable net income value.
        industry = (distill.metadata or {}).get("industry") or "General Corporate"
        net_income = None
        debt = None
        debt_ratio = None

        for f in distill.facts or []:
            if not isinstance(f, dict):
                continue
            metric = str(f.get("metric") or f.get("concept") or "").lower()
            if net_income is None and ("netincome" in metric or "net income" in metric):
                net_income = _parse_decimal(f.get("value"))
            if debt is None and ("debt" in metric or "liabil" in metric):
                debt = _parse_decimal(f.get("value"))
            if debt_ratio is None and ("debt_ratio" in metric or "debt ratio" in metric):
                debt_ratio = _parse_decimal(f.get("value"))

        conf = 0.55
        if debt_ratio is not None:
            conf = min(0.85, conf + float(min(Decimal("0.25"), debt_ratio)))

        if net_income and net_income > 0:
            try:
                impact = await fed_shock_analyzer.calculate_shock_impact(str(industry), net_income, shock_bps=100)
                text = fed_shock_analyzer.get_scenario_text(impact, "Net Income")
                return CausalStoryStep(
                    step_type="inference",
                    category="fundamentals",
                    claim=text,
                    confidence=min(0.9, conf + 0.15),
                    debug={"industry": industry, "net_income": str(net_income), "impact": impact},
                    as_of=as_of,
                )
            except Exception as exc:
                logger.warning("swallowed exception", exc_info=exc)

        # Conservative qualitative step (explicitly inference) so the chain is still useful without those fields.
        return CausalStoryStep(
            step_type="inference",
            category="fundamentals",
            claim=(
                "Higher policy rates typically increase discount rates and interest expense for leveraged firms, "
                "which can pressure margins/FCF and compress valuation multiples. "
                "This step is an inference and must be validated against extracted debt/interest metrics."
            ),
            confidence=conf,
            debug={"industry": industry, "net_income_found": bool(net_income), "debt_found": bool(debt), "debt_ratio_found": bool(debt_ratio)},
            as_of=as_of,
        )

    async def _supply_chain_step(self, *, distill: DistillResult, entity: str, limit: int) -> Optional[CausalStoryStep]:
        # Build a local subgraph around the entity to keep DB reads bounded.
        triples: List[Dict[str, Any]] = []
        try:
            triples.extend(extract_graph_triples(distill))
        except Exception as exc:
            logger.warning("swallowed exception", exc_info=exc)

        try:
            triples.extend(self._collect_local_triples(start=entity, max_hops=3, per_node=180, total_limit=limit))
        except Exception as exc:
            logger.warning("swallowed exception", exc_info=exc)

        if not triples:
            return CausalStoryStep(
                step_type="hypothesis",
                category="supply_chain",
                claim=(
                    "Supply-chain edges were not found in Spoke D graph. "
                    "To enable 3-hop contagion, ingest partner 'alt/supply_chain' facts or add vendor/customer fields in facts."
                ),
                confidence=0.25,
                debug={"triples": 0},
            )

        paths = find_three_hop_paths_from_triples(start_node=str(entity), triples=triples, max_hops=3, limit=30)
        supply_paths = []
        for p in paths:
            steps = p.get("steps") or []
            if any(_looks_supply_relation(str(s.get("relation") or "")) for s in steps):
                supply_paths.append(p)

        chosen = supply_paths[0] if supply_paths else (paths[0] if paths else None)
        if not chosen:
            return None

        chain = " -> ".join([str(s.get("to")) for s in (chosen.get("steps") or []) if s.get("to")])
        rels = [str(s.get("relation") or "") for s in (chosen.get("steps") or [])]
        conf = 0.7 if supply_paths else 0.55
        return CausalStoryStep(
            step_type="inference",
            category="supply_chain",
            claim=(
                f"3-hop graph path found: {entity} -> {chain}. "
                "If upstream financial stress increases, downstream counterparties may face liquidity/default risk depending on exposure and concentration."
            ),
            confidence=conf,
            debug={"path": chosen, "relations": rels, "supply_chain_detected": bool(supply_paths)},
        )

    def _market_step(self, *, distill: DistillResult, entity: str, as_of: str) -> Optional[CausalStoryStep]:
        # Look for explicit market facts (price/vol/volume) in the document payload.
        price = None
        vol = None
        volume = None
        for f in distill.facts or []:
            if not isinstance(f, dict):
                continue
            metric = str(f.get("metric") or f.get("concept") or "").lower()
            if price is None and any(k in metric for k in ("close", "price", "ohlc")):
                price = f.get("value")
            if vol is None and "volatil" in metric:
                vol = f.get("value")
            if volume is None and "volume" in metric:
                volume = f.get("value")

        if price is not None or vol is not None or volume is not None:
            parts = []
            if price is not None:
                parts.append(f"price={price}")
            if vol is not None:
                parts.append(f"volatility={vol}")
            if volume is not None:
                parts.append(f"volume={volume}")
            return CausalStoryStep(
                step_type="fact",
                category="market",
                claim=f"Market signals observed ({', '.join(parts)}) as-of {as_of}.",
                confidence=0.75,
                as_of=as_of,
                debug={"price": price, "volatility": vol, "volume": volume},
            )

        return CausalStoryStep(
            step_type="hypothesis",
            category="market",
            claim=(
                "No explicit market price/volume facts were present in the ingested payload. "
                "If macro stress propagates, price drawdowns and volatility spikes are plausible; ingest market OHLC/volume to confirm."
            ),
            confidence=0.35,
            as_of=as_of,
            debug={"missing_market_facts": True},
        )

    def _events_for_date(self, *, entity: str, as_of: str) -> List[Dict[str, Any]]:
        # Best-effort: use Spoke C contexts which already contain event/market/fundamental snippets.
        out: List[Dict[str, Any]] = []
        try:
            rows = self.db.search_rag_context(keyword=as_of, limit=40) or []
            for r in rows:
                text = str(r.get("text_content") or "").lower()
                if "event:" in text or "headline" in text or "gdelt" in text or "rss" in text:
                    out.append({"chunk_id": r.get("chunk_id"), "source": r.get("source"), "preview": (r.get("text_content") or "")[:180]})
        except Exception:
            return []
        return out[:20]

    def _next_step_hypothesis(self, *, steps: List[CausalStoryStep], as_of: str, horizon_days: int) -> Optional[CausalStoryStep]:
        cats = [s.category for s in steps]
        if "macro" in cats and ("fundamentals" in cats or "supply_chain" in cats):
            horizon_end = (datetime.strptime(as_of, "%Y-%m-%d") + timedelta(days=max(1, horizon_days))).strftime("%Y-%m-%d")
            return CausalStoryStep(
                step_type="hypothesis",
                category="hypothesis",
                claim=(
                    f"Hypothesis ({as_of} -> {horizon_end}): If tighter policy persists, monitor for margin/FCF deterioration, "
                    "credit spread widening in exposed suppliers, and elevated price volatility. "
                    "This is a forecast scenario, not a confirmed fact."
                ),
                confidence=0.45,
                as_of=as_of,
                debug={"horizon_days": horizon_days},
            )
        return None

    def _find_evidence_chunks(self, *, entity: str, as_of: str, keywords: List[str]) -> List[str]:
        # Keep this conservative: it is fine to return fewer chunks rather than wrong evidence.
        ids: List[str] = []
        try:
            # Prefer period-normalized contexts when present.
            rows = []
            try:
                rows = self.db.search_rag_context(entity=entity, period=as_of, limit=20) or []
            except Exception:
                rows = []
            for kw in keywords[:6]:
                try:
                    rows.extend(self.db.search_rag_context(keyword=kw, limit=10) or [])
                except Exception:
                    continue
            seen: Set[str] = set()
            for r in rows:
                cid = r.get("chunk_id")
                if not cid or cid in seen:
                    continue
                seen.add(cid)
                ids.append(str(cid))
                if len(ids) >= 12:
                    break
        except Exception:
            return []
        return ids

    def _collect_local_triples(self, *, start: str, max_hops: int, per_node: int, total_limit: int) -> List[Dict[str, Any]]:
        triples: List[Dict[str, Any]] = []
        frontier = {start}
        seen_nodes: Set[str] = set()
        for _ in range(max_hops):
            next_frontier: Set[str] = set()
            for node in list(frontier):
                if node in seen_nodes:
                    continue
                seen_nodes.add(node)
                try:
                    local = self.db.search_graph_triples(head=str(node), limit=per_node) or []
                except Exception:
                    local = []
                for t in local:
                    triples.append(t)
                    tail = t.get("tail_node")
                    if tail:
                        next_frontier.add(str(tail))
                if len(triples) >= total_limit:
                    return triples[:total_limit]
            frontier = next_frontier
            if not frontier:
                break
        return triples[:total_limit]
