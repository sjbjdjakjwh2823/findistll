import pytest

from app.services.unified_engine import UnifiedConversionEngine


@pytest.mark.asyncio
async def test_unified_engine_csv_conversion():
    engine = UnifiedConversionEngine()
    csv_bytes = b"Metric,2024,2023\nRevenue,100,90\nNet Income,10,8\n"
    result = await engine.convert_document(
        file_bytes=csv_bytes,
        filename="sample.csv",
        mime_type="text/csv",
        source="upload",
        run_snorkel=False,
    )

    assert result.extracted
    assert result.distill.facts
    assert result.distill.metadata.get("filename") == "sample.csv"
