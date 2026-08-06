"""Document parsing primitives used before chunking and indexing."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedDocument:
    """Normalized document text and metadata used by later RAG stages."""

    text: str
    source_name: str
    source_type: str
    metadata: dict[str, str]


def infer_source_type(source_name: str) -> str:
    """Infer a simple source type from the document filename."""
    suffix = Path(source_name).suffix.lower()

    # Markdown documents receive a specific type for future parser selection.
    if suffix in {".md", ".markdown"}:
        return "markdown"

    # Plain text is the safe fallback for unknown text-like extensions.
    return "text"


def parse_text_document(
    content: str,
    source_name: str,
    source_type: str | None = None,
) -> ParsedDocument:
    """Normalize a text document into the format expected by the chunker."""
    if not isinstance(content, str):
        raise TypeError("Document content must be a string.")

    # Reject empty documents before they create useless index tasks.
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValueError("Document content cannot be empty.")

    # Use the caller-provided type when available; otherwise infer it.
    resolved_type = source_type or infer_source_type(source_name)

    return ParsedDocument(
        text=normalized,
        source_name=source_name,
        source_type=resolved_type,
        metadata={
            "source_name": source_name,
            "source_type": resolved_type,
        },
    )