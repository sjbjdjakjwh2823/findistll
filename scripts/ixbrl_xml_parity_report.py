import argparse
import asyncio
import json
import mimetypes
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

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
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def norm_decimal(x: Any) -> Optional[Decimal]:
    if x is None:
        return None
    if isinstance(x, Decimal):
        return x
    s = str(x).strip()
    if not s:
        return None
    # Facts may contain already-normalized strings, including scientific notation.
    s = s.replace(",", "")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def dims_key(dims: Any) -> str:
    if not dims:
        return "{}"
    if isinstance(dims, dict):
        try:
            return json.dumps(dims, sort_keys=True, ensure_ascii=False)
        except Exception:
            return str(dims)
    return str(dims)


@dataclass(frozen=True)
class FactKey:
    concept: str
    period: str
    unit: str
    currency: str
    dimensions: str

    def as_tuple(self) -> Tuple[str, str, str, str, str]:
        return (self.concept, self.period, self.unit, self.currency, self.dimensions)


def build_fact_index(facts: Iterable[Dict[str, Any]]) -> Dict[FactKey, Dict[str, Any]]:
    out: Dict[FactKey, Dict[str, Any]] = {}
    for f in facts:
        concept = str(f.get("concept") or "").strip()
        period = str(f.get("period") or "").strip()
        unit = str(f.get("unit") or "").strip()
        currency = str(f.get("currency") or "").strip()
        dims = dims_key(f.get("dimensions"))
        if not concept or not period:
            continue
        k = FactKey(concept=concept, period=period, unit=unit, currency=currency, dimensions=dims)
        # Keep the first occurrence to preserve determinism.
        out.setdefault(k, f)
    return out


def compare_indexes(
    left: Dict[FactKey, Dict[str, Any]],
    right: Dict[FactKey, Dict[str, Any]],
    *,
    rel_tol: Decimal = Decimal("0.0000001"),
    abs_tol: Decimal = Decimal("0.0000001"),
) -> Dict[str, Any]:
    left_keys = set(left.keys())
    right_keys = set(right.keys())
    common = sorted(left_keys & right_keys, key=lambda k: k.as_tuple())

    matched = 0
    mismatched: List[Dict[str, Any]] = []
    for k in common:
        lv = norm_decimal(left[k].get("value"))
        rv = norm_decimal(right[k].get("value"))
        if lv is None or rv is None:
            # Can't compare; treat as mismatch, but record.
            mismatched.append(
                {
                    "key": k.as_tuple(),
                    "left_value": left[k].get("value"),
                    "right_value": right[k].get("value"),
                    "reason": "non_numeric_value",
                }
            )
            continue

        diff = abs(lv - rv)
        ok = diff <= abs_tol
        if not ok:
            denom = max(abs(lv), abs(rv), Decimal("1"))
            ok = (diff / denom) <= rel_tol

        if ok:
            matched += 1
        else:
            mismatched.append(
                {
                    "key": k.as_tuple(),
                    "left_value": str(lv),
                    "right_value": str(rv),
                    "abs_diff": str(diff),
                }
            )

    only_left = sorted(left_keys - right_keys, key=lambda k: k.as_tuple())
    only_right = sorted(right_keys - left_keys, key=lambda k: k.as_tuple())

    return {
        "left_count": len(left),
        "right_count": len(right),
        "common_count": len(common),
        "matched_count": matched,
        "mismatched_count": len(mismatched),
        "only_left_count": len(only_left),
        "only_right_count": len(only_right),
        "only_left_sample": [k.as_tuple() for k in only_left[:40]],
        "only_right_sample": [k.as_tuple() for k in only_right[:40]],
        "mismatched_sample": mismatched[:60],
    }


async def convert(engine: UnifiedConversionEngine, path: Path) -> Dict[str, Any]:
    mime = guess_mime(path)
    file_bytes = path.read_bytes()
    result = await engine.convert_document(
        file_bytes=file_bytes,
        filename=path.name,
        mime_type=mime,
        source="parity_report",
        document=None,
        run_snorkel=False,
    )
    facts = result.distill.facts or []
    return {
        "path": str(path),
        "mime": mime,
        "fact_count": len(facts),
        "facts": facts,
        "exports": sorted([k for k in result.exports.keys() if not k.endswith("_error")]),
        "exports_errors": {k: v for k, v in result.exports.items() if k.endswith("_error")},
    }


def write_md(report_path: Path, payload: Dict[str, Any]) -> None:
    left = payload["left"]
    right = payload["right"]
    cmp = payload["compare"]
    lines: List[str] = []
    lines.append("# iXBRL vs XML Parity Report")
    lines.append("")
    lines.append(f"- Generated: `{payload['generated_at']}`")
    lines.append(f"- Left: `{left['path']}` (`{left['mime']}`, facts={left['fact_count']})")
    lines.append(f"- Right: `{right['path']}` (`{right['mime']}`, facts={right['fact_count']})")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- common keys: `{cmp['common_count']}`")
    lines.append(f"- matched: `{cmp['matched_count']}`")
    lines.append(f"- mismatched: `{cmp['mismatched_count']}`")
    lines.append(f"- only_left: `{cmp['only_left_count']}`")
    lines.append(f"- only_right: `{cmp['only_right_count']}`")
    lines.append("")
    lines.append("## Samples")
    lines.append("")
    lines.append("### mismatched_sample")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(cmp["mismatched_sample"], ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("### only_left_sample")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(cmp["only_left_sample"], ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("### only_right_sample")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(cmp["only_right_sample"], ensure_ascii=False, indent=2))
    lines.append("```")
    report_path.write_text("\n".join(lines), encoding="utf-8")


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--left", required=True, help="iXBRL (.htm/.html) or XML (.xml) path")
    p.add_argument("--right", required=True, help="XML (.xml) or iXBRL (.htm/.html) path")
    p.add_argument(
        "--out",
        default="/Users/leesangmin/.openclaw/workspace/preciso/artifacts/parity_reports",
        help="output directory",
    )
    args = p.parse_args()

    left_path = Path(args.left)
    right_path = Path(args.right)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    engine = UnifiedConversionEngine()
    left = await convert(engine, left_path)
    right = await convert(engine, right_path)

    left_index = build_fact_index(left["facts"])
    right_index = build_fact_index(right["facts"])
    compare = compare_indexes(left_index, right_index)

    payload = {
        "generated_at": ts,
        "left": {k: v for k, v in left.items() if k != "facts"},
        "right": {k: v for k, v in right.items() if k != "facts"},
        "compare": compare,
    }

    (run_dir / "report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_md(run_dir / "report.md", payload)

    print(json.dumps(payload["compare"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
