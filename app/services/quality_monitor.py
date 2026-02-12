from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.services.audit_logger import AuditLogger, AuditEntry

logger = logging.getLogger(__name__)


def record_quality_gate(
    *,
    db: Any,
    doc_id: str,
    metadata: Optional[Dict[str, Any]],
    metrics: Optional[Dict[str, Any]],
    source: str,
) -> None:
    if not db or not doc_id:
        return
    gate = (metrics or {}).get("quality_gate") or {}
    needs_review = bool((metadata or {}).get("needs_review"))
    md = metadata or {}
    tenant_id = md.get("tenant_id") or md.get("tenant") or md.get("tenantId")
    payload = {
        "source": source,
        "doc_id": doc_id,
        "needs_review": needs_review,
        "quality_gate": gate,
        "metadata": md,
        "tenant_id": tenant_id,
    }
    try:
        logger = AuditLogger(db)
        logger.append_log(
            AuditEntry(
                action="quality_gate",
                actor_type="system",
                actor_id=None,
                entity_type="raw_document",
                entity_id=str(doc_id),
                context=payload,
                outcome={"ok": True},
            )
        )
        try:
            from app.services.metrics_logger import MetricsLogger
            MetricsLogger().log("quality_gate.needs_review", 1 if needs_review else 0, payload)
            MetricsLogger().log("quality_gate.missing_unit", int(gate.get("missing_unit_count", 0) or 0), payload)
            MetricsLogger().log("quality_gate.missing_period", int(gate.get("missing_period_count", 0) or 0), payload)
            MetricsLogger().log("quality_gate.missing_evidence", int(gate.get("missing_evidence_count", 0) or 0), payload)
            MetricsLogger().log("quality_gate.missing_currency", int(gate.get("missing_currency_count", 0) or 0), payload)
            MetricsLogger().log("quality_gate.total", 1, payload)
        except Exception as exc:
            logger.warning("quality gate metrics logging failed", exc_info=exc)

        try:
            from app.services.quality_alerts import maybe_alert_quality_regression
            maybe_alert_quality_regression(payload, db=db)
        except Exception as exc:
            logger.warning("quality regression alert failed", exc_info=exc)
    except Exception:
        # Do not block ingest on audit log failures.
        logger.warning("quality gate audit logging failed")
