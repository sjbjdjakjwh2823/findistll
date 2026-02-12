from __future__ import annotations

import os
import re
from typing import List


_SECRET_PATTERNS = [
    # Google API key style
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    # Notion token style seen in this project
    re.compile(r"ntn_[0-9A-Za-z]{10,}"),
    # JWT-like
    re.compile(r"eyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}"),
]


def _redact_line(line: str) -> str:
    out = line
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def tail_file(path: str, *, lines: int = 200, max_bytes: int = 512 * 1024) -> List[str]:
    """
    Read last N lines of a log file with a bounded max_bytes read.
    """
    if not path:
        return []
    if not os.path.exists(path):
        return []
    if lines <= 0:
        return []

    size = os.path.getsize(path)
    start = max(0, size - max_bytes)
    with open(path, "rb") as f:
        f.seek(start)
        buf = f.read()
    text = buf.decode("utf-8", errors="replace")
    parts = text.splitlines()
    return [_redact_line(p) for p in parts[-lines:]]

