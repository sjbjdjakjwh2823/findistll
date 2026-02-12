import re
from typing import Any, Dict, List

from app.services.types import DecisionResult, DistillResult


class SelfCheckService:
    """
    Lightweight SelfCheck-style consistency scorer.

    Heuristic: compare decision rationale vs extracted facts and compute
    coverage of key terms. Designed to be fast and offline-friendly.
    """

    def evaluate(self, decision: DecisionResult, distill: DistillResult) -> Dict[str, Any]:
        rationale = (decision.rationale or "").lower()
        facts = distill.facts or []

        checks = []
        matched_terms_total = 0
        total_terms = 0

        for fact in facts[:20]:
            field, terms = self._fact_terms(fact)
            if not terms:
                continue

            total_terms += len(terms)
            matched = [t for t in terms if t in rationale]
            matched_terms_total += len(matched)

            score = len(matched) / max(1, len(terms))
            checks.append(
                {
                    "field": field,
                    "score": round(score, 3),
                    "level": self._level(score),
                    "matched_terms": matched,
                }
            )

        overall = matched_terms_total / max(1, total_terms)
        return {
            "consistency_score": round(overall, 3),
            "confidence_level": self._level(overall),
            "confidence_score": round(overall, 3),
            "field_checks": checks,
        }

    def _fact_terms(self, fact: Any) -> tuple[str, List[str]]:
        if isinstance(fact, dict):
            field = str(fact.get("concept") or fact.get("key") or fact.get("label") or "fact")
            values = [str(fact.get("value") or ""), field]
        else:
            field = "fact"
            values = [str(fact)]

        terms = []
        for value in values:
            for token in re.split(r"[\\s,;:()]+", value.lower()):
                token = token.strip()
                if token and len(token) > 2:
                    terms.append(token)

        return field, list(dict.fromkeys(terms))

    def _level(self, score: float) -> str:
        if score >= 0.8:
            return "High"
        if score >= 0.6:
            return "Medium"
        return "Low"
