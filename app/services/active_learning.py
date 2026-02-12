from typing import Any, Dict, List


class ActiveLearningPrioritizer:
    """
    Prioritize cases for HITL review.

    Uses uncertainty (1 - consistency_score) + impact (priority) + recency.
    """

    PRIORITY_IMPACT = {"high": 0.9, "medium": 0.6, "low": 0.3}

    def prioritize(self, cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        scored = []
        for case in cases:
            uncertainty = 1.0 - float(case.get("consistency_score", 0.5))
            impact = self.PRIORITY_IMPACT.get(str(case.get("priority", "medium")).lower(), 0.6)
            recency = 0.5
            score = uncertainty * 0.5 + impact * 0.3 + recency * 0.2
            scored.append({**case, "priority_score": round(score, 3)})

        scored.sort(key=lambda x: x["priority_score"], reverse=True)
        return scored
