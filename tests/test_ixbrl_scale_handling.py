from __future__ import annotations


import pytest


@pytest.mark.asyncio
async def test_ixbrl_scale_and_no_double_normalize() -> None:
    """
    Regression: Inline XBRL facts often display values with ix:scale (e.g., scale=6 for millions).
    We must:
    1) apply the scale so downstream normalized value is correct (billions convention)
    2) not re-apply ScaleProcessor again in ingestion (which would shrink by 1e9 twice)
    """
    from vendor.findistill.services.ingestion import ingestion_service

    html = b"""<!doctype html>
<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:us-gaap="http://fasb.org/us-gaap/2025">
  <body>
    <ix:resources>
      <xbrli:context xmlns:xbrli="http://www.xbrl.org/2003/instance" id="C1">
        <xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000000000</xbrli:identifier></xbrli:entity>
        <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period>
      </xbrli:context>
      <xbrli:unit xmlns:xbrli="http://www.xbrl.org/2003/instance" id="U_USD">
        <xbrli:measure>iso4217:USD</xbrli:measure>
      </xbrli:unit>
    </ix:resources>
    <ix:nonFraction name="us-gaap:CashAndCashEquivalentsAtCarryingValue"
        contextRef="C1" unitRef="U_USD" scale="6" decimals="-6">24,296</ix:nonFraction>
  </body>
</html>
"""

    out = await ingestion_service.process_file(html, "sample.htm", "text/html")
    facts = out.get("facts") or []
    assert facts, "expected at least one fact"
    f0 = facts[0]
    assert f0.get("concept") in ("CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalentsAtCarryingValue".lower())
    # 24,296 (millions) => 24.296 billion
    assert abs(float(f0["value"]) - 24.296) < 1e-6

