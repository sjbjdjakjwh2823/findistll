from vendor.findistill.services.spreadsheet_parser import SpreadsheetParser


def test_years_detected_from_columns_csv(tmp_path):
    csv = "Metric,Q4 2024,Q4 2023\nRevenue,1,2\n"
    p = tmp_path / "s.csv"
    p.write_text(csv, encoding="utf-8")
    parser = SpreadsheetParser(p.read_bytes(), file_type="csv")
    facts = parser.parse()
    assert len(facts) > 0
    periods = {f.period for f in facts}
    assert "CY" in periods
    assert "PY_2023" in periods

