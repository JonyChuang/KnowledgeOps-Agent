import pytest

from knowledgeops.rag import (
    HybridCandidate,
    reciprocal_rank_fusion,
)


def candidate(
    chunk_id: str,
    source: str,
) -> HybridCandidate:
    return HybridCandidate(
        chunk_id=chunk_id,
        score=0.8,
        payload={
            "knowledge_base_id": "support",
            "document_id": f"document-{chunk_id}",
            "source_name": f"{chunk_id}.md",
            "text": f"text for {chunk_id}",
        },
        source=source,
    )


def test_rrf_combines_same_chunk_from_two_retrievers():
    """A chunk appearing in both lists should receive both rank contributions."""
    results = reciprocal_rank_fusion(
        [
            [candidate("chunk-a", "vector"), candidate("chunk-b", "vector")],
            [candidate("chunk-b", "keyword"), candidate("chunk-c", "keyword")],
        ],
        k=1,
    )

    assert [result.chunk_id for result in results] == [
        "chunk-b",
        "chunk-a",
        "chunk-c",
    ]
    assert results[0].score == pytest.approx(1 / 3 + 1 / 2)
    assert results[0].sources == ("vector", "keyword")


def test_rrf_does_not_count_duplicate_chunk_twice_in_one_list():
    """Duplicate entries from one retriever should not inflate the RRF score."""
    results = reciprocal_rank_fusion(
        [
            [
                candidate("chunk-a", "vector"),
                candidate("chunk-a", "vector"),
                candidate("chunk-b", "vector"),
            ]
        ],
        k=1,
    )

    assert [result.chunk_id for result in results] == [
        "chunk-a",
        "chunk-b",
    ]
    assert results[0].score == pytest.approx(0.5)
    assert results[1].score == pytest.approx(1 / 3)


def test_rrf_supports_limit_and_validates_arguments():
    """The output limit and RRF constant should reject invalid values."""
    with pytest.raises(ValueError, match="greater than zero"):
        reciprocal_rank_fusion([], k=0)

    with pytest.raises(ValueError, match="greater than zero"):
        reciprocal_rank_fusion([], limit=0)

    results = reciprocal_rank_fusion(
        [[candidate("chunk-a", "vector"), candidate("chunk-b", "vector")]],
        k=1,
        limit=1,
    )

    assert len(results) == 1