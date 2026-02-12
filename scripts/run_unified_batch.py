import argparse
import asyncio
import json
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.unified_engine import UnifiedConversionEngine

try:
    from app.core.secret_loader import load_secrets_from_file

    load_secrets_from_file()
except Exception:
    pass


def guess_mime(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".pdf"):
        return "application/pdf"
    if name.endswith(".csv"):
        return "text/csv"
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if name.endswith(".xml") or name.endswith(".xbrl"):
        return "application/xml"
    if name.endswith(".html") or name.endswith(".htm") or name.endswith(".xhtml"):
        return "text/html"
    if name.endswith(".json"):
        return "application/json"
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def safe_write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


async def convert_one(engine: UnifiedConversionEngine, path: Path, out_dir: Path) -> Dict[str, Any]:
    mime = guess_mime(path)
    raw_bytes: Optional[bytes] = None
    document: Optional[Dict[str, Any]] = None

    if mime == "application/json":
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            parsed = json.loads(path.read_text(errors="ignore"))
        # Treat JSON as structured payload so we don't depend on vendor ingestion supporting JSON.
        document = {"content": parsed}
    else:
        raw_bytes = path.read_bytes()

    result = await engine.convert_document(
        file_bytes=raw_bytes,
        filename=path.name,
        mime_type=mime,
        source="batch_test",
        document=document,
        run_snorkel=False,
    )

    facts = result.distill.facts or []
    norm_tables = (result.normalized or {}).get("tables", []) or []
    math_derived = (result.mathematics or {}).get("derived", {}) or {}
    math_vg = (result.mathematics or {}).get("visibility_graph", {}) or {}

    summary = {
        "file": path.name,
        "path": str(path),
        "mime": mime,
        "fact_count": len(facts),
        "table_count": len(norm_tables),
        "exports": sorted([k for k in result.exports.keys() if not k.endswith("_error")]),
        "exports_errors": {k: v for k, v in result.exports.items() if k.endswith("_error")},
        "mathematics": {
            "derived_keys": len(math_derived),
            "visibility_graph_keys": len(math_vg),
            "error": (result.mathematics or {}).get("error"),
        },
        "notes": [],
    }

    if summary["fact_count"] == 0:
        summary["notes"].append("no_facts")
    if summary["table_count"] == 0:
        summary["notes"].append("no_tables")
    if summary["mathematics"]["derived_keys"] == 0:
        summary["notes"].append("no_math_series")
    if summary["exports_errors"]:
        summary["notes"].append("export_errors")

    file_dir = out_dir / path.stem
    file_dir.mkdir(parents=True, exist_ok=True)
    safe_write_json(file_dir / "summary.json", summary)
    safe_write_json(file_dir / "facts_sample.json", facts[:80])
    derived_keys = list(math_derived.keys())[:10]
    safe_write_json(file_dir / "math_derived_sample.json", {k: math_derived[k] for k in derived_keys})

    return summary


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--out", default="/Users/leesangmin/.openclaw/workspace/preciso/artifacts/unified_batch")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    engine = UnifiedConversionEngine()
    summaries: List[Dict[str, Any]] = []
    for p in args.paths:
        path = Path(p)
        if not path.exists():
            summaries.append({"file": str(path), "error": "not_found"})
            continue
        summaries.append(await convert_one(engine, path, out_dir))

    safe_write_json(out_dir / "batch_summary.json", summaries)
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
