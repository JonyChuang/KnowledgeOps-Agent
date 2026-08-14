"""Entity-driven retrieval over the KnowledgeOps graph."""

from .extractor import EntityExtractor
from .models import GraphChunk
from .store import GraphStore


class GraphRetriever:
    """Retrieve document chunks linked to entities from a user question."""

    def __init__(
        self,
        *,
        graph_store: GraphStore,
        entity_extractor: EntityExtractor,
    ) -> None:
        self.graph_store = graph_store
        self.entity_extractor = entity_extractor

    async def retrieve(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int = 5,
    ) -> list[GraphChunk]:
        """Return graph-related chunks for entities recognized in a query."""
        if not query.strip():
            raise ValueError("Query cannot be empty.")
        if not knowledge_base_id.strip():
            raise ValueError("Knowledge base ID cannot be empty.")
        if limit <= 0:
            raise ValueError("Search limit must be greater than zero.")

        entities = self.entity_extractor.extract_entities(query)
        if not entities:
            return []

        return await self.graph_store.find_chunks(
            knowledge_base_id=knowledge_base_id,
            entity_keys=[entity.key for entity in entities],
            limit=limit,
        )