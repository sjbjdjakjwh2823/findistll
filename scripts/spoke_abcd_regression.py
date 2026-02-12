#!/usr/bin/env python3
"""Regression check for Spoke A/B/C/D outputs."""

import asyncio
import json
import mimetypes
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from app.core.secret_loader import load_secrets_from_file

    load_secrets_from_file()
except Exception:
    pass

from vendor.findistill.services.ingestion import FileIngestionService
from vendor.findistill.services.exporter import exporter

FILES = [
    "/Users/leesangmin/Downloads/$REBXUEI.csv",
    "/Users/leesangmin/Downloads/$R7TFEW4.xlsx",
    "/Users/leesangmin/Downloads/$R6M10XT.xml",
    "/Users/leesangmin/Downloads/$RGA4E91.html",
]


def _detect_mime(fp: str, content: bytes) -> str:
    mime, _ = mimetypes.guess_type(fp)
    if fp.endswith(".pdf"):
        sniff = content.lstrip()[:20].lower()
        if sniff.startswith(b"<!doctype") or sniff.startswith(b"<html"):
            return "text/html"
    return mime or "application/octet-stream"


async def main() -> int:
    service = FileIngestionService()
    out = []
    for fp in FILES:
        p = Path(fp)
        if not p.exists():
            continue
        content = p.read_bytes()
        mime = _detect_mime(fp, content)
        result = await service.process_file(content, p.name, mime)
        facts = result.get("facts") or []
        tables = result.get("tables") or []
        qa = result.get("reasoning_qa") or []
        jsonl = result.get("jsonl_data") or []
        kg = exporter.to_kg_triples(result)

        out.append({
            "file": p.name,
            "file_type": (result.get("metadata") or {}).get("file_type"),
            "facts": len(facts),
            "tables": len(tables),
            "reasoning_qa": len(qa),
            "jsonl_data": len(jsonl),
            "kg_triples": len(kg),
        })

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
