from typing import Any, Dict, List


class EvalSuite:
    """
    Lightweight eval suite for alignment/benchmark scoring.
    """

    def score(self, predictions: List[Dict[str, Any]], ground_truth: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not predictions or not ground_truth:
            return {"accuracy": 0.0, "samples": 0}

        matched = 0
        total = min(len(predictions), len(ground_truth))
        latency_values = []
        token_values = []
        evaluator_scores = []
        for idx in range(total):
            pred = predictions[idx]
            gt = ground_truth[idx]
            if str(pred.get("decision")) == str(gt.get("decision")):
                matched += 1
            if pred.get("latency_ms") is not None:
                latency_values.append(float(pred.get("latency_ms")))
            if pred.get("token_usage") is not None:
                token_values.append(float(pred.get("token_usage")))
            evaluations = pred.get("evaluations") or []
            for ev in evaluations:
                if ev.get("score") is not None:
                    evaluator_scores.append(float(ev.get("score")))

        efficiency = None
        if latency_values or token_values:
            efficiency = {
                "avg_latency_ms": round(sum(latency_values) / max(1, len(latency_values)), 2) if latency_values else None,
                "avg_tokens": round(sum(token_values) / max(1, len(token_values)), 2) if token_values else None,
            }

        robustness = None
        if evaluator_scores:
            mean = sum(evaluator_scores) / len(evaluator_scores)
            var = sum((s - mean) ** 2 for s in evaluator_scores) / len(evaluator_scores)
            robustness = {"evaluator_variance": round(var, 4)}

        return {
            "accuracy": round(matched / total, 3),
            "samples": total,
            "efficiency": efficiency,
            "robustness": robustness,
        }
