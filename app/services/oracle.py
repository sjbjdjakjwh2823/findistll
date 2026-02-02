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

    def build_causal_skeleton(self, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for edge in edges:
            head = self._as_str(edge.get("head_node"))
            relation = self._as_str(edge.get("relation"))
            tail = self._as_str(edge.get("tail_node"))
            if not head or not relation or not tail:
                continue

            key = (head, relation, tail)
            strength = self._edge_strength(edge)
            existing = grouped.get(key)
            if existing is None:
                grouped[key] = {
                    "head_node": head,
                    "relation": relation,
                    "tail_node": tail,
                    "strength": strength,
                    "support_count": 1,
                    "time_granularity": edge.get("time_granularity") or "day",
                }
            else:
                existing["strength"] = max(float(existing["strength"]), strength)
                existing["support_count"] = int(existing["support_count"]) + 1

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
                propagated = current_delta * strength * decay
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
