#!/usr/bin/env python3
"""
Phase 2 Integration Test
Tests RAG and Causal engines without database dependencies.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_spoke_c_rag():
    """Test RAG Engine functionality."""
    from app.services.spoke_c_rag import RAGEngine, RAGResult, RAGContext

    rag = RAGEngine(supabase_client=None, openai_api_key=None)

    test_doc = """
    Apple Inc. reported Q4 2025 earnings with revenue of $120 billion.
    The company's iPhone segment showed strong growth of 15% YoY.
    Services revenue reached a record $25 billion.
    CEO Tim Cook expressed optimism about the AI features in iOS 19.
    The company faces headwinds from regulatory scrutiny in the EU.
    """

    chunks = rag.chunk_document(test_doc, chunk_size=100, overlap=20)
    assert len(chunks) > 0

    mock_results = [
        RAGResult(
            chunk_id="test1",
            content="Apple's revenue growth was driven by iPhone sales.",
            similarity=0.92,
            metadata={"source": "10-K"},
        ),
        RAGResult(
            chunk_id="test2",
            content="Services segment showed record performance.",
            similarity=0.85,
            metadata={"source": "earnings_call"},
        ),
    ]
    context = RAGContext(results=mock_results, query="Apple revenue", total_tokens=50)
    formatted = rag.format_context(context)

    assert "[Retrieved Evidence]" in formatted
    assert "similarity: 0.92" in formatted


def test_spoke_d_causal():
    """Test Causal Engine functionality."""
    from app.services.spoke_d_causal import CausalEngine, CausalNode, CausalEdge

    causal = CausalEngine(supabase_client=None)

    causal.nodes = {
        "n1": CausalNode(id="n1", name="Fed_Funds_Rate", category="macro"),
        "n2": CausalNode(id="n2", name="Tech_Sector_Valuation", category="sector"),
        "n3": CausalNode(id="n3", name="GDP_Growth", category="macro"),
    }

    causal.edges = [
        CausalEdge(
            source_id="n1",
            target_id="n2",
            relation="negative_correlation",
            weight=-0.7,
            lag_days=30,
            confidence=0.85,
        ),
        CausalEdge(
            source_id="n1",
            target_id="n3",
            relation="negative_correlation",
            weight=-0.8,
            lag_days=90,
            confidence=0.75,
        ),
    ]

    result = causal.counterfactual("Fed_Funds_Rate", 0.25)
    assert result.impacts

    factors = causal.get_upstream_factors("Tech_Sector_Valuation")
    assert factors

    formatted = causal.format_context(result)
    assert "Causal Analysis" in formatted


import pytest


@pytest.mark.asyncio
async def test_robot_engine_integration():
    """Test robot engine with Phase 2 integration."""
    from app.services.robot_engine import FinRobotAdapter
    from app.services.types import DistillResult

    adapter = FinRobotAdapter()

    distill = DistillResult(
        facts=[
            {"concept": "NetIncome", "value": 50000000},
            {"concept": "Revenue", "value": 200000000},
            {"concept": "interest_rate_sensitivity", "value": "high"},
        ],
        cot_markdown="Analysis shows strong fundamentals with rate sensitivity.",
        metadata={
            "company": "TechCorp",
            "industry": "Technology",
            "summary": "Tech company with strong growth but interest rate exposure.",
        },
    )

    result = await adapter.decide(distill)
    assert result.decision
    assert result.rationale
    assert result.trace is not None


def test_types():
    """Test updated types with trace field."""
    from app.services.types import DecisionResult

    result = DecisionResult(
        decision="Approve",
        rationale="Strong fundamentals",
        actions=[{"type": "execute", "priority": "high"}],
        approvals=[{"role": "analyst", "required": True}],
        trace={"rag_context": {"results_count": 5}, "latency_ms": 150},
    )

    assert result.trace is not None
    assert result.trace["latency_ms"] == 150


def main():
    print("=" * 60)
    print("🧠 Phase 2: AI Brain - Integration Tests")
    print("=" * 60)

    results = {
        "types": test_types() or True,
        "spoke_c": test_spoke_c_rag() or True,
        "spoke_d": test_spoke_d_causal() or True,
    }

    results["robot_engine"] = asyncio.run(test_robot_engine_integration()) or True

    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"   {status}: {name}")

    print(f"\n   Total: {passed}/{total} tests passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
