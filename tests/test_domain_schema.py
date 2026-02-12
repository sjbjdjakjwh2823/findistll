from app.services.domain_schema import normalize_partner_payload


def test_domain_schema_normalizes_period_and_evidence():
    payload = {
        "company": "ExampleCo",
        "facts": [
            {"metric": "close_price", "value": "101.5", "period": "2025/02/10"},
        ],
        "metadata": {"source": "partner_api"},
    }
    out, quality = normalize_partner_payload(payload, category="market", partner_id="acme")
    fact = out["facts"][0]
    assert fact.get("period_norm") == "2025-02-10"
    assert fact.get("evidence")
    assert fact["evidence"].get("snippet")
    assert quality.needs_review is True


def test_domain_schema_supports_quarter_periods():
    payload = {
        "company": "ExampleCo",
        "facts": [
            {"metric": "Revenue", "value": "1000000", "period": "2024Q4", "unit": "USD"},
        ],
        "metadata": {"source": "partner_api"},
    }
    out, _quality = normalize_partner_payload(payload, category="fundamentals", partner_id="acme")
    fact = out["facts"][0]
    assert fact.get("period_norm") == "2024-12-31"
