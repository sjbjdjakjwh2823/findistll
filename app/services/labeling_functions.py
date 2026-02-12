import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class LFResult:
    lf_name: str
    value: Optional[str]
    confidence: float
    metadata: Optional[Dict[str, Any]] = None


class LabelingFunctions:
    """
    Fast, deterministic labeling functions for financial fields.
    """

    _PATTERNS = {
        "revenue": r"(매출액|revenue)[\\s:]*([0-9,\\.]+)",
        "profit": r"(영업이익|operating income|profit)[\\s:]*([0-9,\\.]+)",
        "net_income": r"(순이익|net income)[\\s:]*([0-9,\\.]+)",
        "assets": r"(총자산|assets)[\\s:]*([0-9,\\.]+)",
        "liabilities": r"(부채|liabilities)[\\s:]*([0-9,\\.]+)",
    }

    def lf_regex(self, document_text: str, field_name: str) -> LFResult:
        pattern = self._PATTERNS.get(field_name)
        if not pattern or not document_text:
            return LFResult("LF_regex", None, 0.0)
        match = re.search(pattern, document_text, re.IGNORECASE)
        if not match:
            return LFResult("LF_regex", None, 0.0)
        value = match.group(2)
        return LFResult("LF_regex", value, 0.85)

    def lf_table_layout(self, table_data: List[List[str]], field_name: str) -> LFResult:
        if not table_data or len(table_data) < 2:
            return LFResult("LF_layout", None, 0.0)
        header = [str(cell).lower() for cell in table_data[0]]
        keywords = {
            "revenue": ["매출", "revenue", "sales"],
            "profit": ["이익", "profit", "operating"],
            "net_income": ["순이익", "net income"],
            "assets": ["자산", "assets", "총자산"],
            "liabilities": ["부채", "liabilities"],
        }.get(field_name, [])

        for idx, cell in enumerate(header):
            if any(keyword in cell for keyword in keywords):
                value = str(table_data[1][idx]) if idx < len(table_data[1]) else None
                if value:
                    return LFResult("LF_layout", value, 0.8)
        return LFResult("LF_layout", None, 0.0)

    def lf_keyword(self, document_text: str, field_name: str) -> LFResult:
        if not document_text:
            return LFResult("LF_keyword", None, 0.0)
        tokens = {
            "revenue": ["revenue", "매출"],
            "profit": ["profit", "이익"],
            "net_income": ["net income", "순이익"],
            "assets": ["assets", "자산"],
            "liabilities": ["liabilities", "부채"],
        }.get(field_name, [])
        for token in tokens:
            if token in document_text.lower():
                return LFResult("LF_keyword", token, 0.4, {"matched": token})
        return LFResult("LF_keyword", None, 0.0)

    async def lf_llm(self, document_text: str, field_name: str) -> LFResult:
        if os.getenv("SNORKEL_LLM_ENABLED", "0") != "1":
            return LFResult("LF_llm", None, 0.0)
        try:
            import openai
        except Exception as exc:
            return LFResult("LF_llm", None, 0.0, {"error": str(exc)})

        prompt = (
            f"Extract the value for '{field_name}' from the following text. "
            "Return JSON: {\"value\": \"...\", \"confidence\": 0.0-1.0}\n\n"
            f"{document_text[:2000]}"
        )
        try:
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model=os.getenv("SNORKEL_LLM_MODEL", "gpt-4"),
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=float(os.getenv("SNORKEL_LLM_TEMPERATURE", "0.2")),
                max_tokens=int(os.getenv("SNORKEL_LLM_MAX_TOKENS", "200")),
            )
            payload = json.loads(response.choices[0].message.content)
            confidence = float(payload.get("confidence", 0.6))
            min_conf = float(os.getenv("SNORKEL_LLM_MIN_CONFIDENCE", "0.6"))
            value = payload.get("value") if confidence >= min_conf else None
            return LFResult("LF_llm", value, confidence)
        except Exception as exc:
            return LFResult("LF_llm", None, 0.0, {"error": str(exc)})
