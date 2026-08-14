"""Agent tools for ticket lookup and confirmed creation."""

from __future__ import annotations

from typing import Protocol

from ..models import Ticket
from ..schemas import TicketCreate, TicketRead
from .state import AgentState


class TicketServiceLike(Protocol):
    """Ticket service operations needed by Agent-facing tools."""

    async def get_ticket(self, ticket_id: str, *, actor: str) -> Ticket:
        """Return one ticket scoped to the actor."""

    async def list_tickets(self, *, actor: str, limit: int) -> list[Ticket]:
        """Return tickets scoped to the actor."""

    async def create_ticket(
        self,
        payload: TicketCreate,
        *,
        actor: str,
    ) -> Ticket:
        """Persist one ticket for the actor."""


class TicketQueryTool(Protocol):
    """Read-only ticket lookup capability."""

    async def get_ticket(self, ticket_id: str, *, actor: str) -> TicketRead:
        """Return one ticket."""

    async def list_tickets(
        self,
        *,
        actor: str,
        limit: int = 20,
    ) -> list[TicketRead]:
        """Return the actor's tickets."""


class TicketCreationTool(Protocol):
    """Ticket creation capability guarded by AgentState confirmation."""

    async def create_from_state(self, state: AgentState) -> TicketRead:
        """Create a ticket only from a confirmed Agent state."""


class TicketConfirmationRequiredError(PermissionError):
    """Raised when an Agent attempts ticket creation before confirmation."""


class ServiceTicketQueryTool:
    """Adapt TicketService reads to public Agent ticket results."""

    def __init__(self, service: TicketServiceLike) -> None:
        self.service = service

    async def get_ticket(self, ticket_id: str, *, actor: str) -> TicketRead:
        ticket = await self.service.get_ticket(ticket_id, actor=actor)
        return TicketRead.model_validate(ticket)

    async def list_tickets(
        self,
        *,
        actor: str,
        limit: int = 20,
    ) -> list[TicketRead]:
        tickets = await self.service.list_tickets(
            actor=actor,
            limit=limit,
        )
        return [TicketRead.model_validate(ticket) for ticket in tickets]


class ConfirmedTicketCreationTool:
    """Create tickets only after the workflow has explicitly confirmed them."""

    def __init__(self, service: TicketServiceLike) -> None:
        self.service = service

    async def create_from_state(self, state: AgentState) -> TicketRead:
        pending_action = state.pending_action
        if not state.can_create_ticket or pending_action is None:
            raise TicketConfirmationRequiredError(
                "Ticket creation requires explicit confirmation."
            )

        payload = TicketCreate.model_validate(pending_action.arguments)
        ticket = await self.service.create_ticket(
            payload,
            actor=state.actor,
        )
        return TicketRead.model_validate(ticket)