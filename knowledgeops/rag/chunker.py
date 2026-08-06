"""Text splitting utilities for retrieval-augmented generation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    """One searchable text window extracted from a parsed document."""

    chunk_index: int
    text: str
    start_char: int
    end_char: int


def split_text(
    text: str,
    *,
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[TextChunk]:
    """Split text into overlapping character windows."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between zero and chunk_size - 1.")

    if not text.strip():
        return []

    chunks: list[TextChunk] = []
    start = 0
    chunk_index = 0

    while start < len(text):
        # The end position is exclusive, matching normal Python slicing rules.
        end = min(start + chunk_size, len(text))

        chunks.append(
            TextChunk(
                chunk_index=chunk_index,
                text=text[start:end],
                start_char=start,
                end_char=end,
            )
        )

        # Stop after the final window to avoid creating an endless overlap loop.
        if end == len(text):
            break

        # Reuse part of the previous window so context is not cut abruptly.
        start = end - overlap
        chunk_index += 1

    return chunks