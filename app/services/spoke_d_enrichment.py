from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _metric_node(entity: str, metric: str) -> str:
    return f"metric:{entity}::{metric}"


def build_causal_triples_from_training_set(training_set: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert training_set predictive_signals into explicit Spoke D triples.

    This makes causal candidates "queryable" via `spoke_d_graph` (works across DB backends),
    and enables on-prem 3-hop reasoning without Supabase OpsGraph.
    """
    out: List[Dict[str, Any]] = []
    signals = (training_set or {}).get("predictive_signals") or {}
    candidates = (signals.get("causal_candidates") or []) if isinstance(signals, dict) else []
    method = signals.get("method") if isinstance(signals, dict) else None
    confidence_method = signals.get("confidence_method") if isinstance(signals, dict) else None

    # Keep the graph compact and deterministic.
    top = candidates[:30]
    for item in top:
        try:
            entity = str(item.get("entity") or "").strip()
            cause_metric = str(item.get("cause_metric") or "").strip()
            effect_metric = str(item.get("effect_metric") or "").strip()
        except Exception:
            continue
        if not entity or not cause_metric or not effect_metric:
            continue

        props = {
            "entity": entity,
            "lag": item.get("lag"),
            "correlation": item.get("correlation"),
            "granger_score": item.get("granger_score"),
            "score": item.get("score"),
            "confidence": item.get("confidence"),
            "method": method,
            "confidence_method": confidence_method,
            "source": "spokes_training_set",
        }

        src_node = _metric_node(entity, cause_metric)
        dst_node = _metric_node(entity, effect_metric)

        out.append({"head_node": entity, "relation": "has_metric", "tail_node": src_node, "properties": {"metric": cause_metric}})
        out.append({"head_node": entity, "relation": "has_metric", "tail_node": dst_node, "properties": {"metric": effect_metric}})
        out.append({"head_node": src_node, "relation": "causal_affects", "tail_node": dst_node, "properties": props})
    return out

