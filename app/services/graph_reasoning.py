from typing import Any, Dict, List


class GraphReasoningService:
    """
    Risk inference using Knowledge Graph neighborhood.
    """

    PRIORITY_SCORE = {"high": 0.9, "medium": 0.6, "low": 0.3}

    def __init__(self, client) -> None:
        self.client = client

    def predict_risk(self, entity_id: str) -> Dict[str, Any]:
        neighbors = (
            self.client.table("kg_relationships")
            .select("*")
            .or_(f"source_entity_id.eq.{entity_id},target_entity_id.eq.{entity_id}")
            .execute()
        ).data or []

        neighbor_entity_ids = set()
        for rel in neighbors:
            neighbor_entity_ids.add(rel.get("source_entity_id"))
            neighbor_entity_ids.add(rel.get("target_entity_id"))
        neighbor_entity_ids.discard(entity_id)

        cases = []
        if neighbor_entity_ids:
            case_rows = (
                self.client.table("ops_cases")
                .select("id,priority,status,entity_id")
                .in_("entity_id", list(neighbor_entity_ids))
                .execute()
            ).data or []
            cases = case_rows

        score = self._score_cases(cases)
        return {
            "entity_id": entity_id,
            "neighbor_count": len(neighbor_entity_ids),
            "case_count": len(cases),
            "risk_score": score,
            "risk_level": self._level(score),
        }

    def _score_cases(self, cases: List[Dict[str, Any]]) -> float:
        if not cases:
            return 0.5
        weighted = 0.0
        for case in cases:
            priority = str(case.get("priority", "medium")).lower()
            weighted += self.PRIORITY_SCORE.get(priority, 0.6)
        return round(weighted / max(1, len(cases)), 3)

    def _level(self, score: float) -> str:
        if score >= 0.8:
            return "HIGH"
        if score >= 0.6:
            return "MEDIUM"
        return "LOW"

    def find_three_hop_paths(self, entity_id: str, max_hops: int = 3, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Find paths up to 3 hops in kg_relationships.
        Returns list of paths with nodes + relations.
        """
        rels = (
            self.client.table("kg_relationships")
            .select("source_entity_id,target_entity_id,relationship_type,properties")
            .execute()
        ).data or []

        # Build adjacency
        adj: Dict[str, List[Dict[str, Any]]] = {}
        for r in rels:
            src = r.get("source_entity_id")
            dst = r.get("target_entity_id")
            if not src or not dst:
                continue
            adj.setdefault(src, []).append({
                "to": dst,
                "relation": r.get("relationship_type") or "related_to",
                "properties": r.get("properties") or {},
            })

        paths: List[Dict[str, Any]] = []
        queue: List[Dict[str, Any]] = [{"node": entity_id, "path": []}]
        seen = set()

        while queue and len(paths) < limit:
            cur = queue.pop(0)
            node = cur["node"]
            path = cur["path"]
            if len(path) >= max_hops:
                continue
            for edge in adj.get(node, []):
                nxt = edge["to"]
                step = {"from": node, "to": nxt, "relation": edge["relation"], "properties": edge["properties"]}
                new_path = path + [step]
                key = (entity_id, nxt, len(new_path), tuple((p["from"], p["relation"], p["to"]) for p in new_path))
                if key in seen:
                    continue
                seen.add(key)
                paths.append({
                    "start": entity_id,
                    "end": nxt,
                    "hops": len(new_path),
                    "steps": new_path,
                })
                queue.append({"node": nxt, "path": new_path})

        return paths
