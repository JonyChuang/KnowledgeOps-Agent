"""Database access for employee favorites, visits, and Agent feedback."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentFeedback, Favorite, RecentVisit, WorkspaceItemType
from ..models.base import utc_now


class EngagementRepository:
    """Persist employee-scoped engagement records without owning transactions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_favorite(
        self,
        *,
        actor: str,
        entity_type: WorkspaceItemType,
        entity_id: str,
    ) -> Favorite | None:
        return await self.session.scalar(
            select(Favorite).where(
                Favorite.actor == actor,
                Favorite.entity_type == entity_type,
                Favorite.entity_id == entity_id,
            )
        )

    async def list_favorites(self, *, actor: str, limit: int) -> list[Favorite]:
        result = await self.session.scalars(
            select(Favorite)
            .where(Favorite.actor == actor)
            .order_by(Favorite.created_at.desc())
            .limit(limit)
        )
        return list(result)

    async def create_favorite(self, favorite: Favorite) -> Favorite:
        self.session.add(favorite)
        await self.session.flush()
        return favorite

    async def delete_favorite(self, favorite: Favorite) -> None:
        await self.session.delete(favorite)
        await self.session.flush()

    async def get_recent_visit(
        self,
        *,
        actor: str,
        entity_type: WorkspaceItemType,
        entity_id: str,
    ) -> RecentVisit | None:
        return await self.session.scalar(
            select(RecentVisit).where(
                RecentVisit.actor == actor,
                RecentVisit.entity_type == entity_type,
                RecentVisit.entity_id == entity_id,
            )
        )

    async def create_recent_visit(self, visit: RecentVisit) -> RecentVisit:
        self.session.add(visit)
        await self.session.flush()
        return visit

    async def touch_recent_visit(self, visit: RecentVisit) -> RecentVisit:
        visit.visited_at = utc_now()
        await self.session.flush()
        return visit

    async def list_recent_visits(self, *, actor: str, limit: int) -> list[RecentVisit]:
        result = await self.session.scalars(
            select(RecentVisit)
            .where(RecentVisit.actor == actor)
            .order_by(RecentVisit.visited_at.desc())
            .limit(limit)
        )
        return list(result)

    async def get_feedback(
        self,
        *,
        actor: str,
        agent_message_id: str,
    ) -> AgentFeedback | None:
        return await self.session.scalar(
            select(AgentFeedback).where(
                AgentFeedback.actor == actor,
                AgentFeedback.agent_message_id == agent_message_id,
            )
        )

    async def create_feedback(self, feedback: AgentFeedback) -> AgentFeedback:
        self.session.add(feedback)
        await self.session.flush()
        return feedback

    async def list_feedback(self, *, actor: str, limit: int) -> list[AgentFeedback]:
        result = await self.session.scalars(
            select(AgentFeedback)
            .where(AgentFeedback.actor == actor)
            .order_by(AgentFeedback.updated_at.desc())
            .limit(limit)
        )
        return list(result)
