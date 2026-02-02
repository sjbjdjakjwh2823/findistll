from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple


class OracleEngine:
    """
    Pillar 2 + 3 baseline engine.
    - Pillar 2: lightweight causal scaffold (PC/NOTEARS-inspired filtering + acyclic propagation)
    - Pillar 3: temporal-aware forward impact projection
    """

    CAUSAL_REASONING_MATRIX: Dict[Tuple[str, str], Dict[str, Any]] = {
        ("inflation", "policy_rate"): {"multiplier": 1.35, "polarity": 1.0, "path_label": "macro_policy"},
        ("policy_rate", "bond_yield"): {"multiplier": 1.30, "polarity": 1.0, "path_label": "rates_curve"},
        ("policy_rate", "discount_rate"): {"multiplier": 1.28, "polarity": 1.0, "path_label": "valuation_kernel"},
        ("discount_rate", "tech_valuation"): {"multiplier": 1.45, "polarity": -1.0, "path_label": "duration_risk"},
        ("bond_yield", "tech_valuation"): {"multiplier": 1.30, "polarity": -1.0, "path_label": "relative_multiple"},
        ("liquidity", "tech_valuation"): {"multiplier": 1.20, "polarity": 1.0, "path_label": "risk_on"},
        ("energy_price", "inflation"): {"multiplier": 1.22, "polarity": 1.0, "path_label": "cost_push"},
        ("unemployment", "policy_rate"): {"multiplier": 1.15, "polarity": -1.0, "path_label": "labor_slack"},
        ("usd_strength", "exports"): {"multiplier": 1.18, "polarity": -1.0, "path_label": "fx_translation"},
        ("revenue_growth", "earnings_growth"): {"multiplier": 1.20, "polarity": 1.0, "path_label": "fundamental"},
        ("earnings_growth", "equity_valuation"): {"multiplier": 1.24, "polarity": 1.0, "path_label": "multiple_expansion"},
        ("risk_premium", "equity_valuation"): {"multiplier": 1.35, "polarity": -1.0, "path_label": "risk_discount"},
        ("credit_spread", "equity_valuation"): {"multiplier": 1.23, "polarity": -1.0, "path_label": "financing_stress"},
    }

    CONCEPT_ALIASES: Dict[str, Tuple[str, ...]] = {
        "inflation": ("inflation", "cpi", "ppi", "price level", "price pressure"),
        "policy_rate": ("policy rate", "fed funds", "interest rate", "fed policy", "rate hike", "rate cut"),
        "bond_yield": ("bond yield", "treasury yield", "10y yield", "real yield"),
        "discount_rate": ("discount rate", "cost of capital", "wacc"),
        "tech_valuation": ("tech valuation", "growth multiple", "tech multiple", "software multiple", "nasdaq"),
        "equity_valuation": ("equity valuation", "market valuation", "price target", "valuation"),
        "liquidity": ("liquidity", "money supply", "qe", "quantitative easing"),
        "energy_price": ("energy price", "oil", "gas price", "brent", "wti"),
        "unemployment": ("unemployment", "jobless", "labor market slack"),
        "usd_strength": ("usd", "dollar index", "dxy", "strong dollar"),
        "exports": ("exports", "export demand", "trade balance"),
        "revenue_growth": ("revenue growth", "sales growth", "topline"),
        "earnings_growth": ("earnings growth", "eps growth", "profit growth"),
        "risk_premium": ("risk premium", "equity risk premium", "term premium"),
        "credit_spread": ("credit spread", "high yield spread", "corporate spread"),
    }

    def build_causal_skeleton(self, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for edge in edges:
            head = self._as_str(edge.get("head_node"))
            relation = self._as_str(edge.get("relation"))
            tail = self._as_str(edge.get("tail_node"))
            if not head or not relation or not tail:
                continue

            key = (head, relation, tail)
            scored = self._score_edge(edge)
            strength = scored["strength"]
            existing = grouped.get(key)
            if existing is None:
                grouped[key] = {
                    "head_node": head,
                    "relation": relation,
                    "tail_node": tail,
                    "strength": strength,
                    "polarity": scored["polarity"],
                    "support_count": 1,
                    "time_granularity": edge.get("time_granularity") or "day",
                    "reasoning_tags": scored["reasoning_tags"],
                    "matrix_boost": scored["matrix_boost"],
                }
            else:
                old_count = int(existing["support_count"])
                existing["strength"] = max(float(existing["strength"]), strength)
                existing["support_count"] = old_count + 1
                existing["polarity"] = self._clamp(
                    ((float(existing.get("polarity", 1.0)) * old_count) + scored["polarity"]) / (old_count + 1),
                    -1.0,
                    1.0,
                )
                existing["matrix_boost"] = max(float(existing.get("matrix_boost", 1.0)), scored["matrix_boost"])
                existing["reasoning_tags"] = sorted(
                    set(existing.get("reasoning_tags", [])) | set(scored["reasoning_tags"])
                )

        return self._enforce_acyclic(list(grouped.values()))

    def simulate_what_if(
        self,
        node_id: str,
        value_delta: float,
        causal_graph: List[Dict[str, Any]],
        horizon_steps: int = 3,
    ) -> Dict[str, Any]:
        """
        Counterfactual interface:
        Apply delta at node_id and propagate through directed graph with temporal decay.
        """
        start = self._as_str(node_id)
        if not start:
            return {"node_id": node_id, "value_delta": value_delta, "impacts": [], "horizon_steps": horizon_steps}

        adjacency: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for link in causal_graph:
            head = self._as_str(link.get("head_node"))
            tail = self._as_str(link.get("tail_node"))
            if head and tail:
                adjacency[head].append(link)

        impacts: Dict[str, float] = defaultdict(float)
        visited_depth: Dict[str, int] = {}
        queue = deque([(start, float(value_delta), 0)])

        while queue:
            current_node, current_delta, depth = queue.popleft()
            impacts[current_node] += current_delta

            if depth >= horizon_steps:
                continue

            next_depth = depth + 1
            for link in adjacency.get(current_node, []):
                downstream = self._as_str(link.get("tail_node"))
                if not downstream:
                    continue

                strength = float(link.get("strength", 0.3))
                decay = self._temporal_decay(link.get("time_granularity"))
                polarity = self._link_polarity(link)
                propagated = current_delta * strength * decay * polarity
                if abs(propagated) < 1e-9:
                    continue

                best_known_depth = visited_depth.get(downstream)
                if best_known_depth is None or next_depth <= best_known_depth:
                    visited_depth[downstream] = next_depth
                    queue.append((downstream, propagated, next_depth))

        ranked = sorted(impacts.items(), key=lambda item: abs(item[1]), reverse=True)
        impact_rows = [{"node_id": node, "delta": delta} for node, delta in ranked]

        return {
            "node_id": start,
            "value_delta": float(value_delta),
            "horizon_steps": horizon_steps,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "impacts": impact_rows,
        }

    def forecast_from_edges(self, edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Simple temporal projection baseline using edge validity windows.
        Returns an aggregate outlook that downstream API/UI can render.
        """
        causal_graph = self.build_causal_skeleton(edges)
        top_links = sorted(causal_graph, key=lambda x: float(x.get("strength", 0.0)), reverse=True)[:10]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "link_count": len(causal_graph),
            "top_links": top_links,
        }

    def get_root_cause_path(
        self,
        target_node: str,
        causal_graph: List[Dict[str, Any]],
        max_depth: int = 6,
    ) -> Dict[str, Any]:
        target = self._as_str(target_node)
        if not target:
            return {
                "target_node": target_node,
                "root_cause": "",
                "path": [],
                "edge_path": [],
                "influence_score": 0.0,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        incoming: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for link in causal_graph:
            head = self._as_str(link.get("head_node"))
            tail = self._as_str(link.get("tail_node"))
            if head and tail:
                incoming[tail].append(link)

        for node in incoming:
            incoming[node] = sorted(
                incoming[node],
                key=lambda row: abs(float(row.get("strength", 0.0))),
                reverse=True,
            )

        def walk_back(node: str, depth: int, seen: Set[str]) -> List[Dict[str, Any]]:
            if depth >= max_depth or node not in incoming:
                return [{"path": [node], "edges": [], "abs_score": 1.0, "signed_score": 1.0}]

            paths: List[Dict[str, Any]] = []
            for link in incoming.get(node, []):
                parent = self._as_str(link.get("head_node"))
                if not parent or parent in seen:
                    continue

                factor_signed = float(link.get("strength", 0.3)) * self._temporal_decay(link.get("time_granularity"))
                factor_signed *= self._link_polarity(link)
                factor_abs = abs(factor_signed)
                if factor_abs < 1e-12:
                    continue

                parent_paths = walk_back(parent, depth + 1, seen | {parent})
                edge_row = {
                    "head_node": parent,
                    "relation": self._as_str(link.get("relation")),
                    "tail_node": node,
                    "strength": float(link.get("strength", 0.3)),
                    "polarity": self._link_polarity(link),
                    "time_granularity": link.get("time_granularity") or "day",
                }
                for prev in parent_paths:
                    paths.append(
                        {
                            "path": prev["path"] + [node],
                            "edges": prev["edges"] + [edge_row],
                            "abs_score": prev["abs_score"] * factor_abs,
                            "signed_score": prev["signed_score"] * factor_signed,
                        }
                    )

            if not paths:
                return [{"path": [node], "edges": [], "abs_score": 1.0, "signed_score": 1.0}]
            return paths

        candidates = walk_back(target, depth=0, seen={target})
        best = max(candidates, key=lambda row: row["abs_score"])
        top_paths = sorted(candidates, key=lambda row: row["abs_score"], reverse=True)[:3]

        return {
            "target_node": target,
            "root_cause": best["path"][0] if best["path"] else target,
            "path": best["path"],
            "edge_path": best["edges"],
            "influence_score": best["abs_score"],
            "directional_effect": best["signed_score"],
            "top_paths": [
                {
                    "path": row["path"],
                    "influence_score": row["abs_score"],
                    "directional_effect": row["signed_score"],
                }
                for row in top_paths
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _enforce_acyclic(self, links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        NOTEARS-inspired practical constraint:
        greedily keep high-strength links while rejecting links that create a cycle.
        """
        sorted_links = sorted(links, key=lambda x: float(x.get("strength", 0.0)), reverse=True)
        kept: List[Dict[str, Any]] = []
        graph: Dict[str, Set[str]] = defaultdict(set)

        for link in sorted_links:
            head = self._as_str(link.get("head_node"))
            tail = self._as_str(link.get("tail_node"))
            if not head or not tail:
                continue
            if head == tail:
                continue
            if self._has_path(graph, tail, head):
                continue
            graph[head].add(tail)
            kept.append(link)
        return kept

    def _has_path(self, graph: Dict[str, Set[str]], src: str, dst: str) -> bool:
        if src == dst:
            return True
        stack = [src]
        seen: Set[str] = set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            for nxt in graph.get(node, set()):
                if nxt == dst:
                    return True
                stack.append(nxt)
        return False

    def _edge_strength(self, edge: Dict[str, Any]) -> float:
        return self._score_edge(edge)["strength"]

    def _score_edge(self, edge: Dict[str, Any]) -> Dict[str, Any]:
        base = self._base_edge_strength(edge)
        relation = self._as_str(edge.get("relation")).lower()
        head = self._as_str(edge.get("head_node"))
        tail = self._as_str(edge.get("tail_node"))

        relation_boost = self._relation_strength_modifier(relation)
        matrix_boost, matrix_polarity, matrix_tag = self._matrix_modifier(head, tail)
        strength = self._clamp(base * relation_boost * matrix_boost, 0.05, 0.98)

        relation_polarity = self._relation_polarity(relation)
        polarity = self._clamp(matrix_polarity * relation_polarity, -1.0, 1.0)

        tags: List[str] = ["base_signal"]
        if relation_boost > 1.0:
            tags.append("relation_weighted")
        if matrix_tag:
            tags.append(matrix_tag)

        return {
            "strength": strength,
            "polarity": polarity,
            "matrix_boost": matrix_boost,
            "reasoning_tags": tags,
        }

    def _base_edge_strength(self, edge: Dict[str, Any]) -> float:
        base = 0.35
        confidence = self._as_str((edge.get("properties") or {}).get("confidence")).lower()
        if confidence == "high":
            base += 0.25
        elif confidence == "medium":
            base += 0.15
        elif confidence == "low":
            base += 0.05

        reflection_quality = (edge.get("properties") or {}).get("reflection_quality")
        if isinstance(reflection_quality, (int, float)):
            base += max(min(float(reflection_quality), 1.0), 0.0) * 0.2

        temporal_quality = (edge.get("properties") or {}).get("temporal_quality")
        if isinstance(temporal_quality, (int, float)):
            base += max(min(float(temporal_quality), 1.0), 0.0) * 0.2

        return max(0.05, min(base, 0.98))

    def _relation_strength_modifier(self, relation: str) -> float:
        if not relation:
            return 1.0
        causal_terms = ("drives", "causes", "raises", "tightens", "expands", "accelerates", "improves")
        weak_terms = ("correlates", "relates", "tracks", "mentions")
        if any(term in relation for term in causal_terms):
            return 1.12
        if any(term in relation for term in weak_terms):
            return 0.9
        return 1.0

    def _relation_polarity(self, relation: str) -> float:
        if not relation:
            return 1.0
        inverse_terms = ("reduces", "suppresses", "compresses", "decreases", "inverse", "offsets", "hurts")
        if any(term in relation for term in inverse_terms):
            return -1.0
        return 1.0

    def _matrix_modifier(self, head_node: str, tail_node: str) -> Tuple[float, float, str]:
        head_concepts = self._match_concepts(head_node)
        tail_concepts = self._match_concepts(tail_node)
        if not head_concepts or not tail_concepts:
            return 1.0, 1.0, ""

        best_multiplier = 1.0
        best_polarity = 1.0
        best_tag = ""
        for head in head_concepts:
            for tail in tail_concepts:
                spec = self.CAUSAL_REASONING_MATRIX.get((head, tail))
                if not spec:
                    continue
                multiplier = float(spec.get("multiplier", 1.0))
                if multiplier > best_multiplier:
                    best_multiplier = multiplier
                    best_polarity = float(spec.get("polarity", 1.0))
                    best_tag = self._as_str(spec.get("path_label"))
        return best_multiplier, best_polarity, best_tag

    def _match_concepts(self, node: str) -> Set[str]:
        normalized = self._normalize_text(node)
        concepts: Set[str] = set()
        if not normalized:
            return concepts
        for concept, aliases in self.CONCEPT_ALIASES.items():
            if concept in normalized:
                concepts.add(concept)
                continue
            for alias in aliases:
                if alias in normalized:
                    concepts.add(concept)
                    break
        return concepts

    def _normalize_text(self, value: str) -> str:
        text = self._as_str(value).lower()
        for ch in ("-", "_", "/", ",", ".", "(", ")", ":"):
            text = text.replace(ch, " ")
        return " ".join(text.split())

    def _link_polarity(self, link: Dict[str, Any]) -> float:
        raw_polarity = link.get("polarity")
        if isinstance(raw_polarity, (int, float)):
            return self._clamp(float(raw_polarity), -1.0, 1.0)
        relation = self._as_str(link.get("relation")).lower()
        return self._relation_polarity(relation)

    def _temporal_decay(self, granularity: Optional[str]) -> float:
        if granularity == "year":
            return 0.9
        if granularity == "quarter":
            return 0.85
        if granularity == "month":
            return 0.78
        return 0.7

    def _as_str(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(value, high))
