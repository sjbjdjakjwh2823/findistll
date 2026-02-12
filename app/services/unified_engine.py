from __future__ import annotations

import os
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
from decimal import Decimal, InvalidOperation

from app.services.types import DistillResult, DecisionResult
from app.services.spokes import build_rag_context, extract_graph_triples, build_training_set
from app.services.preciso_mathematics import PrecisoMathematicsService
from app.services.labeling_functions import LabelingFunctions
from app.services.snorkel_aggregator import SnorkelAggregator
from app.services.pws_metrics import compute_lf_metrics, compute_label_noise
from app.services.data_quality import compute_data_quality

logger = logging.getLogger(__name__)


@dataclass
class UnifiedConversionResult:
    extracted: Dict[str, Any] = field(default_factory=dict)
    normalized: Dict[str, Any] = field(default_factory=dict)
    distill: DistillResult = field(default_factory=DistillResult)
    exports: Dict[str, Any] = field(default_factory=dict)
    spokes: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    mathematics: Dict[str, Any] = field(default_factory=dict)


class UnifiedConversionEngine:
    """
    Unified financial document conversion engine.

    This consolidates all existing conversion logic (ingestion, normalization,
    export formatting, and Spoke outputs) into one orchestrated pipeline.
    """

    async def convert_document(
        self,
        *,
        file_bytes: Optional[bytes] = None,
        filename: str = "document",
        mime_type: str = "text/plain",
        source: str = "upload",
        document: Optional[Dict[str, Any]] = None,
        decision: Optional[DecisionResult] = None,
        run_snorkel: bool = True,
    ) -> UnifiedConversionResult:
        if file_bytes is None and document and document.get("file_bytes"):
            file_bytes = document.get("file_bytes")
        if file_bytes is None and document and document.get("content_base64"):
            import base64
            file_bytes = base64.b64decode(document["content_base64"])
        if file_bytes is None and document and document.get("content"):
            content = document.get("content")
            if isinstance(content, (bytes, bytearray)):
                file_bytes = bytes(content)
            elif isinstance(content, str):
                file_bytes = content.encode("utf-8")

        result = UnifiedConversionResult()

        if file_bytes is None and document:
            # Structured JSON content path (e.g., FRED/SEC/FMP payloads)
            structured = self._process_structured_payload(document, source)
            # Ensure structured facts comply with Preciso fact schema invariants.
            if isinstance(structured, dict) and isinstance(structured.get("facts"), list):
                meta = structured.get("metadata", {})
                if not isinstance(meta, dict):
                    meta = {"source": source}
                meta.setdefault("source", source)
                structured["metadata"] = meta
                structured["facts"] = self._enrich_facts(
                    structured.get("facts") or [],
                    meta,
                    structured,
                    structured,
                )
            result.extracted = structured
            result.normalized = structured
            result.distill = DistillResult(
                facts=structured.get("facts", []),
                cot_markdown=structured.get("cot_markdown", ""),
                metadata=structured.get("metadata", {}),
            )
            try:
                if isinstance(result.distill.metadata, dict):
                    if not result.distill.metadata.get("document_date") and not result.distill.metadata.get("as_of"):
                        inferred = self._infer_document_date_from_facts(result.distill.facts or [])
                        if inferred:
                            result.distill.metadata["document_date"] = inferred
                            result.distill.metadata.setdefault("as_of", inferred)
            except Exception as exc:
                logger.warning("swallowed exception", exc_info=exc)
            self._apply_quality_gate(result.distill)
            result.metrics = self._build_quality_metrics(result.distill, structured)
            result.exports = self._build_exports(structured, result.distill)
            result.spokes = self._build_spokes(result.distill, decision)
            result.mathematics = self._build_mathematics(result.distill)
            return result

        if file_bytes is None:
            result.distill = DistillResult(
                facts=[],
                cot_markdown="",
                metadata={"error": "no content"},
            )
            return result

        # Content-based MIME sniffing: callers often supply incorrect extensions/MIME.
        # This is critical for reliability (e.g., HTML saved as .pdf).
        mime_type = self._sniff_mime(file_bytes, filename, mime_type)

        extracted = await self._run_ingestion(file_bytes, filename, mime_type)
        result.extracted = extracted

        normalized = self._run_normalizer(extracted)
        result.normalized = normalized

        facts = normalized.get("facts") or extracted.get("facts") or []
        cot_markdown = self._build_cot(normalized)
        metadata = dict(normalized.get("metadata", {}))
        metadata.setdefault("source", source)
        metadata.setdefault("filename", filename)
        metadata.setdefault("title", normalized.get("title") or extracted.get("title") or filename)

        distill = DistillResult(
            facts=facts,
            cot_markdown=cot_markdown,
            metadata=metadata,
        )
        distill.facts = self._enrich_facts(distill.facts, distill.metadata, normalized, extracted)
        self._apply_quality_gate(distill)
        # Date-awareness hardening:
        # If document_date/as_of is missing, infer from normalized periods (period_norm) deterministically.
        try:
            if isinstance(distill.metadata, dict):
                if not distill.metadata.get("document_date") and not distill.metadata.get("as_of"):
                    inferred = self._infer_document_date_from_facts(distill.facts or [])
                    if inferred:
                        distill.metadata["document_date"] = inferred
                        distill.metadata.setdefault("as_of", inferred)
        except Exception as exc:
            logger.warning("swallowed exception", exc_info=exc)

        if run_snorkel and os.getenv("SNORKEL_ENABLED", "0") == "1":
            snorkel_payload = await self._run_snorkel(distill, normalized)
            if snorkel_payload.get("facts"):
                distill.facts = distill.facts + snorkel_payload["facts"]
            distill.metadata["snorkel"] = snorkel_payload

        result.distill = distill
        result.metrics = self._build_quality_metrics(distill, normalized)

        # Perfectness hardening: if table-cell validation shows a scale mismatch pattern,
        # attempt a deterministic correction before returning artifacts.
        if mime_type == "application/pdf":
            try:
                cv = (result.metrics or {}).get("cell_validation") or {}
                applied = self._attempt_scale_correction(distill, normalized, cv)
                if applied:
                    distill.metadata.setdefault("quality_fixes", [])
                    distill.metadata["quality_fixes"].append(applied)
                    result.metrics = self._build_quality_metrics(distill, normalized)
            except Exception as exc:
                logger.warning("swallowed exception", exc_info=exc)
        result.exports = self._build_exports(normalized, distill)
        result.spokes = self._build_spokes(distill, decision)
        result.mathematics = self._build_mathematics(distill)

        return result

    def _infer_document_date_from_facts(self, facts: List[Dict[str, Any]]) -> Optional[str]:
        import re
        dates: List[str] = []
        for f in facts or []:
            if not isinstance(f, dict):
                continue
            p = f.get("period_norm") or f.get("period") or f.get("date") or f.get("as_of")
            if not p:
                continue
            m = re.match(r"^(\d{4}-\d{2}-\d{2})", str(p).strip())
            if m:
                dates.append(m.group(1))
        if not dates:
            return None
        dates.sort()
        return dates[-1]

    def _sniff_mime(self, file_bytes: bytes, filename: str, mime_type: str) -> str:
        head = file_bytes[:4096]
        lowered = head.lstrip().lower()

        # PDF magic
        if head.startswith(b"%PDF-"):
            return "application/pdf"

        # ZIP container (xlsx/docx/etc)
        if head.startswith(b"PK\x03\x04"):
            name = filename.lower()
            if name.endswith(".xlsx") or name.endswith(".xls"):
                return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if name.endswith(".docx"):
                return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            return mime_type

        # HTML (including "fake pdf" files that are actually HTML)
        if lowered.startswith(b"<!doctype html") or b"<html" in lowered[:512]:
            return "text/html"

        # XML/XBRL
        if lowered.startswith(b"<?xml") or b"<xbrl" in lowered[:512]:
            return "application/xml"

        # JSON
        if lowered.startswith(b"{") or lowered.startswith(b"["):
            try:
                import json
                json.loads(head.decode("utf-8"))
                return "application/json"
            except Exception as exc:
                logger.warning("swallowed exception", exc_info=exc)

        return mime_type

    def _enrich_facts(
        self,
        facts: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        normalized: Dict[str, Any],
        extracted: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not facts:
            # Never silently drop: mark metadata for HITL review.
            metadata.setdefault("needs_review", True)
            metadata.setdefault("fact_extraction", {"status": "empty", "reason": "no_facts_extracted"})
            return []
        entity = (
            metadata.get("company")
            or metadata.get("entity")
            or normalized.get("title")
            or extracted.get("title")
            or metadata.get("title")
            or metadata.get("filename")
            or "Unknown"
        )
        doc_period = metadata.get("period") or metadata.get("fiscal_period") or metadata.get("as_of")
        doc_year = metadata.get("fiscal_year")
        if not doc_year:
            import re
            title = metadata.get("title") or normalized.get("title") or extracted.get("title") or ""
            years = re.findall(r"20\\d{2}", str(title))
            if years:
                doc_year = years[0]

        enriched: List[Dict[str, Any]] = []
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            payload = dict(fact)
            payload.setdefault("entity", entity)
            payload.setdefault("metric", payload.get("label") or payload.get("concept"))
            if "period" not in payload and payload.get("fiscal_period"):
                payload["period"] = payload.get("fiscal_period")
            if "period" not in payload and doc_period:
                payload["period"] = doc_period
            # Add normalized period for downstream time-series use.
            if "period" in payload and "period_norm" not in payload:
                payload["period_norm"] = self._normalize_period(payload.get("period"), doc_year)
            if "source" not in payload:
                payload["source"] = metadata.get("file_type") or metadata.get("source") or "distill"
            # Financial data engineering requirements:
            # - Use Decimal for numeric normalization
            # - Keep raw_value and normalized_value separate
            # - Attach evidence fields (document/page/section/snippet/method/confidence)
            payload = self._standardize_fact(payload, metadata)
            enriched.append(payload)
        return enriched

    def _standardize_fact(self, fact: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enforce a stable fact schema for downstream Spokes/QA.
        Keeps original fields intact and adds:
        - raw_value, normalized_value (string, Decimal-based)
        - unit, currency (if missing)
        - evidence with document_id/page/section/snippet/method/confidence
        - needs_review flag when evidence is missing or low confidence
        """
        payload = dict(fact)

        def _to_decimal_str(value: Any) -> Optional[str]:
            if value is None:
                return None
            if isinstance(value, Decimal):
                return format(value, "f")
            if isinstance(value, (int, float)):
                return format(Decimal(str(value)), "f")
            if isinstance(value, str):
                cleaned = value.replace(",", "").strip()
                if cleaned == "":
                    return None
                # Remove currency symbols while keeping numeric content
                cleaned = re.sub(r"[$€¥₩]", "", cleaned)
                cleaned = cleaned.replace("USD", "").replace("EUR", "").replace("JPY", "").strip()
                cleaned = cleaned.replace("%", "")
                try:
                    return format(Decimal(cleaned), "f")
                except InvalidOperation:
                    return None
            return None

        raw_value = payload.get("raw_value")
        if raw_value is None:
            raw_value = payload.get("value") or payload.get("amount") or payload.get("number") or payload.get("metric_value")
        normalized_value = payload.get("normalized_value")
        if normalized_value is None:
            normalized_value = payload.get("value") or payload.get("amount") or payload.get("number") or payload.get("metric_value")

        raw_value_str = _to_decimal_str(raw_value)
        normalized_value_str = _to_decimal_str(normalized_value)

        if raw_value_str is not None:
            payload["raw_value"] = raw_value_str
        if normalized_value_str is not None:
            payload["normalized_value"] = normalized_value_str
            # Keep backward compatibility: if "value" is missing, set it to normalized_value.
            if "value" not in payload:
                payload["value"] = normalized_value_str

        payload.setdefault("unit", payload.get("unit"))
        payload.setdefault("currency", payload.get("currency"))
        if not payload.get("currency") and (payload.get("unit") or "") == "currency":
            dims = payload.get("dimensions")
            if isinstance(dims, dict) and dims.get("currency"):
                payload["currency"] = str(dims.get("currency"))
            else:
                # Defaulting is safer than nulls for downstream quant/RAG, but keep it explicit.
                payload["currency"] = os.getenv("DEFAULT_CURRENCY", "USD")
                tags = payload.get("tags")
                if isinstance(tags, list):
                    tags.append("currency_defaulted")
                else:
                    payload["tags"] = ["currency_defaulted"]

        evidence = payload.get("evidence") or {}
        # Prefer stable internal document id; fall back to filename for auditability in offline runs.
        document_id = (
            evidence.get("document_id")
            or metadata.get("doc_id")
            or metadata.get("document_id")
            or metadata.get("filename")
        )
        # evidence.method should reflect extraction path (xbrl/ixbrl/pdf_ocr/html_tables/etc),
        # not the ingestion source (upload/api/etc).
        method = (
            evidence.get("method")
            or payload.get("source")
            or metadata.get("file_type")
            or metadata.get("processed_by")
            or "unknown"
        )
        confidence = (
            evidence.get("confidence")
            or payload.get("confidence")
            or payload.get("confidence_score")
            or payload.get("conf")
        )
        snippet = evidence.get("snippet") or payload.get("snippet") or payload.get("text")
        if not snippet:
            # Stable evidence fallback for structured sources (XBRL/iXBRL): preserve at least
            # concept/context/unit/raw_value for auditability.
            concept = payload.get("concept") or payload.get("metric") or payload.get("label")
            raw = payload.get("raw_value") if "raw_value" in payload else payload.get("value")
            ctx = payload.get("context_ref") or payload.get("contextRef")
            unit = payload.get("unit") or payload.get("unit_ref") or payload.get("unitRef")
            if concept and raw is not None:
                snippet = f"{concept}={raw}"
                if ctx:
                    snippet += f" ctx={ctx}"
                if unit:
                    snippet += f" unit={unit}"

        evidence_payload = {
            "document_id": document_id,
            "page": evidence.get("page") or payload.get("page"),
            "section": evidence.get("section") or payload.get("section"),
            "snippet": snippet,
            "method": method,
            "confidence": confidence,
        }
        payload["evidence"] = evidence_payload

        needs_review = payload.get("needs_review", False)
        if not document_id or not snippet:
            needs_review = True
        try:
            if confidence is not None and float(confidence) < 0.5:
                needs_review = True
        except Exception as exc:
            logger.warning("swallowed exception", exc_info=exc)
        payload["needs_review"] = needs_review

        # Canonical categorization (non-destructive)
        try:
            from app.services.canonical_facts import apply_canonical_fields
            payload = apply_canonical_fields(payload)
        except Exception as exc:
            logger.warning("swallowed exception", exc_info=exc)

        # Backward/forward compatibility:
        # - Some pipelines use "concept" (SEC/XBRL style), others use "metric".
        # Keep both aligned so AI Brain (oracle/causal) and Spokes operate consistently.
        if "concept" not in payload and payload.get("metric"):
            payload["concept"] = payload.get("metric")
        return payload

    def _normalize_period(self, period: Optional[str], doc_year: Optional[str]) -> Optional[str]:
        if not period:
            return None
        text = str(period).strip()
        if not text:
            return None

        # Unwrap PY_ prefix.
        if text.startswith("PY_"):
            text = text.split("_", 1)[1].strip()

        # Normalize separators.
        text = text.replace("/", "-").replace(".", "-")

        # ISO date already.
        if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            return text

        # CY/PY to year-end date.
        if text in ("CY", "PY") and doc_year:
            try:
                year = int(doc_year)
                if text == "PY":
                    year -= 1
                return f"{year}-12-31"
            except Exception:
                return None

        # Year only -> year-end.
        if re.match(r"^\d{4}$", text):
            return f"{text}-12-31"

        # Quarter patterns.
        q_match = re.match(r"^(\\d{4})\\s*[-_]?Q([1-4])$", text, re.IGNORECASE)
        if not q_match:
            q_match = re.match(r"^Q([1-4])\\s*(\\d{4})$", text, re.IGNORECASE)
            if q_match:
                q_match = (q_match.group(2), q_match.group(1))
        if q_match:
            if isinstance(q_match, tuple):
                year, q = q_match
            else:
                year, q = q_match.group(1), q_match.group(2)
            q = int(q)
            month = {1: 3, 2: 6, 3: 9, 4: 12}[q]
            day = {3: 31, 6: 30, 9: 30, 12: 31}[month]
            return f"{year}-{month:02d}-{day:02d}"

        # Half-year patterns.
        h_match = re.match(r"^(\\d{4})\\s*[-_]?H([12])$", text, re.IGNORECASE)
        if not h_match:
            h_match = re.match(r"^H([12])\\s*(\\d{4})$", text, re.IGNORECASE)
            if h_match:
                h_match = (h_match.group(2), h_match.group(1))
        if h_match:
            if isinstance(h_match, tuple):
                year, h = h_match
            else:
                year, h = h_match.group(1), h_match.group(2)
            h = int(h)
            return f"{year}-06-30" if h == 1 else f"{year}-12-31"

        # Year-month -> end of month.
        m_match = re.match(r"^(\\d{4})-(\\d{1,2})$", text)
        if m_match:
            year = int(m_match.group(1))
            month = int(m_match.group(2))
            try:
                import calendar
                day = calendar.monthrange(year, month)[1]
                return f"{year}-{month:02d}-{day:02d}"
            except Exception as exc:
                logger.warning("swallowed exception", exc_info=exc)

        return text

    def _apply_quality_gate(self, distill: DistillResult) -> None:
        meta = distill.metadata if isinstance(distill.metadata, dict) else {}
        needs_review = bool(meta.get("needs_review"))
        reasons: List[str] = list(meta.get("quality_reasons") or [])
        for f in distill.facts or []:
            if not isinstance(f, dict):
                continue
            evidence = f.get("evidence") or {}
            if not f.get("period_norm") and not f.get("period"):
                needs_review = True
                reasons.append("missing_period_norm")
            if not f.get("unit"):
                needs_review = True
                reasons.append("missing_unit")
            # Currency is required when values are monetary.
            unit = f.get("unit")
            if unit in ("USD", "KRW", "EUR", "JPY", "currency") and not f.get("currency"):
                needs_review = True
                reasons.append("missing_currency")
            if not evidence or not evidence.get("snippet"):
                needs_review = True
                reasons.append("missing_evidence_snippet")
        if needs_review:
            meta["needs_review"] = True
        if reasons:
            meta["quality_reasons"] = sorted(set(reasons))
        distill.metadata = meta

    async def _run_ingestion(self, file_bytes: bytes, filename: str, mime_type: str) -> Dict[str, Any]:
        from vendor.findistill.services.ingestion import ingestion_service
        extracted = await ingestion_service.process_file(file_bytes, filename, mime_type)
        return extracted or {}

    def _run_normalizer(self, extracted: Dict[str, Any]) -> Dict[str, Any]:
        from vendor.findistill.services.normalizer import normalizer
        try:
            return normalizer.normalize(extracted)
        except Exception as exc:
            logger.warning("Normalizer failed: %s", exc)
            try:
                if isinstance(extracted, dict):
                    meta = extracted.get("metadata")
                    if not isinstance(meta, dict):
                        meta = {}
                    meta["normalizer_error"] = str(exc)
                    meta["needs_review"] = True
                    extracted["metadata"] = meta
            except Exception as exc:
                logger.warning("swallowed exception", exc_info=exc)
            return extracted

    def _build_exports(self, normalized: Dict[str, Any], distill: Optional[DistillResult] = None) -> Dict[str, Any]:
        from vendor.findistill.services.exporter import exporter
        exports: Dict[str, Any] = {}
        try:
            exports["jsonl"] = exporter.to_jsonl(normalized)
        except Exception as exc:
            exports["jsonl_error"] = str(exc)
        try:
            exports["markdown"] = exporter.to_markdown(normalized)
        except Exception as exc:
            exports["markdown_error"] = str(exc)
        try:
            exports["parquet"] = exporter.to_parquet(normalized)
        except Exception as exc:
            exports["parquet_error"] = str(exc)
        # HDF5 is optional and often unavailable in minimal/runtime builds. Keep it behind a flag
        # so it never degrades the default conversion path.
        if os.getenv("ENABLE_HDF5_EXPORT", "0") == "1":
            try:
                exports["hdf5"] = exporter.to_hdf5(normalized)
            except Exception as exc:
                exports["hdf5_error"] = str(exc)

        if distill:
            exports["facts_table"] = exporter.export_facts(distill.facts, distill.metadata)
            try:
                exports["triples_csv"] = exporter.to_triples_csv(extract_graph_triples(distill))
            except Exception as exc:
                exports["triples_csv_error"] = str(exc)
        return exports

    def _build_spokes(self, distill: DistillResult, decision: Optional[DecisionResult]) -> Dict[str, Any]:
        spokes: Dict[str, Any] = {}
        try:
            spokes["rag_contexts"] = build_rag_context(distill, distill.metadata.get("doc_id", "case"))
        except Exception as exc:
            spokes["rag_contexts_error"] = str(exc)
        try:
            spokes["graph_triples"] = extract_graph_triples(distill)
        except Exception as exc:
            spokes["graph_triples_error"] = str(exc)
        if decision:
            try:
                spokes["training_set"] = build_training_set(distill.metadata.get("doc_id", "case"), distill, decision)
            except Exception as exc:
                spokes["training_set_error"] = str(exc)
        return spokes

    def _build_mathematics(self, distill: DistillResult) -> Dict[str, Any]:
        try:
            analysis = PrecisoMathematicsService().analyze(distill.facts)
            return {
                "series": analysis.series,
                "derived": analysis.derived,
                "visibility_graph": analysis.visibility_graph,
            }
        except Exception as exc:
            return {"error": str(exc)}

    def _build_cot(self, normalized: Dict[str, Any]) -> str:
        jsonl_data = normalized.get("jsonl_data", [])
        reasoning_qa = normalized.get("reasoning_qa", [])
        if jsonl_data:
            return "\n".join(jsonl_data)
        if reasoning_qa:
            return "\n\n".join([qa.get("response", "") for qa in reasoning_qa])
        return ""

    async def _run_snorkel(self, distill: DistillResult, normalized: Dict[str, Any]) -> Dict[str, Any]:
        fields = os.getenv("SNORKEL_FIELDS", "revenue,profit,net_income,assets,liabilities")
        target_fields = [f.strip() for f in fields.split(",") if f.strip()]
        if not target_fields:
            return {}

        document_text = (distill.cot_markdown or "")
        table_data = normalized.get("tables", [])

        lf = LabelingFunctions()
        aggregator = SnorkelAggregator()

        aggregated_facts = []
        lf_metrics_payload = []
        for field in target_fields:
            lf_results = [
                lf.lf_regex(document_text, field),
                lf.lf_table_layout(table_data, field),
                lf.lf_keyword(document_text, field),
            ]
            aggregated = aggregator.aggregate(lf_results)

            llm_gate = float(os.getenv("SNORKEL_LLM_TRIGGER_CONFIDENCE", "0.75"))
            if os.getenv("SNORKEL_LLM_ENABLED", "0") == "1" and aggregated.get("confidence", 0.0) < llm_gate:
                lf_results.append(await lf.lf_llm(document_text, field))
                aggregated = aggregator.aggregate(lf_results)

            metrics = compute_lf_metrics(lf_results)
            noise = compute_label_noise(metrics)
            quality_score = compute_data_quality(metrics, aggregated.get("confidence", 0.0))
            lf_metrics_payload.append({
                "field": field,
                "metrics": metrics,
                "noise": noise,
                "quality_score": quality_score,
            })

            if aggregated.get("value") is not None:
                aggregated_facts.append({
                    "metric": field,
                    "value": aggregated.get("value"),
                    "unit": aggregated.get("unit", "currency"),
                    "confidence_score": aggregated.get("confidence", 0.0),
                    "tags": ["snorkel"],
                })

        return {
            "facts": aggregated_facts,
            "lf_metrics": lf_metrics_payload,
        }

    def _build_quality_metrics(self, distill: DistillResult, normalized: Dict[str, Any]) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}
        try:
            metrics["fact_count"] = len(distill.facts)
            metrics["table_count"] = len(normalized.get("tables", []) or [])
        except Exception as exc:
            logger.warning("swallowed exception", exc_info=exc)
        try:
            metrics["cell_validation"] = self._compute_cell_level_validation(distill, normalized)
        except Exception as exc:
            logger.warning("swallowed exception", exc_info=exc)
        try:
            needs_review_count = 0
            missing_unit = 0
            missing_period = 0
            missing_evidence = 0
            for f in distill.facts or []:
                if not isinstance(f, dict):
                    continue
                if f.get("needs_review"):
                    needs_review_count += 1
                if not f.get("unit"):
                    missing_unit += 1
                if not f.get("period_norm") and not f.get("period"):
                    missing_period += 1
                ev = f.get("evidence") or {}
                if not isinstance(ev, dict) or not ev.get("snippet"):
                    missing_evidence += 1
            metrics["quality_gate"] = {
                "needs_review_count": needs_review_count,
                "missing_unit_count": missing_unit,
                "missing_period_count": missing_period,
                "missing_evidence_count": missing_evidence,
            }
        except Exception as exc:
            logger.warning("swallowed exception", exc_info=exc)
        return metrics

    def _compute_cell_level_validation(self, distill: DistillResult, normalized: Dict[str, Any]) -> Dict[str, Any]:
        """
        "Cell-level" numeric preservation check (best-effort).
        For facts that carry (table, row_idx, col_name), verify the table cell matches the fact value.
        """
        tables = (normalized or {}).get("tables", []) or []
        if not tables or not (distill.facts or []):
            return {"checked": 0, "mismatched": 0, "mismatch_rate": 0.0, "examples": []}

        lookup: Dict[tuple, str] = {}
        for t in tables:
            tname = t.get("name") or "table"
            headers = [str(h) for h in (t.get("headers") or [])]
            rows = t.get("rows") or []
            for r_idx, row in enumerate(rows):
                for c_idx, col_name in enumerate(headers):
                    cell = ""
                    try:
                        if c_idx < len(row):
                            cell = str(row[c_idx])
                    except Exception:
                        cell = ""
                    lookup[(str(tname), int(r_idx), str(col_name))] = cell

        def norm_num_token(s: Any) -> Optional[Decimal]:
            if s is None:
                return None
            txt = str(s).strip()
            if not txt:
                return None
            neg = "(" in txt and ")" in txt
            txt = txt.replace(",", "").replace("$", "").replace("USD", "").replace("KRW", "").strip()
            txt = txt.replace("(", "").replace(")", "")
            txt = txt.replace("%", "").strip()
            if not txt:
                return None
            try:
                val = Decimal(txt)
            except (InvalidOperation, ValueError):
                return None
            return -val if neg else val

        checked = 0
        mismatched = 0
        examples: List[Dict[str, Any]] = []

        for f in distill.facts or []:
            if not isinstance(f, dict):
                continue
            dims = f.get("dimensions") or {}
            if not isinstance(dims, dict):
                continue
            tname = dims.get("table")
            row_idx = dims.get("row_idx")
            col_name = dims.get("col_name")
            if tname is None or row_idx is None or col_name is None:
                continue

            key = (str(tname), int(row_idx), str(col_name))
            if key not in lookup:
                continue

            cell_val = lookup.get(key, "")
            fact_val = f.get("normalized_value")
            if fact_val is None:
                fact_val = f.get("value")
            if fact_val is None:
                continue

            a = norm_num_token(cell_val)
            b = norm_num_token(fact_val)
            if a is None or b is None:
                continue

            checked += 1
            if a != b:
                mismatched += 1
                if len(examples) < 8:
                    examples.append(
                        {
                            "table": str(tname),
                            "row_idx": int(row_idx),
                            "col_name": str(col_name),
                            "cell_value": str(cell_val),
                            "fact_value": str(fact_val),
                            "metric": f.get("metric") or f.get("label") or f.get("concept"),
                            "period": f.get("period_norm") or f.get("period"),
                            "page": (f.get("evidence") or {}).get("page"),
                            "method": (f.get("evidence") or {}).get("method"),
                        }
                    )

        mismatch_rate = (mismatched / checked) if checked else 0.0
        return {
            "checked": checked,
            "mismatched": mismatched,
            "mismatch_rate": round(float(mismatch_rate), 4),
            "examples": examples,
        }

    def _attempt_scale_correction(self, distill: DistillResult, normalized: Dict[str, Any], cv: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        If cell-level mismatches consistently look like a 1,000x issue (millions vs billions),
        apply a deterministic scale correction to facts and re-run validation.
        """
        checked = int(cv.get("checked") or 0)
        mismatched = int(cv.get("mismatched") or 0)
        examples = cv.get("examples") or []
        if checked < 10 or mismatched < 5 or not examples:
            return None

        def to_dec(x: Any) -> Optional[Decimal]:
            if x is None:
                return None
            s = str(x).strip()
            if not s:
                return None
            neg = "(" in s and ")" in s
            s = s.replace(",", "").replace("$", "").replace("(", "").replace(")", "")
            s = s.replace("%", "").strip()
            try:
                d = Decimal(s)
            except (InvalidOperation, ValueError):
                return None
            return -d if neg else d

        votes: Dict[str, int] = {"*1000": 0, "/1000": 0}
        for ex in examples:
            a = to_dec(ex.get("cell_value"))
            b = to_dec(ex.get("fact_value"))
            if a is None or b is None or b == 0:
                continue
            ratio = (a / b).copy_abs()
            # Accept near-1000 within tolerance.
            if abs(ratio - Decimal("1000")) <= Decimal("1"):
                votes["*1000"] += 1
            # Accept near-0.001 within tolerance.
            inv = (Decimal("1") / ratio) if ratio != 0 else None
            if inv is not None and abs(inv - Decimal("1000")) <= Decimal("1"):
                votes["/1000"] += 1

        total_votes = votes["*1000"] + votes["/1000"]
        if total_votes < 5:
            return None

        direction = "*1000" if votes["*1000"] >= votes["/1000"] else "/1000"
        dominance = max(votes["*1000"], votes["/1000"]) / max(1, total_votes)
        if dominance < 0.8:
            return None

        factor = Decimal("1000") if direction == "*1000" else (Decimal("1") / Decimal("1000"))

        # Apply correction only to facts that are table-anchored (safe) and match the affected tables.
        affected_tables = {str(ex.get("table") or "") for ex in examples if ex.get("table")}
        if not affected_tables:
            return None

        mutated = 0
        for f in distill.facts or []:
            if not isinstance(f, dict):
                continue
            dims = f.get("dimensions") or {}
            if not isinstance(dims, dict):
                continue
            if str(dims.get("table") or "") not in affected_tables:
                continue
            val = f.get("normalized_value")
            key = "normalized_value"
            if val is None:
                val = f.get("value")
                key = "value"
            d = to_dec(val)
            if d is None:
                continue
            f[key] = str((d * factor).normalize())
            mutated += 1

        if mutated == 0:
            return None

        return {
            "type": "scale_correction",
            "direction": direction,
            "factor": str(factor),
            "tables": sorted([t for t in affected_tables if t]),
            "mutated_facts": mutated,
            "votes": votes,
        }

    def _process_structured_payload(self, document: Dict[str, Any], source: str) -> Dict[str, Any]:
        content = document.get("content") or {}
        if not isinstance(content, dict):
            return {"content": content, "metadata": {"source": source}}
        # If this is already a FinDistill-like payload, preserve it as-is.
        if isinstance(content.get("facts"), list) and ("reasoning_qa" in content or "jsonl_data" in content):
            payload = dict(content)
            payload.setdefault("metadata", {})
            if isinstance(payload["metadata"], dict):
                payload["metadata"].setdefault("source", source)
            return payload
        try:
            from app.services.polars_processing import process_with_polars
            processed = process_with_polars(content, source)
            if isinstance(processed, dict):
                processed.setdefault("metadata", {})
                if isinstance(processed["metadata"], dict):
                    processed["metadata"].setdefault("source", source)
            return processed if isinstance(processed, dict) else {"content": processed, "metadata": {"source": source}}
        except Exception as exc:
            # Don't drop fields; return original content on failure.
            logger.warning("Structured processing failed: %s", exc)
            payload = dict(content)
            payload.setdefault("metadata", {})
            if isinstance(payload["metadata"], dict):
                payload["metadata"].setdefault("source", source)
                payload["metadata"].setdefault("warning", f"structured_processing_failed: {exc}")
            return payload
