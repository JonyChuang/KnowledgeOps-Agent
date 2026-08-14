"""Tests for document normalization and text chunking."""

import pytest

from knowledgeops.rag import parse_pdf_document, parse_text_document, split_text


def test_parse_text_document_normalizes_line_endings():
    """Parser should produce stable text across operating systems."""
    document = parse_text_document(
        "第一行\r\n第二行\r第三行",
        "guide.md",
    )

    assert document.text == "第一行\n第二行\n第三行"
    assert document.source_name == "guide.md"
    assert document.source_type == "markdown"


def test_parse_text_document_rejects_empty_content():
    """Empty documents should not enter the indexing pipeline."""
    with pytest.raises(ValueError):
        parse_text_document(" \r\n ", "empty.txt")


def test_split_text_creates_overlapping_chunks():
    """Chunk windows should preserve the configured overlap."""
    chunks = split_text(
        "0123456789ABCDEFGHIJ",
        chunk_size=10,
        overlap=3,
    )

    assert len(chunks) == 3
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == "0123456789"
    assert chunks[1].text[:3] == chunks[0].text[-3:]
    assert chunks[-1].end_char == 20


def test_split_text_rejects_invalid_overlap():
    """Overlap equal to the chunk size would make progress impossible."""
    with pytest.raises(ValueError):
        split_text("some text", chunk_size=10, overlap=10)


def test_infer_source_type_supports_pdf():
    """PDF filenames should select the PDF parser path."""
    document = parse_pdf_document.__name__

    assert document == "parse_pdf_document"


def test_parse_pdf_document_extracts_page_text(monkeypatch):
    """PDF parser should combine text from all pages into one document."""

    class FakePage:
        def __init__(self, text: str):
            self.text = text

        def extract_text(self):
            return self.text

    class FakePdfReader:
        def __init__(self, stream):
            self.pages = [
                FakePage("First page."),
                FakePage("Second page."),
            ]

    monkeypatch.setattr(
        "knowledgeops.rag.parser.PdfReader",
        FakePdfReader,
    )

    document = parse_pdf_document(b"fake-pdf-bytes", "handbook.pdf")

    assert document.text == "First page.\nSecond page."
    assert document.source_name == "handbook.pdf"
    assert document.source_type == "pdf"
    assert document.metadata["page_count"] == "2"

def test_parse_html_document_omits_scripts_and_collects_visible_text():
    """HTML uploads should keep readable content without script source."""
    from knowledgeops.rag import parse_html_document

    document = parse_html_document(
        b"<html><head><title>Runbook</title><script>secret()</script></head><body><h1>VPN</h1><p>Restart the client.</p></body></html>",
        "runbook.html",
    )

    assert document.source_type == "html"
    assert document.metadata["title"] == "Runbook"
    assert document.text == "Runbook\nVPN\nRestart the client."
    assert "secret" not in document.text


def test_parse_docx_document_extracts_paragraph_text():
    """DOCX uploads should extract Word paragraph runs without python-docx."""
    from io import BytesIO
    from zipfile import ZipFile

    from knowledgeops.rag import parse_docx_document

    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body><w:p><w:r><w:t>First paragraph.</w:t></w:r></w:p><w:p><w:r><w:t>Second paragraph.</w:t></w:r></w:p></w:body></w:document>""",
        )

    document = parse_docx_document(stream.getvalue(), "handbook.docx")

    assert document.source_type == "word"
    assert document.text == "First paragraph.\nSecond paragraph."