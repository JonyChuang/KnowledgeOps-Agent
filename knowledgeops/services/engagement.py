"""Business operations for local cross-workspace engagement features."""

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..graphrag import RuleBasedEntityExtractor
from ..models import (
    AgentFeedback,
    AgentMessage,
    Document,
    Favorite,
    RecentVisit,
    Ticket,
    WorkspaceItemType,
)
from ..repositories import AgentConversationRepository, EngagementRepository
from .knowledge import ResourceNotFoundError


@dataclass(frozen=True)
class GlobalSearchItem:
    entity_type: WorkspaceItemType
    entity_id: str
    title: str
    summary: str
    target_view: str
    target_id: str | None
    metadata_json: dict[str, object]
    created_at: object | None


class EngagementService:
    """Keep personal shortcuts and feedback isolated by the active employee."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.items = EngagementRepository(session)
        self.conversations = AgentConversationRepository(session)

    async def add_favorite(self, payload, *, actor: str) -> Favorite:
        existing = await self.items.get_favorite(
            actor=actor,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
        )
        if existing is not None:
            return existing
        favorite = await self.items.create_favorite(
            Favorite(actor=actor, **payload.model_dump())
        )
        await self.session.commit()
        await self.session.refresh(favorite)
        return favorite

    async def remove_favorite(
        self,
        *,
        actor: str,
        entity_type: WorkspaceItemType,
        entity_id: str,
    ) -> None:
        favorite = await self.items.get_favorite(
            actor=actor,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        if favorite is None:
            raise ResourceNotFoundError("Favorite not found.")
        await self.items.delete_favorite(favorite)
        await self.session.commit()

    async def list_favorites(self, *, actor: str, limit: int) -> list[Favorite]:
        return await self.items.list_favorites(actor=actor, limit=limit)

    async def record_recent_visit(self, payload, *, actor: str) -> RecentVisit:
        visit = await self.items.get_recent_visit(
            actor=actor,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
        )
        if visit is None:
            visit = await self.items.create_recent_visit(
                RecentVisit(actor=actor, **payload.model_dump())
            )
        else:
            visit.title = payload.title
            visit.subtitle = payload.subtitle
            visit.target_view = payload.target_view
            visit.target_id = payload.target_id
            visit.metadata_json = payload.metadata_json
            visit = await self.items.touch_recent_visit(visit)
        await self.session.commit()
        await self.session.refresh(visit)
        return visit

    async def list_recent_visits(self, *, actor: str, limit: int) -> list[RecentVisit]:
        return await self.items.list_recent_visits(actor=actor, limit=limit)

    async def add_agent_feedback(
        self,
        agent_message_id: str,
        payload,
        *,
        actor: str,
    ) -> AgentFeedback:
        message = await self.session.scalar(
            select(AgentMessage)
            .where(
                AgentMessage.id == agent_message_id,
                AgentMessage.role == "agent",
                AgentMessage.conversation.has(actor=actor),
            )
        )
        if message is None:
            raise ResourceNotFoundError("Agent message not found.")
        feedback = await self.items.get_feedback(
            actor=actor,
            agent_message_id=agent_message_id,
        )
        if feedback is None:
            feedback = await self.items.create_feedback(
                AgentFeedback(
                    actor=actor,
                    agent_message_id=agent_message_id,
                    feedback_type=payload.feedback_type,
                    comment=payload.comment.strip(),
                )
            )
        else:
            feedback.feedback_type = payload.feedback_type
            feedback.comment = payload.comment.strip()
        await self.session.commit()
        await self.session.refresh(feedback)
        return feedback

    async def global_search(
        self,
        query: str,
        *,
        actor: str,
        limit: int,
    ) -> list[GlobalSearchItem]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            raise ValueError("Search query cannot be empty.")
        pattern = f"%{normalized_query.casefold()}%"
        per_source_limit = max(1, limit)

        documents = list(
            await self.session.scalars(
                select(Document)
                .where(
                    or_(
                        func.lower(Document.source_name).like(pattern),
                        func.lower(Document.content).like(pattern),
                    )
                )
                .order_by(Document.updated_at.desc())
                .limit(per_source_limit)
            )
        )
        tickets = list(
            await self.session.scalars(
                select(Ticket)
                .where(
                    Ticket.requester == actor,
                    or_(
                        func.lower(Ticket.title).like(pattern),
                        func.lower(Ticket.description).like(pattern),
                    ),
                )
                .order_by(Ticket.updated_at.desc())
                .limit(per_source_limit)
            )
        )
        messages = list(
            await self.session.scalars(
                select(AgentMessage)
                .where(
                    AgentMessage.conversation.has(actor=actor),
                    AgentMessage.content.is_not(None),
                    func.lower(AgentMessage.content).like(pattern),
                )
                .order_by(AgentMessage.created_at.desc())
                .limit(per_source_limit)
            )
        )

        items: list[GlobalSearchItem] = []
        items.extend(
            GlobalSearchItem(
                entity_type=WorkspaceItemType.DOCUMENT,
                entity_id=document.id,
                title=document.source_name,
                summary=self._preview(document.content),
                target_view="knowledge",
                target_id=document.knowledge_base_id,
                metadata_json={
                    "knowledge_base_id": document.knowledge_base_id,
                    "status": document.status.value,
                },
                created_at=document.updated_at,
            )
            for document in documents
        )
        items.extend(
            GlobalSearchItem(
                entity_type=WorkspaceItemType.TICKET,
                entity_id=ticket.id,
                title=ticket.title,
                summary=self._preview(ticket.description),
                target_view="tickets",
                target_id=ticket.id,
                metadata_json={
                    "status": ticket.status.value,
                    "priority": ticket.priority.value,
                },
                created_at=ticket.updated_at,
            )
            for ticket in tickets
        )
        items.extend(
            GlobalSearchItem(
                entity_type=WorkspaceItemType.CONVERSATION,
                entity_id=message.conversation_id,
                title="历史 Agent 对话",
                summary=self._preview(message.content or ""),
                target_view="agent",
                target_id=message.conversation_id,
                metadata_json={"message_id": message.id},
                created_at=message.created_at,
            )
            for message in messages
        )

        graph_entities = RuleBasedEntityExtractor().extract_entities(normalized_query)
        items.extend(
            GlobalSearchItem(
                entity_type=WorkspaceItemType.GRAPH,
                entity_id=f"entity:{entity.key}",
                title=f"图谱实体：{entity.name}",
                summary=f"可在图谱检索中查看与“{entity.name}”关联的已索引资料。",
                target_view="graph",
                target_id=entity.name,
                metadata_json={"entity": entity.name},
                created_at=None,
            )
            for entity in graph_entities
        )
        items.sort(
            key=lambda item: item.created_at.isoformat() if item.created_at else "",
            reverse=True,
        )
        return items[:limit]

    @staticmethod
    def _preview(value: str, limit: int = 160) -> str:
        normalized = " ".join(value.split())
        return normalized[:limit] + ("..." if len(normalized) > limit else "")
