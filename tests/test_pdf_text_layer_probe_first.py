import sys

import pytest


@pytest.mark.asyncio
async def test_pdf_text_layer_probe_first_skips_ocr(monkeypatch):
    # Import module so we can monkeypatch internal helpers.
    import vendor.findistill.services.unstructured_parser as up

    # If OCR is invoked, this test must fail.
    async def _ocr_should_not_run(*_args, **_kwargs):
        raise AssertionError("OCR path should not run when text layer is sufficient and PDF_TEXT_LAYER_PROBE_FIRST=1")

    monkeypatch.setattr(up, "_extract_text_from_pdf_images_async", _ocr_should_not_run)
    monkeypatch.setattr(up, "_extract_tables_from_pdf", lambda *_args, **_kwargs: [])

    # Fake pypdf module: return a "reader" whose pages have extract_text.
    class _Page:
        def extract_text(self):
            return "Total revenues 100 90\nNet income 10 9\n"

    class _Reader:
        def __init__(self, *_args, **_kwargs):
            self.pages = [_Page()]

    class _PypdfModule:
        PdfReader = _Reader

    monkeypatch.setitem(sys.modules, "pypdf", _PypdfModule)

    monkeypatch.setenv("GEMINI_ENABLED", "0")
    monkeypatch.setenv("PDF_TEXT_LAYER_PROBE_FIRST", "1")
    monkeypatch.setenv("PDF_TEXT_MIN_CHARS", "5")
    monkeypatch.setenv("PDF_OCR_FIRST", "1")
    monkeypatch.setenv("PDF_OCR_FORCE", "1")

    parser = up.UnstructuredHTMLParser(gemini_client=object())
    facts, meta = await parser.parse(b"%PDF-1.4 dummy", "sample.pdf")
    assert isinstance(meta, dict)
    assert facts  # if text-layer was used, heuristic extraction should yield some facts

