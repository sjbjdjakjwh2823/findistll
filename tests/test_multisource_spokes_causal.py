from __future__ import annotations

import pytest

from app.db.client import InMemoryDB
from app.services.orchestrator import Orchestrator
from app.services.types import DecisionResult, DistillResult
from app.services.robot_engine import FinRobotAdapter


class _StubDistillEngine:
    async def extract(self, document: dict) -> DistillResult:
        # Multi-source facts: market + fundamentals + macro + events + alt + ownership
        entity = "ACME Corp"
        facts = [
            # Fundamentals (quarterly series)
            {"entity": entity, "metric": "revenue", "period": "2023Q4", "period_norm": "2023-12-31", "unit": "currency", "value": "100"},
            {"entity": entity, "metric": "revenue", "period": "2024Q1", "period_norm": "2024-03-31", "unit": "currency", "value": "110"},
            {"entity": entity, "metric": "revenue", "period": "2024Q2", "period_norm": "2024-06-30", "unit": "currency", "value": "120"},
            {"entity": entity, "metric": "revenue", "period": "2024Q3", "period_norm": "2024-09-30", "unit": "currency", "value": "130"},
            {"entity": entity, "metric": "revenue", "period": "2024Q4", "period_norm": "2024-12-31", "unit": "currency", "value": "140"},
            {"entity": entity, "metric": "net income", "period": "2023Q4", "period_norm": "2023-12-31", "unit": "currency", "value": "10"},
            {"entity": entity, "metric": "net income", "period": "2024Q1", "period_norm": "2024-03-31", "unit": "currency", "value": "11"},
            {"entity": entity, "metric": "net income", "period": "2024Q2", "period_norm": "2024-06-30", "unit": "currency", "value": "13"},
            {"entity": entity, "metric": "net income", "period": "2024Q3", "period_norm": "2024-09-30", "unit": "currency", "value": "12"},
            {"entity": entity, "metric": "net income", "period": "2024Q4", "period_norm": "2024-12-31", "unit": "currency", "value": "15"},
            # Market (price series)
            {"entity": entity, "metric": "price", "period": "2024-09", "period_norm": "2024-09-30", "unit": "currency", "value": "50"},
            {"entity": entity, "metric": "price", "period": "2024-10", "period_norm": "2024-10-31", "unit": "currency", "value": "52"},
            {"entity": entity, "metric": "price", "period": "2024-11", "period_norm": "2024-11-30", "unit": "currency", "value": "55"},
            {"entity": entity, "metric": "price", "period": "2024-12", "period_norm": "2024-12-31", "unit": "currency", "value": "54"},
            {"entity": entity, "metric": "volume", "period": "2024-12", "period_norm": "2024-12-31", "unit": "count", "value": "1000000"},
            # Macro (FRED-like, percent unit)
            {"entity": "FEDFUNDS", "metric": "interest rate", "period": "2024-09-30", "period_norm": "2024-09-30", "unit": "percent", "value": "5.33"},
            {"entity": "FEDFUNDS", "metric": "interest rate", "period": "2024-10-31", "period_norm": "2024-10-31", "unit": "percent", "value": "5.33"},
            {"entity": "FEDFUNDS", "metric": "interest rate", "period": "2024-11-30", "period_norm": "2024-11-30", "unit": "percent", "value": "5.33"},
            {"entity": "FEDFUNDS", "metric": "interest rate", "period": "2024-12-31", "period_norm": "2024-12-31", "unit": "percent", "value": "5.33"},
            # Events / alternative / ownership (as signals)
            {"entity": entity, "metric": "event_earnings", "period": "2024-11-01", "period_norm": "2024-11-01", "unit": "event", "value": "earnings beat"},
            {"entity": entity, "metric": "sentiment", "period": "2024-11", "period_norm": "2024-11-30", "unit": "ratio", "value": "0.72"},
            {"entity": entity, "metric": "short interest", "period": "2024-11", "period_norm": "2024-11-30", "unit": "ratio", "value": "0.08"},
            # Supply-chain / relationship (graph triple extraction uses vendor/customer/related_entity keys)
            {"entity": entity, "metric": "supplier", "vendor": "FOUNDRY Inc", "period": "2024Q4", "unit": "ratio", "value": "1.0"},
        ]
        return DistillResult(
            facts=facts,
            cot_markdown="ACME Corp partnered with FOUNDRY Inc to secure supply.",
            metadata={"company": entity, "entity": entity, "source": "test"},
        )


@pytest.mark.asyncio
async def test_multisource_spokes_emit_math_and_causal_triples():
    db = InMemoryDB()
    distill = _StubDistillEngine()
    robot = FinRobotAdapter()  # runs fallback path by default
    orch = Orchestrator(db, distill, robot)

    case_id = db.create_case({"title": "multi-source"})
    result = await orch.run(case_id, {"content": "ignored"})
    assert result.case_id == case_id

    # Spoke C should include a math-derived evidence chunk for market/fundamental metrics.
    rag = db.list_rag_context(limit=500)
    assert any(r.get("source") == "preciso_mathematics" for r in rag), "missing math evidence in Spoke C"

    # Spoke D should include causal_affects triples materialized from training_set.
    triples = db.list_graph_triples(limit=2000)
    assert any(t.get("relation") == "causal_affects" for t in triples), "missing causal_affects triples in Spoke D"

    # Training set should carry causal candidates (Spoke D signal)
    training = db.list_training_sets(limit=50)
    assert training, "missing training set rows"
    predictive = (training[0].get("predictive_signals") or {}) if isinstance(training[0], dict) else {}
    # InMemoryDB stores the full training_set dict as inserted, so keys are at top-level.
    if "predictive_signals" not in training[0]:
        # Supabase schema stores fields; InMemory stores full record.
        predictive = (training[0].get("predictive_signals") or {})
    candidates = (predictive.get("causal_candidates") or []) if isinstance(predictive, dict) else []
    assert len(candidates) >= 1, "expected at least one causal candidate"
