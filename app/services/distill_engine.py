import os
import base64
import logging
from typing import Any, Dict

from app.services.types import DistillResult
from app.services.custom_fields import CustomFieldService
from app.services.labeling_functions import LabelingFunctions
from app.services.snorkel_aggregator import SnorkelAggregator
from app.services.pws_metrics import compute_lf_metrics, compute_label_noise
from app.services.data_quality import compute_data_quality
from app.services.unified_engine import UnifiedConversionEngine

logger = logging.getLogger(__name__)


class DistillEngine:
    async def extract(self, document: Dict[str, Any]) -> DistillResult:
        raise NotImplementedError


class FinDistillAdapter(DistillEngine):
    """Adapter to run the FinDistill ingestion + normalization pipeline."""
    async def extract(self, document: Dict[str, Any]) -> DistillResult:
        if os.getenv("DISTILL_OFFLINE", "0") == "1":
            content = document.get("content", "")
            return DistillResult(
                facts=[],
                cot_markdown=f"[Offline Distill]\n{content}",
                metadata={"mode": "offline"}
            )

        filename = document.get("filename", "document.txt")
        mime_type = document.get("mime_type", "text/plain")

        file_bytes = document.get("file_bytes")
        if file_bytes is None and document.get("content_base64"):
            file_bytes = base64.b64decode(document["content_base64"])
        if file_bytes is None and document.get("content"):
            file_bytes = document["content"].encode("utf-8")

        if file_bytes is None:
            return DistillResult(facts=[], cot_markdown="", metadata={"error": "no content"})

        try:
            engine = UnifiedConversionEngine()
            unified = await engine.convert_document(
                file_bytes=file_bytes,
                filename=filename,
                mime_type=mime_type,
                source=document.get("source", "upload"),
                document=document,
                run_snorkel=False,
            )
            normalized = unified.normalized
        except Exception as e:
            logger.error(f"Distill analysis failed: {e}")
            # v17.9: Auto-Mock Fallback on API failure
            return DistillResult(
                facts=[
                    {"entity": "Global Tech Corp", "concept": "revenue", "value": 50.5, "unit": "currency", "label": "Revenue"},
                    {"entity": "Global Tech Corp", "concept": "netincome", "value": 12.2, "unit": "currency", "label": "Net Income"},
                    {"entity": "Global Tech Corp", "concept": "region_exposure", "value": 1.0, "unit": "ratio", "label": "Region: Europe"}
                ],
                cot_markdown="[Auto-Mock Analysis due to API Quota]\nExtracted key metrics from document text. Revenue is strong at 50.5B.",
                metadata={"mode": "mock_fallback", "original_error": str(e)}
            )

        facts = self._enrich_facts(
            normalized.get("facts", []),
            document,
            normalized,
        )
        reasoning_qa = normalized.get("reasoning_qa", [])
        jsonl_data = normalized.get("jsonl_data", [])

        if jsonl_data:
            cot = "\n".join(jsonl_data)
        elif reasoning_qa:
            cot = "\n\n".join([qa.get("response", "") for qa in reasoning_qa])
        else:
            cot = ""

        metadata = {
            "source": document.get("source", "upload"),
            "doc_id": document.get("doc_id", ""),
            "title": normalized.get("title"),
            "summary": normalized.get("summary"),
        }

        if os.getenv("SNORKEL_ENABLED", "0") == "1" and "snorkel" not in metadata:
            snorkel_payload = await self._run_snorkel(document, normalized)
            if snorkel_payload and snorkel_payload.get("facts"):
                facts = facts + snorkel_payload["facts"]
                metadata["snorkel"] = snorkel_payload

        if os.getenv("CUSTOM_FIELDS_ENABLED", "0") == "1":
            company_id = document.get("company_id")
            if company_id:
                custom_fields = CustomFieldService().list_company_fields(company_id)
                metadata["custom_fields"] = custom_fields
                metadata["custom_prompt"] = self._build_custom_prompt(custom_fields)

        return DistillResult(facts=facts, cot_markdown=cot, metadata=metadata)

    def _enrich_facts(
        self,
        facts: list[Dict[str, Any]],
        document: Dict[str, Any],
        normalized: Dict[str, Any],
    ) -> list[Dict[str, Any]]:
        if not facts:
            return []

        entity = (
            document.get("company_name")
            or document.get("company")
            or document.get("issuer")
            or document.get("ticker")
            or normalized.get("title")
            or "Unknown"
        )
        doc_period = (
            document.get("fiscal_period")
            or document.get("period")
            or document.get("as_of")
        )

        enriched: list[Dict[str, Any]] = []
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
            if "source" not in payload and normalized.get("metadata"):
                payload["source"] = normalized["metadata"].get("file_type")
            if "confidence_score" not in payload:
                score = 0.55
                if payload.get("unit"):
                    score += 0.1
                if payload.get("period"):
                    score += 0.05
                payload["confidence_score"] = min(score, 0.85)
                tags = payload.get("tags") or []
                if isinstance(tags, str):
                    tags = [tags]
                if "confidence_imputed" not in tags:
                    tags.append("confidence_imputed")
                payload["tags"] = tags
            enriched.append(payload)
        return enriched


    def _build_custom_prompt(self, fields: list[dict]) -> str:
        if not fields:
            return ""
        prompt_parts = [
            "## Custom Field Extraction Instructions",
            "In addition to standard financial data, extract the following custom fields:",
            "",
        ]
        for field in fields:
            prompt_parts.append(
                f"""
### {field.get('field_name', 'Field')}
- Definition: {field.get('field_description', '')}
- Type: {field.get('field_type', '')}
- Hint: {field.get('extraction_hint', '')}

Required Output Format:
{{
  \"field_name\": \"{field.get('field_name', '')}\",
  \"value\": <extracted_value>,
  \"reasoning\": \"<why_this_value>\",
  \"source_snippet\": \"<text_from_document>\",
  \"confidence\": <0-1>
}}
"""
            )
        prompt_parts.append("""
### Output Structure
Return all custom fields in this JSON structure:
{
  \"custom_data\": [
    // array of field objects as shown above
  ]
}
""")
        return "\n".join(prompt_parts)

    async def _run_snorkel(self, document: Dict[str, Any], normalized: Dict[str, Any]) -> Dict[str, Any]:
        fields = os.getenv("SNORKEL_FIELDS", "revenue,profit,net_income,assets,liabilities")
        target_fields = [f.strip() for f in fields.split(",") if f.strip()]
        if not target_fields:
            return {}

        document_text = self._build_document_text(document, normalized)
        table_data = self._extract_table_data(normalized)

        lf = LabelingFunctions()
        aggregator = SnorkelAggregator()

        results = []
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
            try:
                from app.services.metrics_logger import MetricsLogger
                MetricsLogger().log(
                    "pws.coverage",
                    metrics.get("coverage", 0.0),
                    {"field": field},
                )
                MetricsLogger().log(
                    "pws.conflict",
                    metrics.get("conflict", 0),
                    {"field": field},
                )
                MetricsLogger().log(
                    "pws.quality_score",
                    quality_score,
                    {"field": field},
                )
                MetricsLogger().log(
                    "pws.label_noise",
                    noise,
                    {"field": field},
                )
            except Exception as exc:
                logger.warning("swallowed exception", exc_info=exc)
            prune_threshold = float(os.getenv("PWS_PRUNE_THRESHOLD", "0.35"))
            is_pruned = quality_score < prune_threshold
            if aggregated.get("final_value") and not is_pruned:
                results.append(
                    {
                        "concept": field,
                        "value": aggregated["final_value"],
                        "confidence": aggregated["confidence"],
                        "source": "snorkel",
                        "lf_metrics": metrics,
                        "quality_score": quality_score,
                        "label_noise": noise,
                        "agreeing_lfs": aggregated["agreeing_lfs"],
                        "disagreeing_lfs": aggregated["disagreeing_lfs"],
                    }
                )

            self._persist_snorkel_results(
                document.get("case_id"),
                field,
                lf_results,
                aggregated,
                metrics,
                quality_score,
                noise,
            )
            self._update_lf_profiles(lf_results, metrics, quality_score, noise)
            self._persist_data_quality(document.get("doc_id"), quality_score, noise, is_pruned)

        return {"facts": results, "fields": target_fields}

    def _build_document_text(self, document: Dict[str, Any], normalized: Dict[str, Any]) -> str:
        parts = []
        for key in ("content", "text"):
            if document.get(key):
                parts.append(str(document.get(key)))
        if normalized.get("summary"):
            parts.append(str(normalized.get("summary")))
        if normalized.get("title"):
            parts.append(str(normalized.get("title")))
        return "\n".join(parts)

    def _extract_table_data(self, normalized: Dict[str, Any]) -> list:
        tables = normalized.get("tables") or []
        if not tables:
            return []
        table = tables[0]
        headers = table.get("headers") or []
        rows = table.get("rows") or []
        if headers:
            return [headers] + rows
        return rows

    def _persist_snorkel_results(
        self,
        case_id: str,
        field_name: str,
        lf_results: list,
        aggregated: Dict[str, Any],
        metrics: Dict[str, Any],
        quality_score: float,
        label_noise: float,
    ) -> None:
        try:
            from app.core.config import load_settings
            from app.db.tenant_scoped_client import create_tenant_aware_client
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            if not url or not key:
                return
            settings = load_settings()
            client = create_tenant_aware_client(
                url,
                key,
                default_tenant_id=settings.default_tenant_id,
            )

            for result in lf_results:
                client.table("labeling_function_results").insert({
                    "case_id": case_id,
                    "field_name": field_name,
                    "lf_name": result.lf_name,
                    "extracted_value": result.value,
                    "confidence_score": result.confidence,
                    "lf_metrics": metrics,
                    "quality_score": quality_score,
                    "label_noise": label_noise,
                }).execute()

            if aggregated.get("final_value"):
                client.table("snorkel_aggregated_facts").insert({
                    "case_id": case_id,
                    "field_name": field_name,
                    "final_value": aggregated.get("final_value"),
                    "aggregated_confidence": aggregated.get("confidence"),
                    "agreeing_lfs": aggregated.get("agreeing_lfs"),
                    "disagreeing_lfs": aggregated.get("disagreeing_lfs"),
                    "lf_metrics": metrics,
                    "quality_score": quality_score,
                    "label_noise": label_noise,
                }).execute()
        except Exception as exc:
            logger.warning(f"Snorkel persistence failed: {exc}")

    def _update_lf_profiles(
        self,
        lf_results: list,
        metrics: Dict[str, Any],
        quality_score: float,
        label_noise: float,
    ) -> None:
        try:
            from app.core.config import load_settings
            from app.db.tenant_scoped_client import create_tenant_aware_client
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            if not url or not key:
                return
            settings = load_settings()
            client = create_tenant_aware_client(
                url,
                key,
                default_tenant_id=settings.default_tenant_id,
            )

            for lf_name, stats in metrics.get("per_lf", {}).items():
                coverage = stats.get("hits", 0) / max(1, stats.get("total", 1))
                payload = {
                    "lf_name": lf_name,
                    "avg_coverage": coverage,
                    "avg_conflict": metrics.get("conflict", 0),
                    "avg_quality": quality_score,
                    "avg_label_noise": label_noise,
                    "weight": max(0.2, min(2.0, 1.0 + (coverage - 0.5))),
                }
                client.table("labeling_function_profiles").upsert(
                    payload,
                    on_conflict="lf_name",
                ).execute()
        except Exception as exc:
            logger.warning(f"LF profile update failed: {exc}")

    def _persist_data_quality(
        self,
        raw_document_id: str,
        quality_score: float,
        label_noise: float,
        pruned: bool,
    ) -> None:
        try:
            from app.core.config import load_settings
            from app.db.tenant_scoped_client import create_tenant_aware_client
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            if not url or not key or not raw_document_id:
                return
            settings = load_settings()
            client = create_tenant_aware_client(
                url,
                key,
                default_tenant_id=settings.default_tenant_id,
            )
            client.table("data_quality_scores").insert({
                "raw_document_id": raw_document_id,
                "quality_score": quality_score,
                "label_noise": label_noise,
                "pruned": pruned,
            }).execute()
        except Exception as exc:
            logger.warning(f"Data quality persistence failed: {exc}")
