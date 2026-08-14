"""Hybrid retrieval that combines vector and keyword recall."""

import asyncio
from dataclasses import dataclass

from .fusion import FusedCandidate, reciprocal_rank_fusion
from .hybrid import keyword_candidates, vector_candidates
from .keyword_store import KeywordStore
from .reranker import Reranker
from .retriever import SemanticRetriever


@dataclass(frozen=True)
class HybridRetrievedChunk:
    """One citable chunk after vector and keyword fusion."""

    chunk_id: str
    score: float
    sources: tuple[str, ...]
    knowledge_base_id: str
    document_id: str
    source_name: str
    source_type: str
    chunk_index: int
    start_char: int
    end_char: int
    text: str
    rerank_score: float | None = None


class HybridRetriever:
    """Retrieve from Qdrant and BM25, then combine rankings with RRF."""

    def __init__(
        self,
        *,
        semantic_retriever: SemanticRetriever,
        keyword_store: KeywordStore,
        rrf_k: int = 60,
        reranker: Reranker | None = None,
        rerank_candidate_limit: int = 20,
    ) -> None:
        if rrf_k < 1:
            raise ValueError("RRF constant k must be greater than zero.")

        self.semantic_retriever = semantic_retriever
        self.keyword_store = keyword_store
        self.rrf_k = rrf_k
        self.reranker = reranker
        self.rerank_candidate_limit = rerank_candidate_limit

        if rerank_candidate_limit < 1:
            raise ValueError("Rerank candidate limit must be greater than zero.")
    async def retrieve(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int = 5,
    ) -> list[HybridRetrievedChunk]:
        """Return fused, citable chunks from one knowledge base."""
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("Query cannot be empty.")

        if not knowledge_base_id.strip():
            raise ValueError("Knowledge base ID cannot be empty.")

        if limit < 1:
            raise ValueError("Search limit must be greater than zero.")

        candidate_limit = (
            max(limit, self.rerank_candidate_limit)
            if self.reranker is not None
            else limit
        )

        vector_results, keyword_results = await asyncio.gather(
            self.semantic_retriever.retrieve_vector_results(
                clean_query,
                knowledge_base_id=knowledge_base_id,
                limit=candidate_limit
            ),
            self.keyword_store.search(
                clean_query,
                knowledge_base_id=knowledge_base_id,
                limit=candidate_limit
            ),
        )

        fused_results = reciprocal_rank_fusion(
            [
                vector_candidates(
                    vector_results,
                    knowledge_base_id=knowledge_base_id,
                ),
                keyword_candidates(
                    keyword_results,
                    knowledge_base_id=knowledge_base_id,
                ),
            ],
            k=self.rrf_k,
            limit=candidate_limit
        )

        candidates = [
            self._to_hybrid_chunk(
                candidate,
                knowledge_base_id=knowledge_base_id,
            )
            for candidate in fused_results
        ]

        if self.reranker is None:
            return candidates[:limit]

        return await self.reranker.rerank(
            clean_query,
            candidates,
            limit=limit,
        )

    async def close(self) -> None:
        """Release clients created for one hybrid search request."""
        try:
            await self.semantic_retriever.vector_store.close()
        finally:
            await self.keyword_store.close()

    @staticmethod
    def _to_hybrid_chunk(
        candidate: FusedCandidate,
        *,
        knowledge_base_id: str,
    ) -> HybridRetrievedChunk:
        """Validate fused payloads before returning citation fields."""
        payload = candidate.payload
        required_fields = (
            "knowledge_base_id",
            "document_id",
            "source_name",
            "source_type",
            "chunk_index",
            "start_char",
            "end_char",
            "text",
        )
        missing_fields = [
            field
            for field in required_fields
            if field not in payload
        ]
        if missing_fields:
            raise ValueError(
                "Fused result is missing citation payload fields: "
                f"{', '.join(missing_fields)}."
            )

        if str(payload["knowledge_base_id"]) != knowledge_base_id:
            raise ValueError("Fused result belongs to another knowledge base.")

        return HybridRetrievedChunk(
            chunk_id=candidate.chunk_id,
            score=candidate.score,
            sources=candidate.sources,
            knowledge_base_id=str(payload["knowledge_base_id"]),
            document_id=str(payload["document_id"]),
            source_name=str(payload["source_name"]),
            source_type=str(payload["source_type"]),
            chunk_index=int(payload["chunk_index"]),
            start_char=int(payload["start_char"]),
            end_char=int(payload["end_char"]),
            text=str(payload["text"]),
        )