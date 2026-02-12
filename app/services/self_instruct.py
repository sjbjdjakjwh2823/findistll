import json
import os
from typing import Any, Dict, List


class SelfInstructAugmentor:
    """
    Generate additional training cases from gold standard seeds.
    """

    def __init__(self) -> None:
        self._client = None

    def _openai_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            except Exception:
                self._client = None
        return self._client

    async def generate(self, seed_cases: List[Dict[str, Any]], target_count: int = 10) -> List[Dict[str, Any]]:
        if not seed_cases:
            return []

        client = self._openai_client()
        if not client:
            return []

        examples = self._format_seed(seed_cases)
        prompt = (
            "You are a financial analysis expert. Generate new cases based on the examples.\n"
            f"Create {target_count} cases in JSON with keys: company, industry, facts, cot, decision, confidence.\n\n"
            f"Examples:\n{examples}\n"
        )

        try:
            response = client.chat.completions.create(
                model=os.getenv("SELF_INSTRUCT_MODEL", "gpt-4"),
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.8,
            )
            payload = json.loads(response.choices[0].message.content)
            return payload.get("cases", [])[:target_count]
        except Exception:
            return []

    def _format_seed(self, seed_cases: List[Dict[str, Any]]) -> str:
        parts = []
        for idx, case in enumerate(seed_cases, 1):
            parts.append(
                f"Example {idx}:\n"
                f"Company: {case.get('company')}\n"
                f"Industry: {case.get('industry')}\n"
                f"Facts: {case.get('facts')}\n"
                f"CoT: {case.get('cot')}\n"
                f"Decision: {case.get('decision')}\n"
            )
        return "\n".join(parts)
