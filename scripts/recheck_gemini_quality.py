import asyncio
import json
from pathlib import Path

from app.services.unified_engine import UnifiedConversionEngine


async def run_one(path: Path, mime: str, out_dir: Path) -> None:
    engine = UnifiedConversionEngine()
    result = await engine.convert_document(
        file_bytes=path.read_bytes(),
        filename=path.name,
        mime_type=mime,
        source="gemini_recheck",
        run_snorkel=False,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "file": path.name,
        "mime": mime,
        "fact_count": len(result.distill.facts or []),
        "table_count": len((result.normalized or {}).get("tables", []) or []),
        "math_derived_keys": len((result.mathematics or {}).get("derived", {}) or {}),
        "gemini_used": (result.normalized or {}).get("metadata", {}).get("gemini_used", False),
    }
    (out_dir / f"{path.stem}_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    (out_dir / f"{path.stem}_facts.json").write_text(json.dumps((result.distill.facts or [])[:80], ensure_ascii=False, indent=2))


async def main() -> None:
    base_out = Path("/Users/leesangmin/.openclaw/workspace/preciso/artifacts/gemini_recheck")
    pdf_path = Path("/Users/leesangmin/.openclaw/workspace/preciso/artifacts/mathmatics/10-Q4-2024-As-Filed.pdf")
    await run_one(pdf_path, "application/pdf", base_out)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
