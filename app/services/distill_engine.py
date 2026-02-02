import base64
import os
from collections import defaultdict
from copy import deepcopy
from typing import Any, Dict, List, Tuple

from app.services.types import DistillResult


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
                metadata={"mode": "offline"},
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
            from vendor.findistill.services.ingestion import ingestion_service
            from vendor.findistill.services.normalizer import normalizer
        except Exception as exc:
            return DistillResult(
                facts=[],
                cot_markdown="",
                metadata={"error": f"findistill import failed: {exc}"},
            )

        extracted = await ingestion_service.process_file(file_bytes, filename, mime_type)
        normalized = normalizer.normalize(extracted)

        facts = normalized.get("facts", [])
        reasoning_qa = normalized.get("reasoning_qa", [])
        jsonl_data = normalized.get("jsonl_data", [])

        if jsonl_data:
            cot = "\n".join(jsonl_data)
        elif reasoning_qa:
            cot = "\n\n".join([qa.get("response", "") for qa in reasoning_qa])
        else:
            cot = ""

        reflected_facts, reflection_summary = self._self_reflect_facts(facts, max_rounds=2)

        metadata = {
            "source": document.get("source", "upload"),
            "doc_id": document.get("doc_id", ""),
            "title": normalized.get("title"),
            "summary": normalized.get("summary"),
            "self_reflection": reflection_summary,
        }

        return DistillResult(facts=reflected_facts, cot_markdown=cot, metadata=metadata)

    def _self_reflect_facts(self, facts: List[Any], max_rounds: int = 2) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        FinReflectKG-inspired self-reflection loop:
        1) Critique extracted facts
        2) Repair low-quality facts
        3) Re-check until stable or max rounds reached
        """
        working: List[Dict[str, Any]] = [self._coerce_fact(f) for f in facts]
        history: List[Dict[str, Any]] = []
        aggregate_error_counts: Dict[str, int] = defaultdict(int)
        rounds_executed = 0

        for idx in range(max_rounds):
            rounds_executed += 1
            critiques = self._critique_facts(working)
            repaired = self._repair_facts(working, critiques)
            deduped = self._dedupe_facts(repaired)
            round_error_report = self._summarize_error_types(critiques)
            for error_type, count in round_error_report.items():
                aggregate_error_counts[error_type] += count

            history.append(
                {
                    "round": idx + 1,
                    "input_count": len(working),
                    "issues_found": sum(1 for c in critiques if c.get("issues")),
                    "error_report": round_error_report,
                    "output_count": len(deduped),
                }
            )

            if self._facts_signature(deduped) == self._facts_signature(working):
                working = deduped
                break
            working = deduped

        summary = {
            "enabled": True,
            "max_rounds": max_rounds,
            "rounds_executed": rounds_executed,
            "input_count": len(facts),
            "output_count": len(working),
            "history": history,
            "error_report": dict(sorted(aggregate_error_counts.items())),
            "error_types_detected": sorted(aggregate_error_counts.keys()),
        }
        return working, summary

    def _coerce_fact(self, fact: Any) -> Dict[str, Any]:
        if isinstance(fact, dict):
            return deepcopy(fact)
        if isinstance(fact, str):
            cleaned = fact.strip()
            return {"statement": cleaned, "raw_fact": fact, "validation_status": "coerced_from_str"}
        return {"raw_fact": str(fact), "validation_status": "coerced_from_unknown"}

    def _critique_facts(self, facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        critiques: List[Dict[str, Any]] = []
        for fact in facts:
            issues: List[str] = []
            if not any(fact.get(k) for k in ("statement", "metric", "value", "entity", "relation", "head_node")):
                issues.append("missing_semantic_content")
            value = fact.get("value")
            if isinstance(value, str):
                parsed = self._parse_numeric(value)
                if parsed is None and any(ch.isdigit() for ch in value):
                    issues.append("invalid_numeric_value")
            if not fact.get("confidence"):
                issues.append("missing_confidence")
            if self._is_missing_triple_component(fact):
                issues.append("missing_required_component")
            error_types = self._classify_error_types(fact, issues)
            critiques.append({"issues": sorted(set(issues)), "error_types": error_types})
        return critiques

    def _repair_facts(self, facts: List[Dict[str, Any]], critiques: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        repaired: List[Dict[str, Any]] = []
        for fact, critique in zip(facts, critiques):
            fixed = deepcopy(fact)
            issues = critique.get("issues", [])
            error_types = critique.get("error_types", [])

            if "invalid_numeric_value" in issues and isinstance(fixed.get("value"), str):
                parsed = self._parse_numeric(fixed.get("value", ""))
                if parsed is not None:
                    fixed["value"] = parsed

            if "missing_confidence" in issues:
                fixed["confidence"] = "medium"

            if "missing_semantic_content" in issues:
                statement = self._build_statement(fixed)
                if statement:
                    fixed["statement"] = statement
            if "relation_inversion" in error_types:
                fixed = self._repair_relation_inversion(fixed)

            if not fixed.get("validation_status"):
                fixed["validation_status"] = "reflected"
            if issues:
                fixed["reflection_issues"] = issues
            if error_types:
                fixed["reflection_error_types"] = error_types

            repaired.append(fixed)
        return repaired

    def _dedupe_facts(self, facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        deduped: List[Dict[str, Any]] = []
        for fact in facts:
            signature = self._fact_signature(fact)
            if signature in seen:
                continue
            seen.add(signature)
            deduped.append(fact)
        return deduped

    def _build_statement(self, fact: Dict[str, Any]) -> str:
        entity = fact.get("entity") or fact.get("head_node")
        metric = fact.get("metric") or fact.get("relation")
        value = fact.get("value") or fact.get("tail_node")
        period = fact.get("period") or fact.get("date")
        if entity and metric and value is not None:
            if period:
                return f"{entity} {metric} {value} ({period})"
            return f"{entity} {metric} {value}"
        return ""

    def _parse_numeric(self, value: str) -> Any:
        cleaned = self._normalize_numeric_token(value)
        if not cleaned:
            return None
        try:
            if "." in cleaned:
                return float(cleaned)
            return int(cleaned)
        except (TypeError, ValueError):
            return None

    def _normalize_numeric_token(self, value: Any) -> str:
        text = str(value).strip()
        if not text:
            return ""
        text = text.replace(",", "")
        replacements = {
            "O": "0",
            "o": "0",
            "l": "1",
            "I": "1",
            "S": "5",
            "B": "8",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        filtered = []
        for idx, ch in enumerate(text):
            if ch.isdigit() or ch in (".", "-"):
                filtered.append(ch)
            elif ch == "+" and idx == 0:
                continue
        return "".join(filtered)

    def _is_missing_triple_component(self, fact: Dict[str, Any]) -> bool:
        entity = fact.get("entity") or fact.get("head_node")
        relation = fact.get("metric") or fact.get("relation")
        value = fact.get("value") or fact.get("tail_node")
        return not entity or not relation or value in (None, "")

    def _classify_error_types(self, fact: Dict[str, Any], issues: List[str]) -> List[str]:
        error_types: List[str] = []

        if "invalid_numeric_value" in issues:
            error_types.append("numeric_typo")

        if "missing_semantic_content" in issues or "missing_required_component" in issues:
            error_types.append("omission")

        if self._detect_relation_inversion(fact):
            error_types.append("relation_inversion")

        return sorted(set(error_types))

    def _detect_relation_inversion(self, fact: Dict[str, Any]) -> bool:
        relation = str(fact.get("metric") or fact.get("relation") or "").lower()
        value = fact.get("value")
        parsed = None
        if isinstance(value, str):
            parsed = self._parse_numeric(value)
        elif isinstance(value, (int, float)):
            parsed = float(value)

        if parsed is None:
            return False

        down_terms = ("decrease", "decline", "down", "drop", "reduce", "compressed")
        up_terms = ("increase", "rise", "up", "grow", "expanded", "improved")
        if any(term in relation for term in down_terms) and parsed > 0:
            return True
        if any(term in relation for term in up_terms) and parsed < 0:
            return True
        return False

    def _repair_relation_inversion(self, fact: Dict[str, Any]) -> Dict[str, Any]:
        relation = str(fact.get("metric") or fact.get("relation") or "").lower()
        value = fact.get("value")
        parsed = None
        if isinstance(value, str):
            parsed = self._parse_numeric(value)
        elif isinstance(value, (int, float)):
            parsed = float(value)
        if parsed is None:
            return fact

        fixed = deepcopy(fact)
        down_terms = ("decrease", "decline", "down", "drop", "reduce", "compressed")
        up_terms = ("increase", "rise", "up", "grow", "expanded", "improved")
        if any(term in relation for term in down_terms):
            fixed["value"] = -abs(parsed)
            fixed["direction"] = "down"
        elif any(term in relation for term in up_terms):
            fixed["value"] = abs(parsed)
            fixed["direction"] = "up"
        return fixed

    def _summarize_error_types(self, critiques: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = defaultdict(int)
        for critique in critiques:
            for error_type in critique.get("error_types", []):
                counts[error_type] += 1
        return dict(sorted(counts.items()))

    def _fact_signature(self, fact: Dict[str, Any]) -> str:
        return "|".join(
            [
                str(fact.get("entity") or fact.get("head_node") or ""),
                str(fact.get("metric") or fact.get("relation") or ""),
                str(fact.get("value") or fact.get("tail_node") or ""),
                str(fact.get("period") or fact.get("date") or ""),
                str(fact.get("statement") or ""),
            ]
        )

    def _facts_signature(self, facts: List[Dict[str, Any]]) -> Tuple[str, ...]:
        return tuple(sorted(self._fact_signature(fact) for fact in facts))
