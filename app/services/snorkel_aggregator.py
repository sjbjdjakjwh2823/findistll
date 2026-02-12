import re
from typing import Any, Dict, List

from app.services.labeling_functions import LFResult


class SnorkelAggregator:
    """
    Weighted vote aggregator for labeling function outputs.
    """

    def aggregate(self, lf_results: List[LFResult]) -> Dict[str, Any]:
        valid = [r for r in lf_results if r.value]
        if not valid:
            return {
                "final_value": None,
                "confidence": 0.0,
                "agreeing_lfs": [],
                "disagreeing_lfs": [],
                "method": "no_valid_results",
            }

        normalized = []
        for r in valid:
            normalized_value = self._normalize_value(r.value)
            normalized.append(
                {
                    "lf_name": r.lf_name,
                    "original": r.value,
                    "normalized": normalized_value,
                    "confidence": r.confidence,
                }
            )

        weights: Dict[str, float] = {}
        for r in normalized:
            value = r["normalized"]
            if not value:
                continue
            weights[value] = weights.get(value, 0.0) + r["confidence"]

        if not weights:
            return {
                "final_value": None,
                "confidence": 0.0,
                "agreeing_lfs": [],
                "disagreeing_lfs": [],
                "method": "normalization_failed",
            }

        best_value = max(weights.keys(), key=lambda v: weights[v])
        total_weight = sum(weights.values())
        aggregated_confidence = weights[best_value] / total_weight if total_weight else 0.0

        agreeing = [r["lf_name"] for r in normalized if r["normalized"] == best_value]
        disagreeing = [r["lf_name"] for r in normalized if r["normalized"] != best_value]

        return {
            "final_value": best_value,
            "confidence": round(aggregated_confidence, 3),
            "agreeing_lfs": agreeing,
            "disagreeing_lfs": disagreeing,
            "method": "weighted_voting",
            "vote_distribution": weights,
        }

    def _normalize_value(self, value: str) -> str:
        if value is None:
            return ""
        normalized = str(value)
        normalized = normalized.replace(",", "")
        normalized = re.sub(r"[억원만%$]", "", normalized)
        normalized = normalized.strip()
        return normalized
