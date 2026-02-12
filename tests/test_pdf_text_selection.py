from vendor.findistill.services import unstructured_parser


def test_text_sufficient_threshold():
    assert not unstructured_parser._text_sufficient("")
    assert not unstructured_parser._text_sufficient("short", min_chars=10)
    assert unstructured_parser._text_sufficient("x" * 10, min_chars=10)


def test_select_pdf_text_content_prefers_text_layer():
    text_layer = "x" * 300
    ocr_text = "ocr content"
    selected = unstructured_parser._select_pdf_text_content(text_layer, ocr_text)
    assert selected == text_layer


def test_select_pdf_text_content_falls_back_to_ocr():
    text_layer = "tiny"
    ocr_text = "ocr content"
    selected = unstructured_parser._select_pdf_text_content(text_layer, ocr_text)
    assert selected == ocr_text
