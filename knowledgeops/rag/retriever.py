"""Semantic retrieval that converts a question into citable document chunks."""

from dataclasses import dataclass

from .embeddings import EmbeddingProvider
from .vector_store import QdrantVectorStore, VectorSearchResult


@dataclass(frozen=True)
class RetrievedChunk:
    """One semantic match with the source fields required for citation."""

    vector_id: str
    score: float
    knowledge_base_id: str
    document_id: str
    source_name: str
    source_type: str
    chunk_index: int
    start_char: int
    end_char: int
    text: str


class SemanticRetriever:
    """Embed a question and retrieve relevant chunks from one knowledge base."""

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: QdrantVectorStore,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    async def retrieve(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int = 5,
    ) -> list[RetrievedChunk]:
        """Return ranked, citable chunks for one non-empty user question."""
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("Query cannot be empty.")

        if not knowledge_base_id.strip():
            raise ValueError("Knowledge base ID cannot be empty.")

        # One question produces one query vector for nearest-neighbor search.
        vectors = await self.embedding_provider.embed_texts([clean_query])
        if len(vectors) != 1:
            raise RuntimeError("Embedding provider must return exactly one query vector.")

        vector_results = await self.vector_store.search(
            vectors[0],
            limit=limit,
            knowledge_base_id=knowledge_base_id,
        )

        # Convert low-level Qdrant payloads into an explicit citation contract.
        return [
            self._to_retrieved_chunk(result)
            for result in vector_results
        ]

    @staticmethod
    def _to_retrieved_chunk(result: VectorSearchResult) -> RetrievedChunk:
        """Validate the indexing payload before exposing it to a caller."""
        payload = result.payload
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
            joined_fields = ", ".join(missing_fields)
            raise ValueError(
                f"Qdrant result is missing citation payload fields: {joined_fields}."
            )

        return RetrievedChunk(
            vector_id=result.vector_id,
            score=result.score,
            knowledge_base_id=str(payload["knowledge_base_id"]),
            document_id=str(payload["document_id"]),
            source_name=str(payload["source_name"]),
            source_type=str(payload["source_type"]),
            chunk_index=int(payload["chunk_index"]),
            start_char=int(payload["start_char"]),
            end_char=int(payload["end_char"]),
            text=str(payload["text"]),
        )