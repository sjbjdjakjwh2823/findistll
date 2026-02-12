#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECTION_FILE = ROOT / "vendor" / "finrobot" / "data_source" / "filings_src" / "prepline_sec_filings" / "api" / "section.py"


def _ensure_logging(section_text: str) -> str:
    if "import logging" not in section_text:
        section_text = section_text.replace("import csv\n", "import csv\nimport logging\n")
    if "logger = logging.getLogger(__name__)" not in section_text:
        section_text = section_text.replace(
            "router = APIRouter()\n\n",
            "router = APIRouter()\nlogger = logging.getLogger(__name__)\n\n",
        )
    return section_text


def _patch_sigalrm(section_text: str) -> str:
    section_text = re.sub(
        r"except ValueError:\n\s+pass",
        "except ValueError as exc:\n            logger.debug(\"SIGALRM setup skipped (non-main thread): %s\", exc)",
        section_text,
    )
    section_text = re.sub(
        r"except ValueError:\n\s+pass",
        "except ValueError as exc:\n            logger.debug(\"SIGALRM teardown skipped (non-main thread): %s\", exc)",
        section_text,
        count=1,
    )
    return section_text


def patch_section() -> bool:
    if not SECTION_FILE.exists():
        return False
    original = SECTION_FILE.read_text(encoding="utf-8")
    updated = _ensure_logging(original)
    updated = _patch_sigalrm(updated)
    if updated != original:
        SECTION_FILE.write_text(updated, encoding="utf-8")
        return True
    return False


if __name__ == "__main__":
    changed = patch_section()
    print(f"patched={changed} file={SECTION_FILE}")
