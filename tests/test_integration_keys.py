import pytest


def test_normalize_provider_aliases():
    from app.services.integration_keys import normalize_provider

    assert normalize_provider("sec-api") == "sec"
    assert normalize_provider("SEC_API") == "sec"
    assert normalize_provider("financialmodelingprep") == "fmp"
    assert normalize_provider("google") == "gemini"
    assert normalize_provider("finnhub") == "finnhub"


def test_encrypt_requires_master_key(monkeypatch):
    pytest.importorskip("cryptography")
    monkeypatch.delenv("INTEGRATION_KEYS_MASTER_KEY", raising=False)
    from app.services.secret_store import encrypt_secret

    with pytest.raises(RuntimeError):
        encrypt_secret("abc")

