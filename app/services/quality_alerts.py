from __future__ import annotations

import os
from typing import Any, Dict

from app.services.audit_logger import AuditLogger, AuditEntry


def maybe_alert_quality_regression(payload: Dict[str, Any], *, db: Any) -> None:
    """
    Emit an audit alert when quality gate indicates regression.
    Thresholds are environment-configurable and conservative by default.
    """
    try:
        needs_review = bool(payload.get("needs_review"))
        gate = payload.get("quality_gate") or {}
        if not needs_review:
            return

        missing_unit = int(gate.get("missing_unit_count", 0) or 0)
        missing_period = int(gate.get("missing_period_count", 0) or 0)
        missing_evidence = int(gate.get("missing_evidence_count", 0) or 0)
        missing_currency = int(gate.get("missing_currency_count", 0) or 0)

        thresh_unit = int(os.getenv("QUALITY_ALERT_MISSING_UNIT", "1"))
        thresh_period = int(os.getenv("QUALITY_ALERT_MISSING_PERIOD", "1"))
        thresh_evidence = int(os.getenv("QUALITY_ALERT_MISSING_EVIDENCE", "1"))
        thresh_currency = int(os.getenv("QUALITY_ALERT_MISSING_CURRENCY", "1"))

        should_alert = (
            missing_unit >= thresh_unit
            or missing_period >= thresh_period
            or missing_evidence >= thresh_evidence
            or missing_currency >= thresh_currency
        )
        if not should_alert:
            return

        logger = AuditLogger(db)
        logger.append_log(
            AuditEntry(
                action="quality_alert",
                actor_type="system",
                actor_id=None,
                entity_type="raw_document",
                entity_id=str(payload.get("doc_id") or "unknown"),
                context={
                    "tenant_id": payload.get("tenant_id"),
                    "gate": gate,
                },
                outcome={"alert": True},
            )
        )
    except Exception:
        return
