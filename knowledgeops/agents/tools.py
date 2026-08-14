"""Agent-facing tools with explicit read-only boundaries."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from ..rag.hybrid_retriever import HybridRetrievedChunk
from ..repositories import DocumentChunkRepository
from .state import AgentCitation


class RetrieverLike(Protocol):
    """The small retriever interface required by the Agent tool."""

    async def retrieve(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int,
    ) -> list[HybridRetrievedChunk]:
        """Retrieve citable chunks."""

    async def close(self) -> None:
        """Release external clients."""


class KnowledgeSearchTool(Protocol):
    """Read-only knowledge search capability exposed to the Agent."""

    async def search(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int = 5,
    ) -> list[AgentCitation]:
        """Search one knowledge base without changing data."""


class KnowledgeBaseScopeTool(Protocol):
    """Read a small sample of already indexed knowledge-base content."""

    async def list_ready_citations(
        self,
        *,
        knowledge_base_id: str,
        limit: int = 3,
    ) -> list[AgentCitation]:
        """Return citations that describe available corpus coverage."""


class DatabaseKnowledgeBaseScopeTool:
    """Adapt persisted ready chunks for an Agent coverage explanation."""

    def __init__(self, document_chunks: DocumentChunkRepository) -> None:
        self.document_chunks = document_chunks

    async def list_ready_citations(
        self,
        *,
        knowledge_base_id: str,
        limit: int = 3,
    ) -> list[AgentCitation]:
        chunks = await self.document_chunks.list_ready_for_knowledge_base(
            knowledge_base_id,
            limit=limit,
        )
        return [
            AgentCitation(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                source_name=chunk.source_name,
                source_type=chunk.source_type,
                chunk_index=chunk.chunk_index,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                text=chunk.text,
                score=0.0,
                sources=["knowledge_base_scope"],
            )
            for chunk in chunks
        ]


class HybridKnowledgeSearchTool:
    """Adapt HybridRetriever results to the serializable Agent contract."""

    def __init__(self, retriever: RetrieverLike) -> None:
        self.retriever = retriever

    async def search(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int = 5,
    ) -> list[AgentCitation]:
        chunks = await self.retriever.retrieve(
            query,
            knowledge_base_id=knowledge_base_id,
            limit=limit,
        )

        return [
            AgentCitation(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                source_name=chunk.source_name,
                source_type=chunk.source_type,
                chunk_index=chunk.chunk_index,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                text=chunk.text,
                score=chunk.score,
                sources=list(chunk.sources),
                rerank_score=chunk.rerank_score,
            )
            for chunk in chunks
        ]

    async def close(self) -> None:
        """Delegate resource cleanup to the underlying retriever."""
        await self.retriever.close()


class LazyKnowledgeSearchTool:
    """Create the external retriever only for a knowledge-search request."""

    def __init__(
        self,
        retriever_factory: Callable[[], RetrieverLike],
    ) -> None:
        self._retriever_factory = retriever_factory
        self._tool: HybridKnowledgeSearchTool | None = None

    async def search(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int = 5,
    ) -> list[AgentCitation]:
        if self._tool is None:
            self._tool = HybridKnowledgeSearchTool(
                self._retriever_factory()
            )

        return await self._tool.search(
            query,
            knowledge_base_id=knowledge_base_id,
            limit=limit,
        )

    async def close(self) -> None:
        if self._tool is not None:
            await self._tool.close()
