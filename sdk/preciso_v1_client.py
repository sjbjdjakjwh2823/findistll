from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class PrecisoV1Client:
    """
    Minimal Python client for Preciso /api/v1 endpoints.

    Notes:
    - Partner ingest auth uses `X-Partner-Api-Key`.
    - Admin partner registration uses `X-Admin-Token` (recommended) and/or RBAC headers.
    """

    def __init__(
        self,
        *,
        base_url: str,
        partner_api_key: Optional[str] = None,
        admin_token: Optional[str] = None,
        rbac_user_id: str = "sdk",
        rbac_user_role: str = "admin",
        timeout_s: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.partner_api_key = partner_api_key
        self.admin_token = admin_token
        self.rbac_user_id = rbac_user_id
        self.rbac_user_role = rbac_user_role
        self.timeout_s = timeout_s

    def _headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json"}

    def _admin_headers(self) -> Dict[str, str]:
        h = self._headers()
        if self.admin_token:
            h["X-Admin-Token"] = self.admin_token
        # RBAC headers (optional; required if RBAC_ENFORCED=1)
        h["X-Preciso-User-Id"] = self.rbac_user_id
        h["X-Preciso-User-Role"] = self.rbac_user_role
        return h

    def _partner_headers(self) -> Dict[str, str]:
        h = self._headers()
        if self.partner_api_key:
            h["X-Partner-Api-Key"] = self.partner_api_key
        return h

    def public_config(self) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/config/public"
        r = requests.get(url, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

    # ---------------------------------------------------------------------
    # Admin: Partner registry
    # ---------------------------------------------------------------------
    def create_partner(self, *, partner_id: str, name: str, metadata: Optional[Dict[str, Any]] = None, key_label: str = "default") -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/admin/partners"
        payload = {"partner_id": partner_id, "name": name, "metadata": metadata or {}, "key_label": key_label}
        r = requests.post(url, json=payload, headers=self._admin_headers(), timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

    def issue_partner_key(self, *, partner_id: str, label: str = "rotation") -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/admin/partners/{partner_id}/keys"
        payload = {"label": label}
        r = requests.post(url, json=payload, headers=self._admin_headers(), timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

    # ---------------------------------------------------------------------
    # Partner: Ingest + docs
    # ---------------------------------------------------------------------
    def ingest_partner_financials(
        self,
        *,
        partner_id: str,
        payload: Dict[str, Any],
        source: str = "partner",
        document_type: str = "partner_financials",
        ticker: Optional[str] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/partners/financials"
        body: Dict[str, Any] = {
            "partner_id": partner_id,
            "payload": payload,
            "source": source,
            "document_type": document_type,
            "ticker": ticker,
        }
        r = requests.post(url, json=body, headers=self._partner_headers(), timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

    def list_partner_documents(self, *, partner_id: str, limit: int = 50) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/partners/documents"
        r = requests.get(url, params={"partner_id": partner_id, "limit": limit}, headers=self._partner_headers(), timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

