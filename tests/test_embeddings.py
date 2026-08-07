"""Tests for the local deterministic embedding provider."""

import pytest

from knowledgeops.rag import DeterministicEmbeddingProvider
from types import SimpleNamespace

from knowledgeops.rag import OpenAIEmbeddingProvider


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


class FakeEmbeddingsResource:
    """Fake OpenAI endpoint used to test requests without network access."""

    def __init__(self):
        self.request: dict[str, object] | None = None

    async def create(self, **kwargs):
        self.request = kwargs

        # Return reversed data intentionally to verify index-based ordering.
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=1, embedding=[0.4, 0.5, 0.6]),
                SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3]),
            ]
        )


class FakeOpenAIClient:
    """Minimal client shape required by OpenAIEmbeddingProvider."""

    def __init__(self):
        self.embeddings = FakeEmbeddingsResource()


@pytest.mark.asyncio
async def test_openai_provider_uses_batch_request_and_sorts_response():
    """The provider should send one batch request and restore input ordering."""
    client = FakeOpenAIClient()
    provider = OpenAIEmbeddingProvider(
        model_name="text-embedding-3-small",
        dimensions=3,
        client=client,
    )

    vectors = await provider.embed_texts(["first text", "second text"])

    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert client.embeddings.request == {
        "model": "text-embedding-3-small",
        "input": ["first text", "second text"],
        "dimensions": 3,
        "encoding_format": "float",
    }