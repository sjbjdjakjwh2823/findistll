import pytest


@pytest.mark.asyncio
async def test_convert_partner_payload_enriches_evidence_and_values():
    from app.services.partner_ingest import convert_partner_payload

    payload = {
        "title": "Partner Financials",
        "facts": [
            {
                "entity": "ACME",
                "metric": "Revenue",
                "period": "2024Q4",
                "value": "100000000",
                # evidence intentionally incomplete to trigger needs_review
                "evidence": {"method": "partner_api", "confidence": 0.9},
            }
        ],
        "metadata": {"company": "ACME", "fiscal_year": "2024"},
    }

    res = await convert_partner_payload(payload=payload, source="partner")
    assert res.distill_facts_count >= 1
    fact = res.unified.distill.facts[0]
    assert isinstance(fact, dict)
    assert "raw_value" in fact or "normalized_value" in fact
    assert "evidence" in fact
    assert fact.get("needs_review") is True


@pytest.mark.asyncio
async def test_convert_partner_payload_maps_events_to_facts():
    from app.services.partner_ingest import convert_partner_payload

    payload = {
        "events": [
            {
                "entity": "ACME",
                "event_type": "dividend",
                "announced_at": "2024-12-31",
                "payload": {"amount": "0.50", "currency": "USD"},
                "evidence": {"method": "partner_api", "confidence": 0.8},
            }
        ]
    }

    res = await convert_partner_payload(payload=payload, source="partner", partner_id="acme-inc")
    assert res.distill_facts_count >= 1
    fact = res.unified.distill.facts[0]
    assert fact.get("metric") == "event:dividend"
    assert "evidence" in fact
