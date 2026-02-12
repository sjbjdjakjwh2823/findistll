from __future__ import annotations

import pytest

from app.services.partner_ingest import convert_partner_payload


@pytest.mark.asyncio
async def test_unified_engine_assigns_canonical_categories_for_structured_payload():
    payload = {
        "company": "ACME Corp",
        "facts": [
            {"entity": "ACME Corp", "metric": "price", "period": "2024-12-31", "unit": "currency", "value": "54", "source": "finnhub_quote"},
            {"entity": "FEDFUNDS", "metric": "interest rate", "period": "2024-12-31", "unit": "percent", "value": "5.33", "source": "fred_series"},
            {"entity": "ACME Corp", "metric": "revenue", "period": "2024Q4", "unit": "currency", "value": "140", "source": "sec_ixbrl"},
            {"entity": "ACME Corp", "metric": "event_earnings", "period": "2024-11-01", "unit": "event", "value": "earnings beat", "source": "event_timeline"},
            {"entity": "ACME Corp", "metric": "sentiment", "period": "2024-11-30", "unit": "ratio", "value": "0.72", "source": "news"},
            {"entity": "ACME Corp", "metric": "short interest", "period": "2024-11-30", "unit": "ratio", "value": "0.08", "source": "broker"},
        ],
        "metadata": {"source": "partner"},
    }

    result = await convert_partner_payload(payload=payload, source="partner")
    facts = result.unified.distill.facts or []
    cats = {f.get("category") for f in facts if isinstance(f, dict)}
    # Expect at least one from each major bucket to be recognized.
    assert "market" in cats
    assert "macro" in cats
    assert "fundamentals" in cats
    assert "event" in cats
    assert "alternative" in cats
    assert "ownership" in cats
