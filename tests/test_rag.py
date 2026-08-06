"""Tests for document normalization and text chunking."""

import pytest

from knowledgeops.rag import parse_text_document, split_text


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