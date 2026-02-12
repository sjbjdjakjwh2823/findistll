import os

import pytest


def test_secret_store_encrypt_decrypt_roundtrip(monkeypatch):
    cryptography = pytest.importorskip("cryptography")
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("INTEGRATION_KEYS_MASTER_KEY", key)

    from app.services.secret_store import encrypt_secret, decrypt_secret

    plaintext = "sk_test_1234567890abcdef"
    c = encrypt_secret(plaintext)
    assert c.ciphertext and isinstance(c.ciphertext, str)
    assert c.hint.endswith(plaintext[-4:])
    assert decrypt_secret(c.ciphertext) == plaintext


def test_secret_store_disabled_without_env(monkeypatch):
    monkeypatch.delenv("INTEGRATION_KEYS_MASTER_KEY", raising=False)
    from app.services.secret_store import secret_store_enabled

    assert secret_store_enabled() is False

