#!/usr/bin/env python3
from __future__ import annotations

"""
Fetch a real iXBRL HTML file from SEC EDGAR and save it locally.

Why: We need regression testing on true iXBRL inputs to reach "XML-grade" quality.

This script:
1) Fetches recent filings list from data.sec.gov submissions endpoint
2) Picks the most recent filing accession
3) Downloads index.json for that accession
4) Finds a candidate .htm/.html that contains iXBRL tags (ix:nonFraction etc)
5) Downloads that file to /tmp and prints the path

Notes:
- SEC requires a descriptive User-Agent. Set SEC_USER_AGENT env var.
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Optional

import requests


def _ua() -> str:
    ua = (os.getenv("SEC_USER_AGENT") or "").strip()
    if ua:
        return ua
    # Fallback UA, still descriptive. Replace with your email for production.
    return "Preciso/1.0 (contact: dev@preciso.local)"


def _get_json(url: str) -> dict:
    r = requests.get(url, headers={"User-Agent": _ua()}, timeout=60)
    r.raise_for_status()
    return r.json()


def _get_bytes(url: str) -> bytes:
    r = requests.get(url, headers={"User-Agent": _ua()}, timeout=60)
    r.raise_for_status()
    return r.content


def _cik10(cik: str) -> str:
    digits = re.sub(r"\\D", "", cik)
    return digits.zfill(10)


def _pick_recent_accession(submissions: dict) -> Optional[str]:
    recent = (submissions.get("filings") or {}).get("recent") or {}
    accessions = recent.get("accessionNumber") or []
    forms = recent.get("form") or []
    if not accessions:
        return None
    # Prefer primary reporting forms that usually carry Inline XBRL.
    preferred = {"10-Q", "10-K", "20-F", "40-F"}
    for i, acc in enumerate(accessions):
        try:
            form = str(forms[i]) if i < len(forms) else ""
        except Exception:
            form = ""
        if form in preferred:
            return str(acc).replace("-", "")
    # Fallback: first accession.
    return str(accessions[0]).replace("-", "")


def _find_ixbrl_doc(index_json: dict, base: str) -> Optional[str]:
    items = index_json.get("directory", {}).get("item", []) or []
    # Prefer primary docs first (by name order) but verify by content sniff.
    htmls = [it.get("name") for it in items if str(it.get("name", "")).lower().endswith((".htm", ".html", ".xhtml"))]
    for name in htmls:
        if not name:
            continue
        url = f"{base}/{name}"
        try:
            head = _get_bytes(url)[:200_000].lower()
        except Exception:
            continue
        # Require explicit ix namespace usage to avoid grabbing index/listing pages.
        if b"ix:nonfraction" in head or b"ix:nonnumeric" in head or b"xmlns:ix" in head:
            return str(name)
    return None


def _find_instance_xml(index_json: dict, base: str) -> Optional[str]:
    items = index_json.get("directory", {}).get("item", []) or []
    xmls = [it.get("name") for it in items if str(it.get("name", "")).lower().endswith(".xml")]
    for name in xmls:
        if not name:
            continue
        url = f"{base}/{name}"
        try:
            head = _get_bytes(url)[:200_000].lower()
        except Exception:
            continue
        if b"<xbrli:xbrl" in head or b":xbrl" in head:
            return str(name)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cik", required=True, help="Company CIK (e.g. 789019 or 0000789019)")
    ap.add_argument("--accession", default="", help="Accession without dashes (optional). If omitted, uses most recent filing.")
    ap.add_argument(
        "--out",
        default="/tmp/preciso_ixbrl_sample.html",
        help=(
            "Output path. If endswith .html/.htm, writes iXBRL there and writes XML next to it "
            "(same path but .xml). If a directory, writes ixbrl.html and instance.xml inside."
        ),
    )
    args = ap.parse_args()

    cik10 = _cik10(args.cik)
    submissions = _get_json(f"https://data.sec.gov/submissions/CIK{cik10}.json")
    accession = re.sub(r"\\D", "", args.accession) if args.accession else ""
    if not accession:
        picked = _pick_recent_accession(submissions)
        if not picked:
            raise SystemExit("No recent accessions found for this CIK")
        accession = picked

    cik_int = str(int(cik10))  # edgar path uses non-zero-padded int
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}"
    index_json = _get_json(f"{base}/index.json")
    doc = _find_ixbrl_doc(index_json, base)
    if not doc:
        raise SystemExit("No iXBRL-like .htm/.html found in filing directory")

    out_path = Path(args.out)
    if out_path.suffix.lower() in {".html", ".htm", ".xhtml"}:
        ixbrl_path = out_path
        xml_path = out_path.with_suffix(".xml")
    else:
        out_path.mkdir(parents=True, exist_ok=True)
        ixbrl_path = out_path / "ixbrl.html"
        xml_path = out_path / "instance.xml"

    ixbrl_path.write_bytes(_get_bytes(f"{base}/{doc}"))

    xml_name = _find_instance_xml(index_json, base)
    if xml_name:
        xml_path.write_bytes(_get_bytes(f"{base}/{xml_name}"))

    print(json.dumps({"ixbrl": str(ixbrl_path), "xml": str(xml_path) if xml_name else ""}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
