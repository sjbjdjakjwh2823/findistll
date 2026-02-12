import pytest


@pytest.mark.asyncio
async def test_causal_story_builds_chain_with_hypothesis(monkeypatch):
    from app.db.client import InMemoryDB
    from app.services.causal_story import CausalStoryService
    from app.services.types import DistillResult
    from app.services.spokes import build_rag_context

    db = InMemoryDB()

    # Stub FRED series call so the test is deterministic and offline.
    async def _fake_fred(series_id: str, limit: int = 1, **kwargs):
        assert series_id == "FEDFUNDS"
        return [
            {"date": "2025-01-31", "value": "5.50"},
            {"date": "2024-12-31", "value": "5.25"},
        ][:limit]

    monkeypatch.setattr("app.services.market_data.market_data_service.fetch_fred_series", _fake_fred)

    distill = DistillResult(
        facts=[
            # Fundamentals
            {"entity": "TechCo", "metric": "netincome", "value": "10.0", "unit": "USD", "period_norm": "2024-12-31"},
            {"entity": "TechCo", "metric": "debt_ratio", "value": "0.7", "unit": "ratio", "period_norm": "2024-12-31"},
            # Supply chain edges (3-hop)
            {"entity": "TechCo", "metric": "vendor_of", "vendor": "SupplierCo", "value": "SupplierCo", "period_norm": "2024-12-31"},
            {"entity": "SupplierCo", "metric": "vendor_of", "vendor": "SubSupplierCo", "value": "SubSupplierCo", "period_norm": "2024-12-31"},
            {"entity": "SubSupplierCo", "metric": "vendor_of", "vendor": "RawMaterialsCo", "value": "RawMaterialsCo", "period_norm": "2024-12-31"},
            # Market facts
            {"entity": "TechCo", "metric": "close_price", "value": "100.0", "unit": "USD", "period_norm": "2025-01-31"},
            {"entity": "TechCo", "metric": "volume", "value": "999999", "unit": "shares", "period_norm": "2025-01-31"},
        ],
        cot_markdown="TechCo faces rate sensitivity; supply chain exposure noted.",
        metadata={"company": "TechCo", "document_date": "2025-01-31"},
    )

    # Seed evidence into Spoke C so evidence_chunk_ids can be returned.
    contexts = build_rag_context(distill, case_id="doc_test")
    db.save_rag_context("doc_test", contexts)

    service = CausalStoryService(db=db)
    story = await service.build_story(distill=distill, entity_hint="TechCo", as_of="2025-01-31", horizon_days=30)

    assert story["status"] == "ok"
    cats = [s["category"] for s in story["steps"]]
    assert "macro" in cats
    assert "fundamentals" in cats
    assert "supply_chain" in cats
    assert "market" in cats
    # Forecast must be separate and marked hypothesis.
    assert story.get("forecast")
    assert story["forecast"]["step_type"] == "hypothesis"
    hyp_steps = [s for s in story["steps"] if s["category"] == "hypothesis"]
    assert not hyp_steps
    assert story.get("cause_effect")


@pytest.mark.asyncio
async def test_math_is_visible_in_spoke_c_and_spoke_d(monkeypatch):
    from app.services.types import DistillResult
    from app.services.spokes import build_rag_context, extract_graph_triples
    from app.services.spoke_ab_service import SpokeABService
    from app.db.client import InMemoryDB
    import polars as pl
    import io

    # A small time-series so PrecisoMathematics emits derived features.
    distill = DistillResult(
        facts=[
            {"entity": "TechCo", "metric": "revenue", "value": "100", "unit": "USD", "period_norm": "2024-01-01"},
            {"entity": "TechCo", "metric": "revenue", "value": "110", "unit": "USD", "period_norm": "2024-04-01"},
            {"entity": "TechCo", "metric": "revenue", "value": "90", "unit": "USD", "period_norm": "2024-07-01"},
            {"entity": "TechCo", "metric": "revenue", "value": "120", "unit": "USD", "period_norm": "2024-10-01"},
        ],
        cot_markdown="",
        metadata={"company": "TechCo", "document_date": "2024-10-01"},
    )

    # Spoke C should include math evidence chunks
    ctx = build_rag_context(distill, case_id="doc_math")
    assert any("Preciso Mathematics (Derived Time-Series)" in (c.get("text_content") or "") for c in ctx)

    # Spoke D should include series nodes / derived triples
    triples = extract_graph_triples(distill)
    assert any(str(t.get("head_node", "")).startswith("series:") for t in triples) or any(str(t.get("tail_node", "")).startswith("series:") for t in triples)

    # Spoke B features parquet should have derived columns.
    service = SpokeABService()
    artifacts = service.build_spoke_b_parquets(tenant_id="t1", doc_id="doc_math", distill=distill, normalized={"tables": []})
    feats = artifacts["features"]
    df = pl.read_parquet(io.BytesIO(feats))
    assert "pct_change" in df.columns
    assert "log_return" in df.columns
    assert "zscore" in df.columns
