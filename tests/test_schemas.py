"""Validation tests for KnowledgeOps HTTP contracts."""

import pytest
from pydantic import ValidationError

from knowledgeops.schemas import KnowledgeBaseCreate, TextDocumentCreate


def test_knowledge_base_create_uses_defaults():
    """Optional request fields should receive business-safe defaults."""
    payload = KnowledgeBaseCreate(name="Platform Documentation")

    assert payload.description == ""
    assert payload.department == "general"


def test_text_document_rejects_empty_content():
    """Uploading an empty document would create a useless RAG index entry."""
    with pytest.raises(ValidationError):
        TextDocumentCreate(
            source_name="empty.md",
            content="",
        )