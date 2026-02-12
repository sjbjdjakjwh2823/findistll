#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


BOOTSTRAP = Path(__file__).resolve().parents[1] / "supabase_bootstrap_preciso.sql"
OUT_MD = Path(__file__).resolve().parents[1] / "docs" / "SUPABASE_TABLES_INVENTORY.md"


BEGIN_RE = re.compile(r"^-- >>> BEGIN (?P<section>.+?)\s*$")
END_RE = re.compile(r"^-- <<< END (?P<section>.+?)\s*$")
CREATE_TABLE_RE = re.compile(
    r"^CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>(?:public\.)?[a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TableRef:
    name: str
    section: str
    lineno: int


def _read_lines(p: Path) -> List[str]:
    return p.read_text(encoding="utf-8").splitlines()


def parse_inventory(lines: List[str]) -> List[TableRef]:
    current_section = "unscoped"
    refs: List[TableRef] = []
    for i, line in enumerate(lines, start=1):
        m = BEGIN_RE.match(line)
        if m:
            current_section = m.group("section").strip()
            continue
        m = END_RE.match(line)
        if m:
            current_section = "unscoped"
            continue
        m = CREATE_TABLE_RE.match(line.strip())
        if m:
            name = m.group("name").strip()
            # normalize: strip "public." to keep a stable canonical name
            if name.lower().startswith("public."):
                name = name.split(".", 1)[1]
            refs.append(TableRef(name=name, section=current_section, lineno=i))
    return refs


def _dedupe(refs: List[TableRef]) -> Tuple[List[TableRef], Dict[str, List[TableRef]]]:
    by_name: Dict[str, List[TableRef]] = {}
    for r in refs:
        by_name.setdefault(r.name, []).append(r)
    # keep first appearance as primary
    primary = [v[0] for v in sorted(by_name.values(), key=lambda vv: vv[0].lineno)]
    return primary, by_name


def render_md(primary: List[TableRef], by_name: Dict[str, List[TableRef]]) -> str:
    lines: List[str] = []
    lines.append("# Supabase Tables Inventory (Source of Truth: supabase_bootstrap_preciso.sql)")
    lines.append("")
    lines.append("이 문서는 `supabase_bootstrap_preciso.sql`에서 생성되는 테이블을 섹션(작업대/워크스트림)별로 자동 추출한 인벤토리입니다.")
    lines.append("")
    lines.append("## How To Update")
    lines.append("- 새로운 작업대에서 테이블을 추가하면 반드시 `supabase_bootstrap_preciso.sql`에 섹션(`-- >>> BEGIN ...`)으로 포함시키고")
    lines.append("- `python3 scripts/supabase_table_inventory.py`를 실행해 이 문서를 갱신합니다.")
    lines.append("")

    # Section -> tables
    by_section: Dict[str, List[TableRef]] = {}
    for r in primary:
        by_section.setdefault(r.section, []).append(r)

    lines.append("## Sections")
    for section in sorted(by_section.keys()):
        lines.append(f"- `{section}`: {len(by_section[section])} tables")
    lines.append("")

    for section in sorted(by_section.keys()):
        lines.append(f"## {section}")
        for r in sorted(by_section[section], key=lambda x: x.name):
            dups = by_name.get(r.name, [])
            dup_note = ""
            if len(dups) > 1:
                dup_note = f" (defined {len(dups)}x)"
            lines.append(f"- `{r.name}`{dup_note} (bootstrap line {r.lineno})")
        lines.append("")

    # Duplicate summary
    dup_names = sorted([name for name, rs in by_name.items() if len(rs) > 1])
    if dup_names:
        lines.append("## Duplicates (Needs Review)")
        lines.append("동일 테이블이 여러 섹션에서 생성되고 있습니다. 부트스트랩 중복 정의를 정리하는 것이 좋습니다.")
        lines.append("")
        for name in dup_names:
            refs = by_name[name]
            locs = ", ".join([f"{r.section}@{r.lineno}" for r in refs])
            lines.append(f"- `{name}`: {locs}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    if not BOOTSTRAP.exists():
        print(f"ERROR: missing {BOOTSTRAP}", file=sys.stderr)
        return 2
    lines = _read_lines(BOOTSTRAP)
    refs = parse_inventory(lines)
    primary, by_name = _dedupe(refs)
    md = render_md(primary, by_name)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"Wrote {OUT_MD} ({len(primary)} tables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

