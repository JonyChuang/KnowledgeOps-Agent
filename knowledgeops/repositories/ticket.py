"""Database access for tickets."""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Ticket, TicketActivity, TicketStatus


class TicketRepository:
    """Read and write tickets without owning transactions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, ticket: Ticket) -> Ticket:
        self.session.add(ticket)
        await self.session.flush()
        return ticket

    async def get_for_requester(
        self,
        ticket_id: str,
        *,
        requester: str,
    ) -> Ticket | None:
        result = await self.session.scalar(
            select(Ticket).where(
                Ticket.id == ticket_id,
                Ticket.requester == requester,
            )
        )
        return result

    async def get_detail_for_requester(
        self,
        ticket_id: str,
        *,
        requester: str,
    ) -> Ticket | None:
        """Load an employee-owned ticket together with its visible timeline."""
        result = await self.session.scalar(
            select(Ticket)
            .execution_options(populate_existing=True)
            .options(selectinload(Ticket.activities))
            .where(
                Ticket.id == ticket_id,
                Ticket.requester == requester,
            )
        )
        return result

    async def get_detail(self, ticket_id: str) -> Ticket | None:
        """Load a ticket and its timeline for an authorized service-desk view."""
        return await self.session.scalar(
            select(Ticket)
            .execution_options(populate_existing=True)
            .options(selectinload(Ticket.activities))
            .where(Ticket.id == ticket_id)
        )

    async def create_activity(self, activity: TicketActivity) -> TicketActivity:
        """Append, never mutate, an employee-visible ticket event."""
        self.session.add(activity)
        await self.session.flush()
        return activity

    async def list_for_requester(
        self,
        *,
        requester: str,
        status: TicketStatus | None = None,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Ticket]:
        conditions = self._list_conditions(
            requester=requester,
            status=status,
            query=query,
        )
        result = await self.session.scalars(
            select(Ticket)
            .where(*conditions)
            .order_by(Ticket.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result)

    async def count_for_requester(
        self,
        *,
        requester: str,
        status: TicketStatus | None = None,
        query: str | None = None,
    ) -> int:
        """Count ticket records with the same filters as the list view."""
        conditions = self._list_conditions(
            requester=requester,
            status=status,
            query=query,
        )
        count = await self.session.scalar(
            select(func.count(Ticket.id)).where(*conditions)
        )
        return count or 0

    async def count_for_requester_by_status(
        self,
        *,
        requester: str,
    ) -> dict[TicketStatus, int]:
        """Return one requester's ticket counts grouped by lifecycle state."""
        result = await self.session.execute(
            select(Ticket.status, func.count(Ticket.id))
            .where(Ticket.requester == requester)
            .group_by(Ticket.status)
        )
        return {status: count for status, count in result.all()}

    async def list_for_service_desk(
        self,
        *,
        operator: str,
        scope: str,
        status: TicketStatus | None = None,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Ticket]:
        """List tickets in an operational queue without requester filtering."""
        conditions = self._service_list_conditions(
            operator=operator,
            scope=scope,
            status=status,
            query=query,
        )
        result = await self.session.scalars(
            select(Ticket)
            .where(*conditions)
            .order_by(Ticket.updated_at.desc(), Ticket.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result)

    async def count_for_service_desk(
        self,
        *,
        operator: str,
        scope: str,
        status: TicketStatus | None = None,
        query: str | None = None,
    ) -> int:
        """Return the count matching the same queue conditions as the list."""
        conditions = self._service_list_conditions(
            operator=operator,
            scope=scope,
            status=status,
            query=query,
        )
        count = await self.session.scalar(select(func.count(Ticket.id)).where(*conditions))
        return count or 0

    @staticmethod
    def _list_conditions(
        *,
        requester: str,
        status: TicketStatus | None,
        query: str | None,
    ) -> list[object]:
        conditions: list[object] = [Ticket.requester == requester]
        if status is not None:
            conditions.append(Ticket.status == status)

        normalized_query = (query or "").strip().lower()
        if normalized_query:
            # Use a portable case-insensitive match for both SQLite and Postgres.
            pattern = f"%{normalized_query}%"
            conditions.append(
                or_(
                    func.lower(Ticket.title).like(pattern),
                    func.lower(Ticket.description).like(pattern),
                )
            )
        return conditions

    @classmethod
    def _service_list_conditions(
        cls,
        *,
        operator: str,
        scope: str,
        status: TicketStatus | None,
        query: str | None,
    ) -> list[object]:
        valid_scopes = {"all", "mine", "unassigned"}
        if scope not in valid_scopes:
            raise ValueError(f"Unsupported service-desk scope: {scope}.")

        conditions: list[object] = []
        if scope == "mine":
            conditions.append(Ticket.assignee == operator)
        elif scope == "unassigned":
            conditions.append(Ticket.assignee.is_(None))

        if status is not None:
            conditions.append(Ticket.status == status)

        normalized_query = (query or "").strip().lower()
        if normalized_query:
            pattern = f"%{normalized_query}%"
            conditions.append(
                or_(
                    func.lower(Ticket.title).like(pattern),
                    func.lower(Ticket.description).like(pattern),
                    func.lower(Ticket.requester).like(pattern),
                )
            )
        return conditions
