from __future__ import annotations

import re


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{4}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def redact_sensitive(text: str) -> str:
    if not text:
        return text
    redacted = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    redacted = PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    redacted = SSN_RE.sub("[REDACTED_SSN]", redacted)
    return redacted


def scan_sensitive(text: str) -> dict:
    return {
        "emails": len(EMAIL_RE.findall(text or "")),
        "phones": len(PHONE_RE.findall(text or "")),
        "ssn": len(SSN_RE.findall(text or "")),
    }
