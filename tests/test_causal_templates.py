import pytest


@pytest.mark.asyncio
async def test_causal_template_triples_present():
    from app.services.types import DistillResult
    from app.services.spokes import extract_graph_triples

    distill = DistillResult(
        facts=[
            {"entity": "Macro", "metric": "FEDFUNDS", "value": "5.50", "period_norm": "2025-01-31"},
            {"entity": "Macro", "metric": "10Y Treasury Yield", "value": "4.10", "period_norm": "2025-01-31"},
            {"entity": "Macro", "metric": "DXY", "value": "103.2", "period_norm": "2025-01-31"},
            {"entity": "TechCo", "metric": "interest expense", "value": "12.0", "period_norm": "2025-01-31"},
            {"entity": "TechCo", "metric": "capex", "value": "8.0", "period_norm": "2025-01-31"},
            {"entity": "TechCo", "metric": "vendor_of", "vendor": "SupplierCo", "value": "SupplierCo", "period_norm": "2025-01-31"},
            {"entity": "Market", "metric": "VIX", "value": "28.0", "period_norm": "2025-01-31"},
        ],
        cot_markdown="",
        metadata={"company": "TechCo", "document_date": "2025-01-31"},
    )

    triples = extract_graph_triples(distill)
    rels = {(t.get("head_node"), t.get("relation"), t.get("tail_node")) for t in triples}
    assert ("Fed Rate", "causal_affects", "Discount Rate") in rels
    assert ("10Y Treasury Yield", "causal_affects", "Discount Rate") in rels
    assert ("DXY Strength", "causal_affects", "FX Loss Risk") in rels
    assert ("VIX Spike", "causal_affects", "Market Panic") in rels
