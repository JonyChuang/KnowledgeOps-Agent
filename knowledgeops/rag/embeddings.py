"""Embedding provider contracts and deterministic local test implementation."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class EmbeddingProvider(Protocol):
    """Contract implemented by real and test embedding providers."""

    model_name: str

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Convert ordered text inputs into equally ordered vectors."""


@dataclass(frozen=True)
class DeterministicEmbeddingProvider:
    """Deterministic vectors for tests and local development only."""

    dimensions: int = 16
    model_name: str = "deterministic-test-v1"

    def __post_init__(self) -> None:
        # SHA-256 has 32 bytes, so this simple provider supports up to 32 dimensions.
        if not 1 <= self.dimensions <= 32:
            raise ValueError("dimensions must be between 1 and 32.")

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return stable non-semantic vectors without calling an external API."""
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        """Convert one non-empty text value into a repeatable float vector."""
        if not text.strip():
            raise ValueError("Embedding text cannot be empty.")

        digest = hashlib.sha256(text.encode("utf-8")).digest()

        # Map each byte from 0..255 into a float range close to -1..1.
        return [
            (byte / 127.5) - 1.0
            for byte in digest[: self.dimensions]
        ]