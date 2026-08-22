"""Hybrid retrieval that combines vector and keyword recall."""

import asyncio
from dataclasses import dataclass

from .fusion import FusedCandidate, reciprocal_rank_fusion
from .hybrid import keyword_candidates, vector_candidates
from .keyword_store import KeywordStore
from .query_planning import EvidenceFacet, build_multi_source_query_plan
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
    lifecycle: str = "active"
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
        candidate_limit: int = 20,
        max_chunks_per_document: int = 2,
    ) -> None:
        if rrf_k < 1:
            raise ValueError("RRF constant k must be greater than zero.")

        self.semantic_retriever = semantic_retriever
        self.keyword_store = keyword_store
        self.rrf_k = rrf_k
        self.reranker = reranker
        self.candidate_limit = candidate_limit
        self.max_chunks_per_document = max_chunks_per_document

        if candidate_limit < 1:
            raise ValueError("Candidate limit must be greater than zero.")
        if max_chunks_per_document < 1:
            raise ValueError("Maximum chunks per document must be greater than zero.")
    async def retrieve(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int = 5,
        include_archived: bool = False,
    ) -> list[HybridRetrievedChunk]:
        """Return fused, citable chunks from one knowledge base."""
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("Query cannot be empty.")

        if not knowledge_base_id.strip():
            raise ValueError("Knowledge base ID cannot be empty.")

        if limit < 1:
            raise ValueError("Search limit must be greater than zero.")

        plan = build_multi_source_query_plan(clean_query)
        candidate_limit = max(limit, self.candidate_limit)
        recalled = await asyncio.gather(
            self._retrieve_candidates(
                plan.primary_query,
                knowledge_base_id=knowledge_base_id,
                include_archived=include_archived,
                candidate_limit=candidate_limit,
            ),
            *(
                self._retrieve_candidates(
                    facet_query,
                    knowledge_base_id=knowledge_base_id,
                    include_archived=include_archived,
                    candidate_limit=candidate_limit,
                )
                for _facet, facet_query in plan.facet_queries
            ),
        )
        primary_candidates = recalled[0]
        if not plan.is_multi_source:
            return self._select_source_diverse(primary_candidates, limit=limit)

        facet_candidates = tuple(
            (facet, candidates)
            for (facet, _query), candidates in zip(
                plan.facet_queries,
                recalled[1:],
                strict=True,
            )
        )
        candidates = self._prioritize_evidence_coverage(
            primary_candidates,
            facet_candidates,
            limit=limit,
        )
        return self._select_source_diverse(candidates, limit=limit)

    async def _retrieve_candidates(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        include_archived: bool,
        candidate_limit: int,
    ) -> list[HybridRetrievedChunk]:
        """Recall and rank a candidate pool for one focused evidence query."""
        vector_results, keyword_results = await asyncio.gather(
            self.semantic_retriever.retrieve_vector_results(
                query,
                knowledge_base_id=knowledge_base_id,
                limit=candidate_limit,
                include_archived=include_archived,
            ),
            self.keyword_store.search(
                query,
                knowledge_base_id=knowledge_base_id,
                limit=candidate_limit,
                include_archived=include_archived,
            ),
        )
        fused_results = reciprocal_rank_fusion(
            [
                vector_candidates(vector_results, knowledge_base_id=knowledge_base_id),
                keyword_candidates(keyword_results, knowledge_base_id=knowledge_base_id),
            ],
            k=self.rrf_k,
            limit=candidate_limit,
        )
        candidates = [
            self._to_hybrid_chunk(candidate, knowledge_base_id=knowledge_base_id)
            for candidate in fused_results
        ]
        searchable = [
            candidate
            for candidate in candidates
            if self._is_searchable(candidate.lifecycle, include_archived)
        ]
        if self.reranker is None:
            return searchable
        return await self.reranker.rerank(
            query,
            searchable,
            limit=candidate_limit,
        )

    def _prioritize_evidence_coverage(
        self,
        primary_candidates: list[HybridRetrievedChunk],
        facet_candidates: tuple[tuple[EvidenceFacet, list[HybridRetrievedChunk]], ...],
        *,
        limit: int,
    ) -> list[HybridRetrievedChunk]:
        """Seed the final ranking with one distinct source for each requested role."""
        prioritized: list[HybridRetrievedChunk] = []
        selected_document_ids: set[str] = set()
        selected_chunk_ids: set[str] = set()

        for _facet, candidates in facet_candidates:
            candidate = next(
                (
                    item
                    for item in candidates
                    if item.document_id not in selected_document_ids
                ),
                None,
            )
            if candidate is None:
                continue
            prioritized.append(candidate)
            selected_document_ids.add(candidate.document_id)
            selected_chunk_ids.add(candidate.chunk_id)
            if len(prioritized) == limit:
                return prioritized

        for candidate in (
            *primary_candidates,
            *(item for _facet, items in facet_candidates for item in items),
        ):
            if candidate.chunk_id in selected_chunk_ids:
                continue
            prioritized.append(candidate)
            selected_chunk_ids.add(candidate.chunk_id)
        return prioritized

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
            # Existing indexed payloads predate document governance. Treating
            # them as active keeps upgrades backward compatible.
            lifecycle=str(payload.get("document_lifecycle", "active")),
        )

    @staticmethod
    def _is_searchable(lifecycle: str, include_archived: bool) -> bool:
        normalized = lifecycle.strip().lower()
        if normalized == "draft":
            return False
        return include_archived or normalized != "archived"

    def _select_source_diverse(
        self,
        candidates: list[HybridRetrievedChunk],
        *,
        limit: int,
    ) -> list[HybridRetrievedChunk]:
        """Keep adjacent chunks from one source from crowding out evidence."""
        selected: list[HybridRetrievedChunk] = []
        counts_by_document: dict[str, int] = {}
        for candidate in candidates:
            count = counts_by_document.get(candidate.document_id, 0)
            if count >= self.max_chunks_per_document:
                continue
            selected.append(candidate)
            counts_by_document[candidate.document_id] = count + 1
            if len(selected) == limit:
                break
        return selected
