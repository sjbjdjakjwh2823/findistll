from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


def _master_key() -> str:
    return (os.getenv("INTEGRATION_KEYS_MASTER_KEY") or "").strip()


@dataclass
class SecretCipher:
    ciphertext: str
    hint: str


def _require_cryptography():
    try:
        from cryptography.fernet import Fernet  # noqa: F401
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "cryptography is required for INTEGRATION_KEYS_MASTER_KEY secret storage. "
            "Install dependency 'cryptography' and set INTEGRATION_KEYS_MASTER_KEY."
        ) from e


def encrypt_secret(plaintext: str) -> SecretCipher:
    _require_cryptography()
    from cryptography.fernet import Fernet

    key = _master_key()
    if not key:
        raise RuntimeError("INTEGRATION_KEYS_MASTER_KEY is not set")

    f = Fernet(key.encode("utf-8"))
    token = f.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    hint = f"...{plaintext[-4:]}" if len(plaintext) >= 4 else "****"
    return SecretCipher(ciphertext=token, hint=hint)


def decrypt_secret(ciphertext: str) -> str:
    _require_cryptography()
    from cryptography.fernet import Fernet

    key = _master_key()
    if not key:
        raise RuntimeError("INTEGRATION_KEYS_MASTER_KEY is not set")
    f = Fernet(key.encode("utf-8"))
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def secret_store_enabled() -> bool:
    return bool(_master_key())


def try_decrypt(ciphertext: Optional[str]) -> Optional[str]:
    if not ciphertext:
        return None
    if not secret_store_enabled():
        return None
    try:
        return decrypt_secret(ciphertext)
    except Exception:
        return None

