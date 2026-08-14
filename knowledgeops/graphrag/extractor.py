"""Deterministic entity extraction for initial GraphRAG indexing."""

from collections.abc import Sequence
from typing import Protocol

from .models import GraphEntity

DEFAULT_ENTITY_NAMES: tuple[str, ...] = (
    "VPN",
    "API",
    "Redis",
    "Qdrant",
    "Elasticsearch",
    "Neo4j",
    "Celery",
    "PostgreSQL",
    "账号",
    "权限",
    "网络",
    "客户端",
    "错误日志",
)

class EntityExtractor(Protocol):
    """Extract normalized graph entities from one text chunk."""

    def extract_entities(self, text: str) -> list[GraphEntity]:
        """Return the entities mentioned in text."""


class RuleBasedEntityExtractor:
    """Extract configured domain terms without an additional LLM request."""

    def __init__(
        self,
        *,
        entity_names: Sequence[str] = DEFAULT_ENTITY_NAMES,
    ) -> None:
        entities = [
            GraphEntity.from_name(entity_name)
            for entity_name in entity_names
        ]
        self._entities = tuple(
            {entity.key: entity for entity in entities}.values()
        )

    def extract_entities(self, text: str) -> list[GraphEntity]:
        normalized_text = text.casefold()
        return [
            entity
            for entity in self._entities
            if entity.key in normalized_text
        ]