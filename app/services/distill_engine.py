import base64
import os
import io
from dataclasses import dataclass
from collections import defaultdict
from copy import deepcopy
from typing import Any, Dict, List, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from app.services.types import DistillResult

@dataclass
class SymbolicRule:
    rule_id: str
    target_metric: str
    component_metrics: List[str]
    operation: str  # "sum", "difference"
    description: str

class DistillEngine:
    async def extract(self, document: Dict[str, Any]) -> DistillResult:
        raise NotImplementedError


class FinDistillAdapter(DistillEngine):
    """Adapter to run the FinDistill ingestion + normalization pipeline."""

    ACCOUNTING_IDENTITIES = [
        SymbolicRule(
            rule_id="net_income_calc",
            target_metric="net income",
            component_metrics=["revenue", "expenses"],
            operation="difference",
            description="Net Income = Revenue - Expenses"
        ),
        SymbolicRule(
            rule_id="gross_profit_calc",
            target_metric="gross profit",
            component_metrics=["revenue", "cost of goods sold"],
            operation="difference",
            description="Gross Profit = Revenue - Cost of Goods Sold"
        ),
        SymbolicRule(
            rule_id="total_assets_calc",
            target_metric="total assets",
            component_metrics=["current assets", "non-current assets"],
            operation="sum",
            description="Total Assets = Current + Non-current Assets"
        ),
        SymbolicRule(
            rule_id="balance_sheet_identity",
            target_metric="total assets",
            component_metrics=["total liabilities", "total equity"],
            operation="sum",
            description="Assets = Liabilities + Equity"
        )
    ]

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

        # Pixel-Level Data Lineage: Enrich facts with coordinates from PDF
        if mime_type == "application/pdf":
            reflected_facts = self._enrich_with_source_anchors(reflected_facts, file_bytes)
            
        # Pillar 1: Agentic Ontology Self-Correction
        reflected_facts = self._self_heal_ontology_links(reflected_facts)
        
        # Pillar 1+4: Kinetic Action Extraction (Extracting potential strategies as nodes)
        reflected_facts = self._extract_kinetic_actions(reflected_facts, cot)

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

        # Phase 3.5: Symbolic Logic Validation (FinReflect-Chain)
        working = self._validate_with_symbolic_logic(working)
        symbolic_report = self._generate_symbolic_report(working)

        summary = {
            "enabled": True,
            "max_rounds": max_rounds,
            "rounds_executed": rounds_executed,
            "input_count": len(facts),
            "output_count": len(working),
            "history": history,
            "error_report": dict(sorted(aggregate_error_counts.items())),
            "error_types_detected": sorted(aggregate_error_counts.keys()),
            "symbolic_report": symbolic_report,
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

    def _enrich_with_source_anchors(self, facts: List[Dict[str, Any]], file_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Pixel-Level Data Lineage Implementation:
        Uses PyMuPDF to locate extracted facts within the original PDF.
        Enhanced with fuzzy multi-word search and best-match heuristic.
        """
        if not fitz or not file_bytes:
            return facts

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            print(f"[Lineage] Failed to open PDF for coordinate mapping: {e}")
            return facts

        for fact in facts:
            search_candidates = []
            
            # Priority 1: Exact statement (full context)
            if fact.get("statement"):
                search_candidates.append(fact["statement"])
            
            # Priority 2: Label + Value
            label = fact.get("label") or fact.get("metric")
            value = str(fact.get("value", ""))
            if label and value:
                search_candidates.append(f"{label} {value}")
                search_candidates.append(label)
                
            # Priority 3: Just the metric/label
            if label:
                search_candidates.append(label)
            
            # Priority 4: Just the value (only if reasonably long)
            if len(value) >= 3 and value not in ("None", "0", "0.0"):
                search_candidates.append(value)

            best_anchor = None
            
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                for term in search_candidates:
                    if not term or len(term.strip()) < 2:
                        continue
                        
                    # Precise coordinate search
                    instances = page.search_for(term)
                    if instances:
                        # For now, we take the one that contains both if possible, 
                        # or just the first occurrence of the strongest candidate.
                        inst = instances[0]
                        best_anchor = {
                            "page": page_idx + 1,
                            "box": [inst.x0, inst.y0, inst.x1, inst.y1],
                            "match_term": term,
                            "match_type": "precise"
                        }
                        break
                if best_anchor:
                    break
            
            # Fallback: Fuzzy word search if no exact match
            if not best_anchor and label:
                words = label.split()
                if len(words) > 1:
                    first_word_instances = page.search_for(words[0])
                    if first_word_instances:
                        inst = first_word_instances[0]
                        best_anchor = {
                            "page": page_idx + 1,
                            "box": [inst.x0, inst.y0, inst.x1, inst.y1],
                            "match_term": words[0],
                            "match_type": "partial"
                        }
            
            if best_anchor:
                fact["source_anchor"] = best_anchor
        
        doc.close()
        return facts

    def _self_heal_ontology_links(self, facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Pillar 1: Agentic Construction. 
        Automatically fixes common ontological errors in extracted triples.
        """
        healed_facts = []
        for fact in facts:
            healed = deepcopy(fact)
            head = str(healed.get("head_node") or healed.get("entity") or "").lower()
            relation = str(healed.get("relation") or healed.get("metric") or "").lower()
            tail = str(healed.get("tail_node") or healed.get("value") or "").lower()

            # Rule 1: Inverse Link Correction (e.g., "Company is owned by Parent" -> "Parent owns Company")
            if "owned by" in relation:
                healed["head_node"], healed["tail_node"] = fact.get("tail_node"), fact.get("head_node")
                healed["relation"] = "owns"
                healed["tags"] = healed.get("tags", []) + ["ontology_healed"]
            
            # Rule 2: Metric Normalization
            if "revenue" in relation and "sales" in relation:
                healed["relation"] = "revenue"

            healed_facts.append(healed)
        return healed_facts

    def _extract_kinetic_actions(self, facts: List[Dict[str, Any]], cot: str) -> List[Dict[str, Any]]:
        """
        Pillar 1+4 Evolution: Kinetic Extraction.
        Identifies potential 'Actions' or 'Strategies' mentioned in the CoT/Facts.
        """
        enhanced_facts = deepcopy(facts)
        action_keywords = ["strategy", "plan", "hedging", "refinance", "restructure", "expand", "reduce cost"]
        
        # Simple heuristic: Look for action keywords in CoT or statements
        for term in action_keywords:
            if term in cot.lower():
                # Add a virtual 'Action Node' to the fact list
                enhanced_facts.append({
                    "head_node": "Strategic Recommendation",
                    "relation": "suggests action",
                    "tail_node": f"Potential {term.capitalize()}",
                    "confidence": "medium",
                    "tags": ["kinetic_action_extracted"],
                    "statement": f"System identified a potential {term} from the analysis."
                })
        
        return enhanced_facts

    def _generate_symbolic_report(self, facts: List[Dict[str, Any]]) -> Dict[str, Any]:
        mismatched_facts = [
            fact for fact in facts if "symbolic_mismatch" in (fact.get("tags") or [])
        ]
        if not mismatched_facts:
            return {
                "mismatch_count": 0,
                "rules_triggered": [],
                "metrics_affected": [],
            }

        rules_triggered: Dict[str, int] = defaultdict(int)
        metrics_affected: Dict[str, int] = defaultdict(int)
        for fact in mismatched_facts:
            metric = str(fact.get("metric") or fact.get("relation") or "").strip().lower()
            if metric:
                metrics_affected[metric] += 1
            for issue in fact.get("reflection_issues", []):
                if isinstance(issue, str) and issue.startswith("Symbolic mismatch: "):
                    rules_triggered[issue.replace("Symbolic mismatch: ", "").strip()] += 1

        return {
            "mismatch_count": len(mismatched_facts),
            "rules_triggered": dict(sorted(rules_triggered.items())),
            "metrics_affected": dict(sorted(metrics_affected.items())),
        }

    def _validate_with_symbolic_logic(self, facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Pillar 1: Symbolic-Neural Hybrid Validation.
        Checks facts against accounting identities and tags mismatches.
        """
        # Create a lookup for metrics in the current context
        metric_map = {}
        for f in facts:
            metric = str(f.get("metric") or f.get("relation") or "").strip().lower()
            val = f.get("value")
            if metric and val is not None:
                parsed = self._parse_numeric(val)
                if parsed is not None:
                    metric_map[metric] = parsed

        validated_facts = deepcopy(facts)
        for rule in self.ACCOUNTING_IDENTITIES:
            target_metric = str(rule.target_metric).strip().lower()
            component_metrics = [str(m).strip().lower() for m in rule.component_metrics]
            target_val = metric_map.get(target_metric)
            component_vals = [metric_map.get(m) for m in component_metrics]
            
            if target_val is not None and all(v is not None for v in component_vals):
                # Perform arithmetic check
                calculated = 0.0
                if rule.operation == "sum":
                    calculated = sum(component_vals)
                elif rule.operation == "difference":
                    calculated = component_vals[0] - sum(component_vals[1:])
                else:
                    continue
                
                # Check for discrepancy (> 1% tolerance)
                discrepancy = abs(calculated - target_val)
                if target_val != 0 and (discrepancy / abs(target_val)) > 0.01:
                    # Tag all related facts
                    for f in validated_facts:
                        f_metric = str(f.get("metric") or f.get("relation") or "").strip().lower()
                        if f_metric == target_metric or f_metric in component_metrics:
                            f["tags"] = f.get("tags", []) + ["symbolic_mismatch"]
                            f["confidence"] = "low"
                            f["reflection_issues"] = f.get("reflection_issues", []) + [f"Symbolic mismatch: {rule.description}"]

        return validated_facts
