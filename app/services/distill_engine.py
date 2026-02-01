import os
import base64
from typing import Any, Dict

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
            from vendor.findistill.services.ingestion import ingestion_service
            from vendor.findistill.services.normalizer import normalizer
        except Exception as exc:
            return DistillResult(
                facts=[],
                cot_markdown="",
                metadata={"error": f"findistill import failed: {exc}"}
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

        metadata = {
            "source": document.get("source", "upload"),
            "doc_id": document.get("doc_id", ""),
            "title": normalized.get("title"),
            "summary": normalized.get("summary"),
        }

        return DistillResult(facts=facts, cot_markdown=cot, metadata=metadata)
