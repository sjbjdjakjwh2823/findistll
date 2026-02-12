from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.services.selfcheck import SelfCheckService
from app.services.types import DecisionResult, DistillResult
from app.services.labeling_functions import LabelingFunctions
from app.services.snorkel_aggregator import SnorkelAggregator
from app.services.pws_metrics import compute_lf_metrics, compute_label_noise
from app.services.data_quality import compute_data_quality
from app.services.preciso_mathematics import PrecisoMathematicsService

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _extract_numbers(text: str) -> List[str]:
    if not text:
        return []
    # Keep as strings to avoid float rounding; normalize later.
    return re.findall(r"(?<![A-Za-z])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?", text)


def _norm_num_str(s: str) -> str:
    t = (s or "").strip()
    t = t.replace(",", "")
    # normalize percent: keep the number token only for matching
    t = t.replace("%", "")
    # strip leading + for matching
    t = t.lstrip("+")
    return t


def _numeric_preservation_ok(output_text: str, facts: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
    """
    Heuristic numeric preservation check:
    - Extract numeric tokens from output_text.
    - Compare against numeric-ish tokens in extracted facts.
    - If output contains numbers but almost none are found in facts, fail.

    This is intentionally conservative: it avoids silently admitting hallucinated numbers.
    """
    out_nums = [_norm_num_str(x) for x in _extract_numbers(output_text)]
    out_nums = [x for x in out_nums if x not in ("", "-", "+")]
    if not out_nums:
        return True, {"checked": True, "output_numbers": 0, "matched": 0, "ratio": 1.0}

    fact_tokens: List[str] = []
    for f in facts or []:
        if not isinstance(f, dict):
            continue
        for key in ("value", "amount", "number", "metric_value"):
            v = f.get(key)
            if v is None:
                continue
            fact_tokens.extend([_norm_num_str(x) for x in _extract_numbers(str(v))])
        # also include whole fact string as fallback
        fact_tokens.extend([_norm_num_str(x) for x in _extract_numbers(str(f))])
    fact_set = {x for x in fact_tokens if x}

    matched = sum(1 for x in out_nums if x in fact_set)
    ratio = matched / max(1, len(out_nums))
    ok = ratio >= 0.6  # baseline
    return ok, {
        "checked": True,
        "output_numbers": len(out_nums),
        "matched": matched,
        "ratio": round(ratio, 3),
    }


@dataclass
class SpokeAGates:
    selfcheck_ok: bool
    retrieval_ok: bool
    label_noise_ok: bool
    data_quality_ok: bool
    numeric_ok: bool
    status: str  # 'candidate'|'needs_review'|'rejected'
    details: Dict[str, Any]


class SpokeABService:
    """
    WS8 implementation service:
    - Create Spoke A JSONL records on approval events.
    - Create Spoke B Parquet artifacts (facts/tables/features) for downstream use.

    Storage strategy (MVP):
    - Spoke A: store JSON object + JSONL line in DB (spoke_a_samples)
    - Spoke B: store Parquet bytes as base64 in DB (spoke_b_artifacts)
      This is intentionally simple; storage can be moved to object storage later.
    """

    def __init__(self) -> None:
        self._selfcheck = SelfCheckService()

    def build_spoke_a_record(
        self,
        *,
        tenant_id: str,
        doc_id: str,
        case_id: str,
        version: str,
        instruction: str,
        input_text: str,
        output_text: str,
        evidence_chunk_ids: List[str],
        fact_refs: List[Dict[str, Any]],
        selfcheck: Dict[str, Any],
        approval: Dict[str, Any],
    ) -> Dict[str, Any]:
        chunk_hash = _stable_hash({"instruction": instruction, "input": input_text, "output": output_text})
        record_id = f"{tenant_id}:{doc_id}:{case_id}:{version}:{chunk_hash}"
        return {
            "id": record_id,
            "instruction": instruction,
            "input": input_text,
            "output": output_text,
            "metadata": {
                "tenant_id": tenant_id,
                "doc_id": doc_id,
                "case_id": case_id,
                "source": approval.get("source") or "preciso",
                "timestamp": approval.get("approved_at") or _utc_now_iso(),
                "evidence_chunk_ids": evidence_chunk_ids,
                "fact_refs": fact_refs,
                "selfcheck": selfcheck,
                "approval": approval,
            },
            "schema_version": "1.0",
        }

    def evaluate_gates(
        self,
        *,
        spoke_a_record: Dict[str, Any],
        distill: DistillResult,
        min_selfcheck: float = 0.70,
        min_evidence: int = 2,
        max_label_noise: float = 0.35,
        min_data_quality: float = 0.70,
    ) -> SpokeAGates:
        evidence = (spoke_a_record.get("metadata") or {}).get("evidence_chunk_ids") or []
        retrieval_ok = len(evidence) >= min_evidence

        sc_score = float(((spoke_a_record.get("metadata") or {}).get("selfcheck") or {}).get("confidence_score") or 0.0)
        selfcheck_ok = sc_score >= min_selfcheck

        # Weak supervision metrics via simple LFs (regex/layout/keyword).
        lf = LabelingFunctions()
        doc_text = (distill.cot_markdown or "")[:10000]
        fields = ["revenue", "profit", "net_income", "assets", "liabilities"]
        lf_results = []
        for f in fields:
            lf_results.append(lf.lf_regex(doc_text, f))
            lf_results.append(lf.lf_keyword(doc_text, f))
        metrics = compute_lf_metrics(lf_results)
        noise = compute_label_noise(metrics)
        label_noise_ok = noise <= max_label_noise

        # Aggregate confidence is taken from selfcheck for MVP.
        dq = compute_data_quality(metrics, aggregated_confidence=sc_score)
        data_quality_ok = dq >= min_data_quality

        numeric_ok, numeric_detail = _numeric_preservation_ok(spoke_a_record.get("output") or "", distill.facts or [])

        details = {
            "selfcheck": {"score": sc_score, "min": min_selfcheck},
            "retrieval": {"evidence_count": len(evidence), "min": min_evidence},
            "weak_supervision": {"lf_metrics": metrics, "label_noise": noise, "max_noise": max_label_noise},
            "data_quality": {"score": dq, "min": min_data_quality},
            "numeric_preservation": numeric_detail,
        }

        status = "candidate"
        if not (selfcheck_ok and retrieval_ok and label_noise_ok and data_quality_ok and numeric_ok):
            status = "needs_review"
        return SpokeAGates(
            selfcheck_ok=selfcheck_ok,
            retrieval_ok=retrieval_ok,
            label_noise_ok=label_noise_ok,
            data_quality_ok=data_quality_ok,
            numeric_ok=numeric_ok,
            status=status,
            details=details,
        )

    def compute_selfcheck(
        self,
        *,
        decision: DecisionResult,
        distill: DistillResult,
    ) -> Dict[str, Any]:
        try:
            return self._selfcheck.evaluate(decision, distill)
        except Exception as exc:
            return {"error": str(exc), "confidence_score": 0.0, "consistency_score": 0.0}

    def build_fact_refs(self, distill: DistillResult, limit: int = 50) -> List[Dict[str, Any]]:
        refs: List[Dict[str, Any]] = []
        for fact in distill.facts or []:
            if not isinstance(fact, dict):
                continue
            entity = fact.get("entity") or fact.get("company") or fact.get("issuer") or fact.get("ticker")
            metric = fact.get("metric") or fact.get("label") or fact.get("concept")
            period_norm = fact.get("period_norm") or fact.get("period")
            value = None
            for k in ("value", "amount", "number", "metric_value"):
                if fact.get(k) is not None:
                    value = fact.get(k)
                    break
            if entity and metric and period_norm and value is not None:
                refs.append({"entity": entity, "metric": metric, "period_norm": period_norm})
            if len(refs) >= limit:
                break
        return refs

    def build_math_summary(self, distill: DistillResult, max_series: int = 8) -> str:
        """
        Human/LLM-friendly summary of Preciso Mathematics derived features.
        Used to enrich Spoke A input so training data reflects your formulas.
        """
        try:
            analysis = PrecisoMathematicsService().analyze(distill.facts or [])
            derived = analysis.derived or {}
            if not derived:
                return ""
            lines: List[str] = ["Preciso Mathematics (Derived)"]
            for key in sorted(list(derived.keys()))[: max_series]:
                payload = derived.get(key) or {}
                try:
                    entity, metric = key.split("::", 1)
                except ValueError:
                    entity, metric = "Unknown", key
                periods = payload.get("periods") or []
                values = payload.get("values") or []
                pct = payload.get("pct_change") or []
                z = payload.get("zscore") or []
                if not periods or not values:
                    continue
                latest_period = periods[-1]
                latest_value = values[-1]
                latest_pct = pct[-1] if pct else None
                latest_z = z[-1] if z else None
                lines.append(f"- {entity} | {metric} @ {latest_period}: value={latest_value}, pct_change={latest_pct}, zscore={latest_z}")
            return "\n".join(lines).strip()
        except Exception:
            return ""

    def build_spoke_b_parquets(
        self,
        *,
        tenant_id: str,
        doc_id: str,
        distill: DistillResult,
        normalized: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, bytes]:
        """
        Return Parquet bytes for:
        - facts
        - tables
        - features (Preciso Mathematics derived)
        """
        import polars as pl
        import io

        extracted_at = _utc_now_iso()
        facts_rows = []
        for fact in distill.facts or []:
            if not isinstance(fact, dict):
                continue
            facts_rows.append(
                {
                    "tenant_id": tenant_id,
                    "doc_id": doc_id,
                    "entity": fact.get("entity"),
                    "metric": fact.get("metric") or fact.get("label") or fact.get("concept"),
                    "period": fact.get("period"),
                    "period_norm": fact.get("period_norm"),
                    "value": (
                        fact.get("normalized_value")
                        if fact.get("normalized_value") is not None
                        else (fact.get("value") if fact.get("value") is not None else fact.get("amount"))
                    ),
                    "unit": fact.get("unit"),
                    "currency": fact.get("currency"),
                    "source": fact.get("source"),
                    "confidence": fact.get("confidence"),
                    "dimensions": fact.get("dimensions"),
                    "extracted_at": extracted_at,
                }
            )
        df_facts = pl.DataFrame(facts_rows) if facts_rows else pl.DataFrame(
            {"tenant_id": [tenant_id], "doc_id": [doc_id], "extracted_at": [extracted_at]}
        )

        table_rows = []
        for t in (normalized or {}).get("tables", []) or []:
            tname = t.get("name") or "table"
            page = None
            try:
                import re
                m = re.search(r"\bp(\d+)\b", str(tname), re.IGNORECASE)
                if m:
                    page = m.group(1)
            except Exception:
                page = None
            headers = t.get("headers") or []
            for r_idx, row in enumerate(t.get("rows") or []):
                for c_idx, header in enumerate(headers):
                    table_rows.append(
                        {
                            "tenant_id": tenant_id,
                            "doc_id": doc_id,
                            "table_name": tname,
                            "page": page,
                            "section": None,
                            "row_idx": r_idx,
                            "col_idx": c_idx,
                            "col_name": str(header),
                            "col_value": str(row[c_idx]) if c_idx < len(row) else "",
                            "extracted_at": extracted_at,
                        }
                    )
        df_tables = pl.DataFrame(table_rows) if table_rows else pl.DataFrame(
            {"tenant_id": [tenant_id], "doc_id": [doc_id], "extracted_at": [extracted_at]}
        )

        # Features: derived series
        math_analysis = PrecisoMathematicsService().analyze(distill.facts or [])
        features_rows = []
        for key, payload in (math_analysis.derived or {}).items():
            # key: "{entity}::{metric}"
            try:
                entity, metric = key.split("::", 1)
            except ValueError:
                entity, metric = "Unknown", key
            periods = payload.get("periods") or []
            values = payload.get("values") or []
            pct = payload.get("pct_change") or []
            logret = payload.get("log_returns") or []
            z = payload.get("zscore") or []
            for idx, period_norm in enumerate(periods):
                features_rows.append(
                    {
                        "tenant_id": tenant_id,
                        "entity": entity,
                        "metric": metric,
                        "period_norm": period_norm,
                        "value": values[idx] if idx < len(values) else None,
                        "pct_change": pct[idx] if idx < len(pct) else None,
                        "log_return": logret[idx] if idx < len(logret) else None,
                        "zscore": z[idx] if idx < len(z) else None,
                        "computed_at": extracted_at,
                    }
                )
        df_features = pl.DataFrame(features_rows) if features_rows else pl.DataFrame(
            {"tenant_id": [tenant_id], "computed_at": [extracted_at]}
        )

        def to_parquet_bytes(df: pl.DataFrame) -> bytes:
            buf = io.BytesIO()
            df.write_parquet(buf, compression="snappy")
            return buf.getvalue()

        return {
            "facts": to_parquet_bytes(df_facts),
            "tables": to_parquet_bytes(df_tables),
            "features": to_parquet_bytes(df_features),
        }

    def save_spoke_b_artifacts(
        self,
        *,
        db: Any,
        doc_id: str,
        artifacts: Dict[str, bytes],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        ids: Dict[str, str] = {}
        for kind, content in artifacts.items():
            ids[kind] = db.insert_spoke_b_artifact(
                {
                    "doc_id": doc_id,
                    "kind": kind,
                    "content_base64": base64.b64encode(content).decode("ascii"),
                    "metadata": metadata or {},
                }
            )
        return ids
