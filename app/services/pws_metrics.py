from typing import Any, Dict, List

from app.services.labeling_functions import LFResult


def compute_lf_metrics(lf_results: List[LFResult]) -> Dict[str, Any]:
    total = len(lf_results)
    valid = [r for r in lf_results if r.value is not None]
    coverage = len(valid) / total if total else 0.0

    values = [r.value for r in valid]
    conflicts = 0
    if values:
        unique = set(values)
        conflicts = 1 if len(unique) > 1 else 0

    per_lf = {}
    for r in lf_results:
        per_lf.setdefault(r.lf_name, {"hits": 0, "total": 0})
        per_lf[r.lf_name]["total"] += 1
        if r.value is not None:
            per_lf[r.lf_name]["hits"] += 1

    return {
        "coverage": round(coverage, 3),
        "conflict": conflicts,
        "per_lf": per_lf,
    }


def compute_label_noise(metrics: Dict[str, Any]) -> float:
    """
    Heuristic label noise estimate based on conflict + low coverage.
    """
    coverage = float(metrics.get("coverage", 0.0))
    conflict = float(metrics.get("conflict", 0.0))
    noise = (1 - coverage) * 0.5 + conflict * 0.5
    return round(max(0.0, min(1.0, noise)), 3)
