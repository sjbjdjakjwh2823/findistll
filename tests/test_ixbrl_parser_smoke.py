import pytest

try:
    import bs4  # noqa: F401
except Exception:
    bs4 = None

from vendor.findistill.services.ixbrl_parser import IXBRLParser


def test_ixbrl_parser_extracts_nonfraction_with_namespace_variants():
    if bs4 is None:
        pytest.skip("beautifulsoup4 not installed in this environment")
    # Minimal inline XBRL-like HTML with namespace-like tags.
    html = b"""
    <html>
      <body>
        <ix:resources>
          <xbrli:context id="C1">
            <xbrli:period><xbrli:instant>2024-12-31</xbrli:instant></xbrli:period>
          </xbrli:context>
          <xbrli:unit id="U1"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
        </ix:resources>
        <ix:nonFraction name="us-gaap:Revenues" contextRef="C1" unitRef="U1" decimals="-3" scale="6">123</ix:nonFraction>
      </body>
    </html>
    """
    parser = IXBRLParser(html)
    facts = parser.parse()
    assert len(facts) >= 1
    f0 = facts[0]
    assert getattr(f0, "concept", None)
    assert getattr(f0, "period", None) == "2024-12-31"
