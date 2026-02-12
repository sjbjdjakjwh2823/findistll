import pytest


@pytest.mark.asyncio
async def test_market_data_fetch_fred_series_normalizes_with_series_id(monkeypatch):
    from app.services.market_data import MarketDataService

    svc = MarketDataService()

    async def fake_fetch_json(url, params):
        # Emulate FRED observations response
        return {
            "observations": [
                {"date": "2024-12-31", "value": "5.25"},
                {"date": "2024-12-30", "value": "."},  # missing
            ]
        }

    monkeypatch.setattr(svc, "_fetch_json", fake_fetch_json)

    obs = await svc.fetch_fred_series("FEDFUNDS", limit=2, api_key_override="dummy")
    assert len(obs) == 2

    payload = [{**o, "series_id": "FEDFUNDS"} for o in obs]
    normalized = svc.normalize_market_snapshot(payload, "fred_series", symbol="FEDFUNDS")
    facts = normalized.get("facts") or []
    assert len(facts) == 1
    assert facts[0]["entity"] == "FEDFUNDS"
    assert facts[0]["metric"] == "FEDFUNDS"
    assert facts[0]["normalized_value"] == "5.25"


@pytest.mark.asyncio
async def test_market_data_get_key_rates_uses_fetch(monkeypatch):
    from app.services.market_data import MarketDataService

    svc = MarketDataService()

    async def fake_fetch_fred_series(series_id, limit=1, api_key_override=None, db=None):
        return [{"date": "2024-12-31", "value": "1.00"}]

    monkeypatch.setattr(svc, "fetch_fred_series", fake_fetch_fred_series)
    rates = await svc.get_key_rates(api_key_override="dummy")
    assert set(rates.keys()) == {"fed_funds", "treasury_10y", "yield_curve"}
    assert rates["fed_funds"]["series_id"] == "FEDFUNDS"

