from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.core.config import load_settings
from app.services.anonymizer import scan_sensitive


@dataclass
class PolicyDecision:
    action: str
    reason: str
    sensitive_hits: Dict[str, int]
    requires_approval: bool = False


class PolicyEngine:
    def __init__(self) -> None:
        self.settings = load_settings()

    def check_egress(
        self,
        payload: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        destination: str = "external_api",
    ) -> PolicyDecision:
        metadata = metadata or {}
        hits = scan_sensitive(payload or "")
        has_sensitive = any(v > 0 for v in hits.values()) or bool(metadata.get("sensitive"))

        if self.settings.egress_approval_required == "1" or metadata.get("requires_approval"):
            return PolicyDecision(
                action="block",
                reason="approval_required",
                sensitive_hits=hits,
                requires_approval=True,
            )

        mode = (self.settings.egress_mode or "allow").lower()
        if mode == "block":
            return PolicyDecision(
                action="block",
                reason=f"egress_blocked:{destination}",
                sensitive_hits=hits,
            )

        if has_sensitive and self.settings.egress_sensitive_block == "1":
            return PolicyDecision(
                action="block",
                reason="sensitive_payload_blocked",
                sensitive_hits=hits,
            )

        if mode == "anonymize" or (has_sensitive and self.settings.egress_sensitive_block != "1"):
            return PolicyDecision(
                action="anonymize",
                reason="anonymize_sensitive",
                sensitive_hits=hits,
            )

        return PolicyDecision(action="allow", reason="allow", sensitive_hits=hits)
