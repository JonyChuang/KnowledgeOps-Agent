import pytest

from knowledgeops.rag import (
    KeywordSearchResult,
    VectorSearchResult,
    keyword_candidates,
    vector_candidates,
)


def payload(knowledge_base_id: str = "support") -> dict[str, object]:
    return {
        "knowledge_base_id": knowledge_base_id,
        "document_id": "document-1",
        "source_name": "support-guide.md",
        "source_type": "markdown",
        "chunk_index": 0,
        "start_char": 0,
        "end_char": 20,
        "text": "Restart the service.",
    }


def test_vector_results_become_hybrid_candidates():
    """Qdrant vector IDs should become common chunk IDs."""
    results = vector_candidates(
        [
            VectorSearchResult(
                vector_id="chunk-1",
                score=0.91,
                payload=payload(),
            )
        ],
        knowledge_base_id="support",
    )

    assert len(results) == 1
    assert results[0].chunk_id == "chunk-1"
    assert results[0].score == pytest.approx(0.91)
    assert results[0].source == "vector"
    assert results[0].payload["source_name"] == "support-guide.md"


def test_keyword_results_become_hybrid_candidates():
    """BM25 chunk IDs should use the same common candidate structure."""
    results = keyword_candidates(
        [
            KeywordSearchResult(
                chunk_id="chunk-2",
                score=4.5,
                payload=payload(),
            )
        ],
        knowledge_base_id="support",
    )

    assert len(results) == 1
    assert results[0].chunk_id == "chunk-2"
    assert results[0].score == pytest.approx(4.5)
    assert results[0].source == "keyword"


def test_hybrid_candidates_reject_cross_knowledge_base_results():
    """Fusion must not accept a result from another knowledge base."""
    with pytest.raises(ValueError, match="another knowledge base"):
        vector_candidates(
            [
                VectorSearchResult(
                    vector_id="chunk-1",
                    score=0.91,
                    payload=payload("finance"),
                )
            ],
            knowledge_base_id="support",
        )


def test_hybrid_candidates_reject_missing_knowledge_base_id():
    """Every retrieval result must carry its knowledge-base boundary."""
    invalid_payload = payload()
    del invalid_payload["knowledge_base_id"]

    with pytest.raises(ValueError, match="missing knowledge_base_id"):
        keyword_candidates(
            [
                KeywordSearchResult(
                    chunk_id="chunk-1",
                    score=4.5,
                    payload=invalid_payload,
                )
            ],
            knowledge_base_id="support",
        )


def test_hybrid_candidates_reject_empty_chunk_id():
    """Every candidate needs a stable chunk ID for deduplication."""
    with pytest.raises(ValueError, match="missing chunk_id"):
        keyword_candidates(
            [
                KeywordSearchResult(
                    chunk_id="   ",
                    score=4.5,
                    payload=payload(),
                )
            ],
            knowledge_base_id="support",
        )