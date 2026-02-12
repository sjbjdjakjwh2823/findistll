import asyncio
import json
from pathlib import Path

from app.services.unified_engine import UnifiedConversionEngine


async def main():
    pdf_path = Path("/Users/leesangmin/.openclaw/workspace/preciso/artifacts/mathmatics/10-Q4-2024-As-Filed.pdf")
    data = pdf_path.read_bytes()

    engine = UnifiedConversionEngine()
    result = await engine.convert_document(
        file_bytes=data,
        filename=pdf_path.name,
        mime_type="application/pdf",
        source="test_pdf",
        run_snorkel=False,
    )

    out_dir = Path("/Users/leesangmin/.openclaw/workspace/preciso/artifacts/mathmatics/out")
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "filename": pdf_path.name,
        "fact_count": len(result.distill.facts),
        "table_count": len((result.normalized or {}).get("tables", []) or []),
        "has_exports": sorted([k for k in result.exports.keys() if not k.endswith("_error")]),
        "has_mathematics": "error" not in (result.mathematics or {}),
        "math_series_keys": len((result.mathematics or {}).get("derived", {}) or {}),
    }

    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))

    # Save a small sample of facts for manual inspection.
    facts_sample = result.distill.facts[:50]
    (out_dir / "facts_sample.json").write_text(json.dumps(facts_sample, ensure_ascii=False, indent=2))

    # Save mathematics derived sample
    derived = (result.mathematics or {}).get("derived", {})
    derived_keys = list(derived.keys())[:5]
    derived_sample = {k: derived[k] for k in derived_keys}
    (out_dir / "math_derived_sample.json").write_text(json.dumps(derived_sample, ensure_ascii=False, indent=2))

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
