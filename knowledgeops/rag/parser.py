"""Document parsing primitives used before chunking and indexing."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


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

    if suffix == ".pdf":
        return "pdf"

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


def parse_pdf_document(content: bytes, source_name: str) -> ParsedDocument:
    """Extract and normalize text from every page of a PDF document."""
    if not isinstance(content, bytes):
        raise TypeError("PDF content must be bytes.")

    if not content:
        raise ValueError("PDF content cannot be empty.")

    try:
        reader = PdfReader(BytesIO(content))
        page_texts = [
            page.extract_text() or ""
            for page in reader.pages
        ]
    except PdfReadError as error:
        raise ValueError("Invalid PDF document.") from error

    normalized = "\n".join(page_texts)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n").strip()

    if not normalized:
        raise ValueError("PDF document does not contain extractable text.")

    return ParsedDocument(
        text=normalized,
        source_name=source_name,
        source_type="pdf",
        metadata={
            "source_name": source_name,
            "source_type": "pdf",
            "page_count": str(len(reader.pages)),
        },
    )