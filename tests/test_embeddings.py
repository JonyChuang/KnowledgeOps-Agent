"""Tests for the local deterministic embedding provider."""

import pytest

from knowledgeops.rag import DeterministicEmbeddingProvider


@pytest.mark.asyncio
async def test_deterministic_provider_returns_stable_vectors():
    """The same text should always produce the same vector."""
    provider = DeterministicEmbeddingProvider(dimensions=8)

    first = await provider.embed_texts(["Restart the API."])
    second = await provider.embed_texts(["Restart the API."])

    assert first == second
    assert len(first) == 1
    assert len(first[0]) == 8


@pytest.mark.asyncio
async def test_deterministic_provider_preserves_input_order():
    """Batch results must align with their original text inputs."""
    provider = DeterministicEmbeddingProvider(dimensions=4)

    vectors = await provider.embed_texts(["first text", "second text"])

    assert len(vectors) == 2
    assert vectors[0] != vectors[1]


def test_deterministic_provider_rejects_invalid_dimensions():
    """Unsupported dimensions must fail during provider configuration."""
    with pytest.raises(ValueError):
        DeterministicEmbeddingProvider(dimensions=33)