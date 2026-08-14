"""Document parsing primitives used before chunking and indexing."""

from dataclasses import dataclass
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

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

    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".docx":
        return "word"
    if suffix in {".html", ".htm"}:
        return "html"

    # Plain text is the safe fallback for known text-like extensions.
    return "text"


def parse_text_document(
    content: str,
    source_name: str,
    source_type: str | None = None,
) -> ParsedDocument:
    """Normalize a text document into the format expected by the chunker."""
    if not isinstance(content, str):
        raise TypeError("Document content must be a string.")

    normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValueError("Document content cannot be empty.")

    resolved_type = source_type or infer_source_type(source_name)
    return ParsedDocument(
        text=normalized,
        source_name=source_name,
        source_type=resolved_type,
        metadata={"source_name": source_name, "source_type": resolved_type},
    )


def parse_pdf_document(content: bytes, source_name: str) -> ParsedDocument:
    """Extract and normalize text from every page of a PDF document."""
    if not isinstance(content, bytes):
        raise TypeError("PDF content must be bytes.")
    if not content:
        raise ValueError("PDF content cannot be empty.")

    try:
        reader = PdfReader(BytesIO(content))
        page_texts = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as error:
        raise ValueError("Invalid PDF document.") from error

    normalized = _normalize_extracted_text("\n".join(page_texts))
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


def parse_uploaded_document(content: bytes, source_name: str) -> ParsedDocument:
    """Extract text from a supported local file before indexing."""
    if not isinstance(content, bytes):
        raise TypeError("Uploaded document content must be bytes.")

    source_type = infer_source_type(source_name)
    if source_type == "pdf":
        return parse_pdf_document(content, source_name)
    if source_type == "word":
        return parse_docx_document(content, source_name)
    if source_type == "html":
        return parse_html_document(content, source_name)
    return parse_text_document(_decode_text_bytes(content), source_name, source_type)


class _HtmlTextExtractor(HTMLParser):
    """Collect readable text while skipping non-content HTML elements."""

    _ignored_tags = {"script", "style", "noscript", "template", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self._title_depth = 0
        self._title_parts: list[str] = []
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.casefold()
        if normalized_tag in self._ignored_tags:
            self._ignored_depth += 1
        if normalized_tag == "title":
            self._title_depth += 1
        if normalized_tag in {"p", "div", "section", "article", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.casefold()
        if normalized_tag in self._ignored_tags and self._ignored_depth:
            self._ignored_depth -= 1
        if normalized_tag == "title" and self._title_depth:
            self._title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._title_depth:
            self._title_parts.append(data)
        self._text_parts.append(data)

    @property
    def title(self) -> str:
        return _normalize_extracted_text(" ".join(self._title_parts))

    @property
    def text(self) -> str:
        return _normalize_extracted_text("".join(self._text_parts))


def parse_html_document(content: bytes, source_name: str) -> ParsedDocument:
    """Convert an HTML file into readable text for the indexing pipeline."""
    extractor = _HtmlTextExtractor()
    extractor.feed(_decode_text_bytes(content))
    extractor.close()
    text = extractor.text
    if not text:
        raise ValueError("HTML document does not contain extractable text.")

    metadata = {"source_name": source_name, "source_type": "html"}
    if extractor.title:
        metadata["title"] = extractor.title
    return ParsedDocument(
        text=text,
        source_name=source_name,
        source_type="html",
        metadata=metadata,
    )


def parse_docx_document(content: bytes, source_name: str) -> ParsedDocument:
    """Extract paragraphs from a DOCX archive without an extra dependency."""
    if not content:
        raise ValueError("Word document content cannot be empty.")

    try:
        with ZipFile(BytesIO(content)) as archive:
            document_xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(document_xml)
    except (BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise ValueError("Invalid DOCX document.") from error

    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for paragraph in root.iter(f"{namespace}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
        if text.strip():
            paragraphs.append(text.strip())

    normalized = _normalize_extracted_text("\n".join(paragraphs))
    if not normalized:
        raise ValueError("Word document does not contain extractable text.")

    return ParsedDocument(
        text=normalized,
        source_name=source_name,
        source_type="word",
        metadata={"source_name": source_name, "source_type": "word"},
    )


def _decode_text_bytes(content: bytes) -> str:
    if not content:
        raise ValueError("Document content cannot be empty.")

    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Document text must be UTF-8, UTF-16, or GB18030 encoded.")


def _normalize_extracted_text(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()