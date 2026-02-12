from __future__ import annotations

import re
from datetime import datetime
from typing import Optional


def to_date_ymd(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return None


def normalize_period_loose(period: Optional[str], *, doc_year: Optional[str] = None) -> Optional[str]:
    """
    Best-effort period normalization for external partner payloads and causal surfaces.
    Returns an ISO date (YYYY-MM-DD) when possible.
    """
    if not period:
        return None
    text = str(period).strip()
    if not text:
        return None

    # ISO datetime -> date
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)

    # Common date formats
    direct = to_date_ymd(text)
    if direct:
        return direct

    # Normalize separators.
    t = text.replace("/", "-").replace(".", "-").strip()

    # Year only -> year-end.
    if re.match(r"^\d{4}$", t):
        return f"{t}-12-31"

    # Year-month -> end of month (fallback to 28 if calendar fails).
    m = re.match(r"^(\d{4})-(\d{1,2})$", t)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))
        try:
            import calendar
            day = calendar.monthrange(year, month)[1]
        except Exception:
            day = 28
        return f"{year}-{month:02d}-{day:02d}"

    # Quarter patterns: YYYYQ4, YYYY-Q4, Q4 YYYY
    q = re.match(r"^(\d{4})\s*[-_]?Q([1-4])$", t, re.IGNORECASE)
    if not q:
        q = re.match(r"^Q([1-4])\s*(\d{4})$", t, re.IGNORECASE)
        if q:
            year, qn = q.group(2), q.group(1)
            q = re.match(r"^(\d{4})\s*[-_]?Q([1-4])$", f"{year}Q{qn}", re.IGNORECASE)
    if q:
        year = int(q.group(1))
        qn = int(q.group(2))
        month = {1: 3, 2: 6, 3: 9, 4: 12}[qn]
        day = {3: 31, 6: 30, 9: 30, 12: 31}[month]
        return f"{year}-{month:02d}-{day:02d}"

    # Half-year patterns: YYYYH1, H1 YYYY
    h = re.match(r"^(\d{4})\s*[-_]?H([12])$", t, re.IGNORECASE)
    if not h:
        h = re.match(r"^H([12])\s*(\d{4})$", t, re.IGNORECASE)
        if h:
            year, hn = h.group(2), h.group(1)
            h = re.match(r"^(\d{4})\s*[-_]?H([12])$", f"{year}H{hn}", re.IGNORECASE)
    if h:
        year = int(h.group(1))
        hn = int(h.group(2))
        return f"{year}-06-30" if hn == 1 else f"{year}-12-31"

    # CY/PY tokens
    if t in ("CY", "PY") and doc_year:
        try:
            year = int(doc_year)
            if t == "PY":
                year -= 1
            return f"{year}-12-31"
        except Exception:
            return None

    return None
