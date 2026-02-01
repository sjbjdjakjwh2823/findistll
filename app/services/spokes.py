from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional

from app.services.types import DecisionResult, DistillResult


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "is", "it", "of", "on", "or", "that", "the",
    "to", "was", "were", "with", "this", "these", "those", "its",
}


def _first_present(data: Dict[str, Any], keys: Iterable[str]) -> Optional[str]:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        return str(value)
    return None


def extract_keywords(text: str, max_keywords: int = 12) -> List[str]:
    tokens = re.findall(r"[A-Za-z0-9]{2,}", text.lower())
    tokens = [t for t in tokens if t not in _STOPWORDS]
    if not tokens:
        return []
    counts = Counter(tokens)
    return [token for token, _ in counts.most_common(max_keywords)]


def _fact_to_text(fact: Any) -> str:
    if isinstance(fact, dict):
        parts = []
        for key in sorted(fact.keys()):
            value = fact.get(key)
            parts.append(f"{key}: {value}")
        return " | ".join(parts)
    return str(fact)


def build_rag_context(distill: DistillResult, case_id: str) -> List[Dict[str, Any]]:
    contexts: List[Dict[str, Any]] = []
    metadata = distill.metadata or {}

    for idx, fact in enumerate(distill.facts):
        if not isinstance(fact, dict):
            continue
        text_content = _fact_to_text(fact)
        entity = _first_present(fact, ["entity", "company", "issuer", "name", "ticker"])
        period = _first_present(fact, ["period", "fiscal_period", "date", "as_of"])
        source = _first_present(fact, ["source"]) or metadata.get("source", "distill")
        keywords = extract_keywords(text_content)
        contexts.append(
            {
                "chunk_id": f"{case_id}-fact-{idx}",
                "entity": entity,
                "period": period,
                "source": source,
                "text_content": text_content,
                "keywords": keywords,
            }
        )

    if distill.cot_markdown:
        paragraphs = [p.strip() for p in distill.cot_markdown.split("\n\n") if p.strip()]
        for idx, paragraph in enumerate(paragraphs):
            text_content = paragraph
            entity = metadata.get("entity") or metadata.get("title")
            period = metadata.get("period") or metadata.get("fiscal_period")
            keywords = extract_keywords(text_content)
            contexts.append(
                {
                    "chunk_id": f"{case_id}-cot-{idx}",
                    "entity": entity,
                    "period": period,
                    "source": "cot",
                    "text_content": text_content,
                    "keywords": keywords,
                }
            )

    return contexts


def extract_graph_triples(distill: DistillResult) -> List[Dict[str, Any]]:
    triples: List[Dict[str, Any]] = []
    seen = set()

    for fact in distill.facts:
        if not isinstance(fact, dict):
            continue
        head = _first_present(fact, ["entity", "company", "issuer", "name", "ticker"])
        relation = _first_present(fact, ["relation", "relationship", "metric", "fact", "type"])
        tail = _first_present(
            fact,
            [
                "counterparty",
                "subsidiary",
                "parent",
                "segment",
                "region",
                "product",
                "customer",
                "vendor",
                "related_entity",
            ],
        )
        if tail is None and fact.get("value") is not None:
            tail = str(fact.get("value"))
        if head and relation and tail:
            properties: Dict[str, Any] = {}
            if fact.get("period"):
                properties["period"] = fact.get("period")
            if fact.get("unit"):
                properties["unit"] = fact.get("unit")
            if fact.get("source"):
                properties["source"] = fact.get("source")
            key = (head, relation, tail)
            if key in seen:
                continue
            seen.add(key)
            triples.append(
                {
                    "head_node": head,
                    "relation": relation,
                    "tail_node": tail,
                    "properties": properties or None,
                }
            )

    if distill.cot_markdown:
        pattern = re.compile(
            r"([A-Z][A-Za-z0-9&().\- ]{2,})\s+(acquired|acquires|merged with|subsidiary of|partnered with|owns|owned by)\s+([A-Z][A-Za-z0-9&().\- ]{2,})",
            re.IGNORECASE,
        )
        for match in pattern.finditer(distill.cot_markdown):
            head, relation, tail = match.groups()
            head = head.strip()
            tail = tail.strip()
            relation = relation.strip().lower()
            key = (head, relation, tail)
            if key in seen:
                continue
            seen.add(key)
            triples.append(
                {
                    "head_node": head,
                    "relation": relation,
                    "tail_node": tail,
                    "properties": {"source": "cot"},
                }
            )

    return triples


def build_training_set(case_id: str, distill: DistillResult, decision: DecisionResult) -> Dict[str, Any]:
    metadata = {
        "case_id": case_id,
        "source": distill.metadata.get("source") if distill.metadata else None,
        "doc_id": distill.metadata.get("doc_id") if distill.metadata else None,
    }
    input_features = {
        "facts": distill.facts,
        "metadata": distill.metadata,
    }
    reasoning_chain = {
        "cot_markdown": distill.cot_markdown,
    }
    output_narrative = decision.rationale
    training_prompt = (
        "Facts:\n"
        f"{distill.facts}\n\n"
        "Reasoning:\n"
        f"{distill.cot_markdown}\n\n"
        "Decision:\n"
        f"{decision.decision}\n"
    )
    return {
        "metadata": metadata,
        "input_features": input_features,
        "reasoning_chain": reasoning_chain,
        "output_narrative": output_narrative,
        "training_prompt": training_prompt,
    }
