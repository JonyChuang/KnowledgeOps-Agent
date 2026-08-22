"""Adapters that run the versioned gold set against configured services."""

from __future__ import annotations

from dataclasses import dataclass

from openai import AsyncOpenAI

from ..config import Settings
from ..graphrag import GraphRetriever, RuleBasedEntityExtractor
from ..rag import HybridRetriever
from ..tasks.indexing import (
    build_elasticsearch_keyword_store,
    build_neo4j_graph_store,
    build_semantic_retriever,
)
from .verifier import OpenAIAnswerVerifier


@dataclass(frozen=True)
class EvaluationRetrievedItem:
    """Common evidence identity exposed by all retriever baselines."""

    chunk_id: str
    source_name: str
    lifecycle: str = "active"


class SemanticEvaluationRetriever:
    def __init__(self, semantic_retriever) -> None:
        self.semantic_retriever = semantic_retriever

    async def retrieve(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int,
        include_archived: bool = False,
    ):
        results = await self.semantic_retriever.retrieve(
            query,
            knowledge_base_id=knowledge_base_id,
            limit=limit,
            include_archived=include_archived,
        )
        return [
            EvaluationRetrievedItem(
                chunk_id=result.vector_id,
                source_name=result.source_name,
                lifecycle=result.lifecycle,
            )
            for result in results
        ]

    async def close(self) -> None:
        await self.semantic_retriever.vector_store.close()


class KeywordEvaluationRetriever:
    def __init__(self, keyword_store) -> None:
        self.keyword_store = keyword_store

    async def retrieve(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int,
        include_archived: bool = False,
    ):
        results = await self.keyword_store.search(
            query,
            knowledge_base_id=knowledge_base_id,
            limit=limit,
            include_archived=include_archived,
        )
        return [
            EvaluationRetrievedItem(
                chunk_id=result.chunk_id,
                source_name=str(result.payload.get("source_name", "")),
                lifecycle=str(result.payload.get("document_lifecycle", "active")),
            )
            for result in results
        ]

    async def close(self) -> None:
        await self.keyword_store.close()


class GraphEvaluationRetriever:
    def __init__(self, graph_retriever: GraphRetriever) -> None:
        self.graph_retriever = graph_retriever

    async def retrieve(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int,
        include_archived: bool = False,
    ):
        results = await self.graph_retriever.retrieve(
            query,
            knowledge_base_id=knowledge_base_id,
            limit=limit,
            include_archived=include_archived,
        )
        return [
            EvaluationRetrievedItem(
                chunk_id=result.chunk_id,
                source_name=result.source_name,
                lifecycle=result.lifecycle,
            )
            for result in results
        ]

    async def close(self) -> None:
        await self.graph_retriever.graph_store.close()


def build_retrieval_baseline(method: str, settings: Settings):
    """Build one explicitly named baseline with independent clients.

    Methods deliberately match the offline report rows: vector, bm25, hybrid,
    hybrid_rerank, and graph. A run must use the same indexed corpus and model
    configuration for every method to make the comparison meaningful.
    """
    if method == "vector":
        return SemanticEvaluationRetriever(build_semantic_retriever(settings))
    if method == "bm25":
        return KeywordEvaluationRetriever(build_elasticsearch_keyword_store(settings))
    if method in {"hybrid", "hybrid_rerank"}:
        from ..rag import TokenOverlapReranker

        return HybridRetriever(
            semantic_retriever=build_semantic_retriever(settings),
            keyword_store=build_elasticsearch_keyword_store(settings),
            reranker=TokenOverlapReranker() if method == "hybrid_rerank" else None,
        )
    if method == "graph":
        graph_store = build_neo4j_graph_store(settings)
        return GraphEvaluationRetriever(
            GraphRetriever(
                graph_store=graph_store,
                entity_extractor=RuleBasedEntityExtractor(),
            )
        )
    raise ValueError(f"Unsupported retrieval baseline: {method}")


def build_answer_verifier(settings: Settings) -> OpenAIAnswerVerifier | None:
    """Build the optional independent evaluator without falling back to CHAT_MODEL."""
    if (
        not settings.verifier_model
        or settings.verifier_api_key is None
        or not settings.verifier_base_url
    ):
        return None
    return OpenAIAnswerVerifier(
        client=AsyncOpenAI(
            api_key=settings.verifier_api_key.get_secret_value(),
            base_url=settings.verifier_base_url,
        ),
        model=settings.verifier_model,
        temperature=settings.chat_temperature,
    )
