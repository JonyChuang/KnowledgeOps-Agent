"""Tests for the deterministic reranker."""

import pytest

from knowledgeops.rag import HybridRetrievedChunk, TokenOverlapReranker


def chunk(chunk_id: str, score: float, text: str) -> HybridRetrievedChunk:
    return HybridRetrievedChunk(
        chunk_id=chunk_id,
        score=score,
        sources=("vector",),
        knowledge_base_id="support",
        document_id="document-1",
        source_name="runbook.md",
        source_type="markdown",
        chunk_index=0,
        start_char=0,
        end_char=len(text),
        text=text,
    )


@pytest.mark.asyncio
async def test_token_overlap_reranker_promotes_term_coverage():
    """The candidate matching more query terms should rank first."""
    reranker = TokenOverlapReranker()

    results = await reranker.rerank(
        "restart API service",
        [
            chunk("chunk-a", 0.90, "Restart the service."),
            chunk("chunk-b", 0.80, "Restart the API service now."),
        ],
        limit=2,
    )

    assert [result.chunk_id for result in results] == [
        "chunk-b",
        "chunk-a",
    ]
    assert results[0].rerank_score == pytest.approx(1.0)
    assert results[1].rerank_score == pytest.approx(2 / 3)


@pytest.mark.asyncio
async def test_token_overlap_reranker_rejects_non_positive_limit():
    """A reranker must reject an invalid output limit."""
    with pytest.raises(ValueError, match="Rerank limit must be greater than zero"):
        await TokenOverlapReranker().rerank(
            "restart service",
            [],
            limit=0,
        )