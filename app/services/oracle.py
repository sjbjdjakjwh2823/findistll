from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class BusinessObject:
    object_id: str
    object_type: str
    label: str
    canonical_name: str
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_type": self.object_type,
            "label": self.label,
            "canonical_name": self.canonical_name,
            "attributes": self.attributes,
        }


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
        ("policy_rate", "tech_valuation"): {"multiplier": 1.32, "polarity": -1.0, "path_label": "rates_duration"},
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
    SCM_EQUATIONS: Dict[Tuple[str, str], Dict[str, Any]] = {
        ("energy_price", "inflation"): {
            "equation": "inflation_t = a0 + 0.55 * energy_price_t + eps_t",
            "direct_effect": 1.12,
            "noise_sigma": 0.18,
            "domain": "macro",
        },
        ("inflation", "policy_rate"): {
            "equation": "policy_rate_t = b0 + 0.62 * inflation_t + eps_t",
            "direct_effect": 1.18,
            "noise_sigma": 0.16,
            "domain": "macro_policy",
        },
        ("policy_rate", "bond_yield"): {
            "equation": "bond_yield_t = c0 + 0.70 * policy_rate_t + eps_t",
            "direct_effect": 1.1,
            "noise_sigma": 0.14,
            "domain": "rates_curve",
        },
        ("policy_rate", "tech_valuation"): {
            "equation": "tech_valuation_t = d0 - 0.48 * policy_rate_t + eps_t",
            "direct_effect": 1.22,
            "noise_sigma": 0.22,
            "domain": "equity_duration",
        },
        ("revenue_growth", "earnings_growth"): {
            "equation": "earnings_growth_t = e0 + 0.67 * revenue_growth_t + eps_t",
            "direct_effect": 1.08,
            "noise_sigma": 0.2,
            "domain": "fundamentals",
        },
        ("earnings_growth", "equity_valuation"): {
            "equation": "equity_valuation_t = f0 + 0.44 * earnings_growth_t + eps_t",
            "direct_effect": 1.09,
            "noise_sigma": 0.21,
            "domain": "equity_pricing",
        },
        ("credit_spread", "equity_valuation"): {
            "equation": "equity_valuation_t = g0 - 0.35 * credit_spread_t + eps_t",
            "direct_effect": 1.07,
            "noise_sigma": 0.2,
            "domain": "financial_conditions",
        },
    }

    def build_causal_skeleton(self, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for raw_edge in edges:
            edge = self._to_ontology_edge(raw_edge)
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
                    "scm_boost": scored["scm_boost"],
                    "structural_equation": scored["structural_equation"],
                    "scm": scored["scm"],
                    "head_object": edge.get("head_object"),
                    "tail_object": edge.get("tail_object"),
                    "ontology_predicate": edge.get("ontology_predicate"),
                    "data_lineage": edge.get("data_lineage") or [],
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
                existing["scm_boost"] = max(float(existing.get("scm_boost", 1.0)), scored["scm_boost"])
                existing["reasoning_tags"] = sorted(
                    set(existing.get("reasoning_tags", [])) | set(scored["reasoning_tags"])
                )
                if scored.get("structural_equation"):
                    existing["structural_equation"] = scored["structural_equation"]
                    existing["scm"] = scored["scm"]
                existing["data_lineage"] = self._merge_lineage(
                    existing.get("data_lineage", []),
                    edge.get("data_lineage") or [],
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
                direct_effect = self._scm_direct_effect(link)
                propagated = current_delta * strength * decay * polarity * direct_effect
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
                "confidence_interval": {"level": 0.95, "lower": 0.0, "upper": 0.0},
                "data_lineage": [],
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
                    "head_object": link.get("head_object"),
                    "tail_object": link.get("tail_object"),
                    "structural_equation": link.get("structural_equation"),
                    "scm": link.get("scm") or {},
                    "data_lineage": link.get("data_lineage") or [],
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
        confidence_interval = self._influence_confidence_interval(best["abs_score"], best["edges"])
        data_lineage = self._build_data_lineage(best["edges"])

        return {
            "target_node": target,
            "root_cause": best["path"][0] if best["path"] else target,
            "path": best["path"],
            "edge_path": best["edges"],
            "influence_score": best["abs_score"],
            "directional_effect": best["signed_score"],
            "confidence_interval": confidence_interval,
            "data_lineage": data_lineage,
            "top_paths": [
                {
                    "path": row["path"],
                    "influence_score": row["abs_score"],
                    "directional_effect": row["signed_score"],
                    "confidence_interval": self._influence_confidence_interval(row["abs_score"], row["edges"]),
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
        scm_boost, scm_equation, scm_meta = self._scm_modifier(head, tail)
        strength = self._clamp(base * relation_boost * matrix_boost * scm_boost, 0.05, 0.98)

        relation_polarity = self._relation_polarity(relation)
        polarity = self._clamp(matrix_polarity * relation_polarity, -1.0, 1.0)

        tags: List[str] = ["base_signal"]
        if relation_boost > 1.0:
            tags.append("relation_weighted")
        if matrix_tag:
            tags.append(matrix_tag)
        if scm_equation:
            tags.append("scm_direct")

        return {
            "strength": strength,
            "polarity": polarity,
            "matrix_boost": matrix_boost,
            "scm_boost": scm_boost,
            "structural_equation": scm_equation,
            "scm": scm_meta,
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

    def _scm_modifier(self, head_node: str, tail_node: str) -> Tuple[float, str, Dict[str, Any]]:
        head_concepts = self._match_concepts(head_node)
        tail_concepts = self._match_concepts(tail_node)
        if not head_concepts or not tail_concepts:
            return 1.0, "", {}

        best_multiplier = 1.0
        best_equation = ""
        best_meta: Dict[str, Any] = {}
        for head in head_concepts:
            for tail in tail_concepts:
                spec = self.SCM_EQUATIONS.get((head, tail))
                if not spec:
                    continue
                direct_effect = float(spec.get("direct_effect", 1.0))
                if direct_effect > best_multiplier:
                    best_multiplier = direct_effect
                    best_equation = self._as_str(spec.get("equation"))
                    best_meta = {
                        "direct_effect": direct_effect,
                        "noise_sigma": float(spec.get("noise_sigma", 0.2)),
                        "domain": self._as_str(spec.get("domain")),
                        "source_pair": f"{head}->{tail}",
                    }
        return best_multiplier, best_equation, best_meta

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

    def _to_ontology_edge(self, edge: Dict[str, Any]) -> Dict[str, Any]:
        head = self._as_str(edge.get("head_node") or (edge.get("head_object") or {}).get("label"))
        tail = self._as_str(edge.get("tail_node") or (edge.get("tail_object") or {}).get("label"))
        relation = self._as_str(edge.get("relation"))
        props = dict(edge.get("properties") or {})
        if edge.get("doc_id"):
            props.setdefault("doc_id", edge.get("doc_id"))
        if edge.get("case_id"):
            props.setdefault("case_id", edge.get("case_id"))

        head_obj = self._to_business_object(label=head, role="head", edge=edge)
        tail_obj = self._to_business_object(label=tail, role="tail", edge=edge)
        return {
            **edge,
            "head_node": head_obj["label"],
            "tail_node": tail_obj["label"],
            "relation": relation,
            "properties": props,
            "head_object": head_obj,
            "tail_object": tail_obj,
            "ontology_predicate": self._ontology_predicate(relation),
            "data_lineage": self._build_edge_lineage(edge, head_obj, tail_obj),
        }

    def _to_business_object(self, label: str, role: str, edge: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self._normalize_text(label)
        obj_type = self._infer_object_type(normalized, role=role, edge=edge)
        canonical = normalized or f"unknown {obj_type}"
        object_id = f"{obj_type}:{canonical.replace(' ', '_')}"
        source_attrs = dict((edge.get("properties") or {}))
        if edge.get("doc_id"):
            source_attrs["doc_id"] = edge.get("doc_id")
        if edge.get("case_id"):
            source_attrs["case_id"] = edge.get("case_id")

        obj = BusinessObject(
            object_id=object_id,
            object_type=obj_type,
            label=self._as_str(label) or canonical,
            canonical_name=canonical,
            attributes=source_attrs,
        )
        return obj.to_dict()

    def _infer_object_type(self, normalized_label: str, role: str, edge: Dict[str, Any]) -> str:
        if not normalized_label:
            return "metric" if role == "tail" else "entity"
        relation = self._as_str(edge.get("relation")).lower()
        if any(word in normalized_label for word in ("inc", "corp", "ltd", "plc", "company", "holdings")):
            return "company"
        if any(word in normalized_label for word in ("event", "meeting", "filing", "guidance", "announcement")):
            return "event"
        if any(word in relation for word in ("reported", "states", "mentions")) and role == "tail":
            return "observation"
        if any(ch.isdigit() for ch in normalized_label) and role == "tail":
            return "measurement"
        if any(word in normalized_label for word in ("rate", "yield", "spread", "growth", "valuation", "inflation")):
            return "metric"
        return "entity" if role == "head" else "metric"

    def _ontology_predicate(self, relation: str) -> str:
        rel = self._normalize_text(relation)
        if not rel:
            return "related_to"
        if "drives" in rel or "causes" in rel:
            return "causally_influences"
        if "reported" in rel or "states" in rel:
            return "observes"
        if "correlates" in rel:
            return "correlates_with"
        return rel.replace(" ", "_")

    def _build_edge_lineage(
        self,
        edge: Dict[str, Any],
        head_obj: Dict[str, Any],
        tail_obj: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        lineage_rows = edge.get("data_lineage")
        if isinstance(lineage_rows, list) and lineage_rows:
            return lineage_rows
        props = edge.get("properties") or {}
        return [
            {
                "doc_id": self._as_str(edge.get("doc_id") or props.get("doc_id")),
                "case_id": self._as_str(edge.get("case_id") or props.get("case_id")),
                "source_fact_id": self._as_str(props.get("fact_id") or props.get("id")),
                "source_statement": self._as_str(props.get("statement")),
                "head_object_id": head_obj.get("object_id"),
                "tail_object_id": tail_obj.get("object_id"),
                "time_source": self._as_str(edge.get("time_source") or props.get("time_source")),
                "event_time": self._as_str(edge.get("event_time") or props.get("event_time")),
                "observed_at": self._as_str(edge.get("observed_at") or props.get("observed_at")),
            }
        ]

    def _merge_lineage(self, left: List[Dict[str, Any]], right: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows = []
        seen: Set[str] = set()
        for lineage in list(left) + list(right):
            sig = "|".join(
                [
                    self._as_str(lineage.get("doc_id")),
                    self._as_str(lineage.get("case_id")),
                    self._as_str(lineage.get("source_fact_id")),
                    self._as_str(lineage.get("head_object_id")),
                    self._as_str(lineage.get("tail_object_id")),
                    self._as_str(lineage.get("event_time")),
                ]
            )
            if sig in seen:
                continue
            seen.add(sig)
            rows.append(lineage)
        return rows

    def _scm_direct_effect(self, link: Dict[str, Any]) -> float:
        scm_meta = link.get("scm")
        if isinstance(scm_meta, dict):
            val = scm_meta.get("direct_effect")
            if isinstance(val, (int, float)):
                return self._clamp(float(val), 0.7, 1.4)
        return 1.0

    def _influence_confidence_interval(self, influence: float, edge_path: List[Dict[str, Any]]) -> Dict[str, Any]:
        if influence <= 0 or not edge_path:
            return {"level": 0.95, "lower": 0.0, "upper": max(0.0, influence)}

        variance = 0.0
        for edge in edge_path:
            strength = self._clamp(float(edge.get("strength", 0.3)), 0.05, 0.98)
            support = max(1, int(edge.get("support_count", 1)))
            scm_noise = 0.2
            scm_meta = edge.get("scm")
            if isinstance(scm_meta, dict):
                scm_noise = float(scm_meta.get("noise_sigma", 0.2))
            variance += ((1.0 - strength) + scm_noise) * (0.04 / support)

        std = math.sqrt(max(variance, 0.0))
        margin = 1.96 * std
        lower = max(0.0, influence - margin)
        upper = influence + margin
        return {"level": 0.95, "lower": round(lower, 6), "upper": round(upper, 6)}

    def _build_data_lineage(self, edge_path: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for edge in edge_path:
            lineage_rows = edge.get("data_lineage")
            if isinstance(lineage_rows, list):
                rows.extend(lineage_rows)
            else:
                rows.append(
                    {
                        "doc_id": "",
                        "source_fact_id": "",
                        "source_statement": "",
                        "head_object_id": (edge.get("head_object") or {}).get("object_id"),
                        "tail_object_id": (edge.get("tail_object") or {}).get("object_id"),
                        "event_time": self._as_str(edge.get("event_time")),
                    }
                )
        return self._merge_lineage([], rows)

    def _as_str(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(value, high))
