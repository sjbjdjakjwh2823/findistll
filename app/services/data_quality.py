from typing import Any, Dict


def compute_data_quality(metrics: Dict[str, Any], aggregated_confidence: float) -> float:
    """
    Lightweight data quality score for CPWS-style pruning gates.
    """
    coverage = float(metrics.get("coverage", 0.0))
    conflict = float(metrics.get("conflict", 0.0))
    score = (coverage * 0.5) + (aggregated_confidence * 0.5) - (conflict * 0.2)
    return round(max(0.0, min(1.0, score)), 3)
