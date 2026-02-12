import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import polars as pl

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from app.services.distill_engine import FinDistillAdapter
from app.services.spokes import build_rag_context, extract_graph_triples, build_training_set
from app.services.types import DecisionResult, DistillResult


ARTIFACTS_DIR = ROOT_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


SAMPLE_TEXT = """\
ACME FINANCIALS SUMMARY
Company: Acme Industrial Holdings
Fiscal Year: 2024

Income Statement
2021 Revenue: 120.5
2022 Revenue: 132.8
2023 Revenue: 147.3
2024 Revenue: 159.9
2021 Net Income: 12.2
2022 Net Income: 14.7
2023 Net Income: 17.1
2024 Net Income: 18.8

Balance Sheet
2021 Total Assets: 300.0
2022 Total Assets: 320.5
2023 Total Assets: 351.2
2024 Total Assets: 389.4
"""


def _fallback_structured_extract(text: str) -> DistillResult:
    facts: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        try:
            left, right = line.split(":", 1)
            value = float(right.strip())
        except ValueError:
            continue
        left_parts = left.split()
        if not left_parts:
            continue
        period = left_parts[0]
        metric = " ".join(left_parts[1:])
        facts.append(
            {
                "entity": "Acme Industrial Holdings",
                "metric": metric,
                "label": metric,
                "period": period,
                "value": value,
                "unit": "currency",
                "source": "fallback_structured",
                "confidence_score": 0.6,
                "tags": ["confidence_imputed"],
            }
        )
    return DistillResult(
        facts=facts,
        cot_markdown="Fallback structured extraction applied.",
        metadata={"source": "fallback_structured"},
    )


async def run_spoke_check() -> Dict[str, Any]:
    adapter = FinDistillAdapter()
    document = {
        "filename": "acme_financials.txt",
        "mime_type": "text/plain",
        "content": SAMPLE_TEXT,
        "source": "sample",
        "doc_id": "sample-acme-2024",
        "company_name": "Acme Industrial Holdings",
    }

    distill = await adapter.extract(document)
    if not distill.facts:
        distill = _fallback_structured_extract(SAMPLE_TEXT)

    rag_contexts = build_rag_context(distill, case_id="sample-case")
    graph_triples = extract_graph_triples(distill)
    decision_stub = DecisionResult(
        decision="monitor",
        rationale="Synthetic decision for spoke verification.",
    )
    training_set = build_training_set("sample-case", distill, decision_stub)

    spoke_a = bool(distill.cot_markdown.strip())
    spoke_b = any(
        isinstance(fact, dict) and ("confidence_score" in fact or fact.get("tags"))
        for fact in distill.facts
    )
    spoke_c = len(rag_contexts) > 0
    spoke_d = len(training_set.get("predictive_signals", {}).get("causal_candidates", [])) > 0

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "spokes": {
            "A_cot_or_scenario": spoke_a,
            "B_confidence_or_tags": spoke_b,
            "C_rag_context": spoke_c,
            "D_causal_candidates": spoke_d,
        },
        "counts": {
            "facts": len(distill.facts),
            "rag_contexts": len(rag_contexts),
            "graph_triples": len(graph_triples),
            "causal_candidates": len(training_set.get("predictive_signals", {}).get("causal_candidates", [])),
        },
    }

    payload = {
        "summary": summary,
        "distill": {
            "facts": distill.facts,
            "cot_markdown": distill.cot_markdown,
            "metadata": distill.metadata,
        },
        "rag_contexts": rag_contexts,
        "graph_triples": graph_triples,
        "training_set": training_set,
    }

    output_path = ARTIFACTS_DIR / "findistill_spokes_output.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    def _safe_csv_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        safe_rows: List[Dict[str, Any]] = []
        for row in rows:
            safe_row: Dict[str, Any] = {}
            for key, value in row.items():
                if isinstance(value, (dict, list)):
                    safe_row[key] = json.dumps(value, ensure_ascii=False)
                else:
                    safe_row[key] = value
            safe_rows.append(safe_row)
        return safe_rows

    facts_df = pl.DataFrame(_safe_csv_rows(distill.facts))
    facts_df.write_csv(ARTIFACTS_DIR / "findistill_spokes_facts.csv")

    rag_df = pl.DataFrame(_safe_csv_rows(rag_contexts))
    rag_df.write_csv(ARTIFACTS_DIR / "findistill_spokes_rag.csv")

    causal_candidates = training_set.get("predictive_signals", {}).get("causal_candidates", [])
    causal_df = pl.DataFrame(_safe_csv_rows(causal_candidates))
    causal_df.write_csv(ARTIFACTS_DIR / "findistill_spokes_causal.csv")

    return summary


if __name__ == "__main__":
    result = asyncio.run(run_spoke_check())
    print(json.dumps(result, ensure_ascii=False, indent=2))
