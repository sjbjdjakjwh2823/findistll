import json


def test_spoke_a_record_stable_id():
    from app.services.spoke_ab_service import SpokeABService

    svc = SpokeABService()
    base = dict(
        tenant_id="t1",
        doc_id="d1",
        case_id="c1",
        version="v1",
        instruction="inst",
        input_text="in",
        evidence_chunk_ids=["e1", "e2"],
        fact_refs=[{"entity": "X", "metric": "Revenue", "period_norm": "2024Q4"}],
        selfcheck={"confidence_score": 0.9},
        approval={"approved_by": "u1", "approved_at": "2026-02-09T00:00:00Z", "source": "test"},
    )
    r1 = svc.build_spoke_a_record(output_text="out1", **base)
    r2 = svc.build_spoke_a_record(output_text="out1", **base)
    r3 = svc.build_spoke_a_record(output_text="out2", **base)
    assert r1["id"] == r2["id"]
    assert r1["id"] != r3["id"]


def test_spoke_a_numeric_preservation_gate():
    from app.services.spoke_ab_service import SpokeABService
    from app.services.types import DistillResult

    svc = SpokeABService()
    distill = DistillResult(
        facts=[{"entity": "Acme", "metric": "Revenue", "period_norm": "2024", "value": "100"}],
        cot_markdown="## Notes\nRevenue is 100.",
        metadata={},
    )

    spoke_ok = svc.build_spoke_a_record(
        tenant_id="t1",
        doc_id="d1",
        case_id="c1",
        version="v1",
        instruction="inst",
        input_text="in",
        output_text=json.dumps({"revenue": 100}),
        evidence_chunk_ids=["e1", "e2"],
        fact_refs=[],
        selfcheck={"confidence_score": 0.9},
        approval={"approved_by": "u1", "approved_at": "2026-02-09T00:00:00Z", "source": "test"},
    )
    gates_ok = svc.evaluate_gates(spoke_a_record=spoke_ok, distill=distill)
    assert gates_ok.numeric_ok is True

    spoke_bad = dict(spoke_ok)
    spoke_bad["output"] = json.dumps({"revenue": 999})
    gates_bad = svc.evaluate_gates(spoke_a_record=spoke_bad, distill=distill)
    assert gates_bad.numeric_ok is False


def test_spoke_b_parquet_generation_roundtrip():
    from app.services.spoke_ab_service import SpokeABService
    from app.services.types import DistillResult
    import polars as pl
    import io

    svc = SpokeABService()
    distill = DistillResult(
        facts=[
            {"entity": "Acme", "metric": "Revenue", "period": "2024Q4", "period_norm": "2024Q4", "value": 100, "unit": "USD"},
            {"entity": "Acme", "metric": "Revenue", "period": "2024Q3", "period_norm": "2024Q3", "value": 80, "unit": "USD"},
        ],
        cot_markdown="",
        metadata={},
    )
    artifacts = svc.build_spoke_b_parquets(
        tenant_id="t1",
        doc_id="d1",
        distill=distill,
        normalized={"tables": []},
    )
    assert set(artifacts.keys()) == {"facts", "tables", "features"}
    assert len(artifacts["facts"]) > 20

    df = pl.read_parquet(io.BytesIO(artifacts["facts"]))
    assert "metric" in df.columns
    assert df.height >= 1


def test_spoke_b_tables_has_page_and_cell_indexes():
    from app.services.spoke_ab_service import SpokeABService
    from app.services.types import DistillResult
    import polars as pl
    import io

    svc = SpokeABService()
    distill = DistillResult(facts=[], cot_markdown="", metadata={})
    artifacts = svc.build_spoke_b_parquets(
        tenant_id="t1",
        doc_id="d1",
        distill=distill,
        normalized={
            "tables": [
                {
                    "name": "PDF Table p32",
                    "headers": ["Metric", "2024", "2023"],
                    "rows": [["Revenue", "100", "90"]],
                }
            ]
        },
    )
    df_tables = pl.read_parquet(io.BytesIO(artifacts["tables"]))
    assert "page" in df_tables.columns
    assert "row_idx" in df_tables.columns
    assert "col_idx" in df_tables.columns
    # Ensure page parsing works
    assert df_tables.select(pl.col("page").unique()).to_series().to_list() == ["32"]
