from vendor.findistill.services.spreadsheet_parser import SpreadsheetParser


def test_find_years_does_not_false_positive_from_numeric_cells(tmp_path):
    # Regression: row scan should not extract "2040" from a numeric value like 20403.0.
    # We build a minimal CSV where one numeric cell contains 20403.
    csv = (
        'Metric,"Three Months Ended Sept 30, 2024","Three Months Ended Sept 30, 2023"\n'
        "Costs and expenses,23239,20403\n"
    )
    p = tmp_path / "sample.csv"
    p.write_text(csv, encoding="utf-8")
    parser = SpreadsheetParser(p.read_bytes(), file_type="csv")
    facts = parser.parse()
    # We should still get facts from the values (parser runs end-to-end).
    assert len(facts) > 0
    # And the derived periods should be CY and PY_2023 (not PY_2040).
    periods = {f.period for f in facts}
    assert "CY" in periods
    assert "PY_2023" in periods
    assert "PY_2040" not in periods
