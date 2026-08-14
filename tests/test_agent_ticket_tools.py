from datetime import datetime, timezone

import pytest

from knowledgeops.agents.state import (
    AgentIntent,
    AgentState,
    ConfirmationStatus,
    PendingAction,
)
from knowledgeops.agents.ticket_tools import (
    ConfirmedTicketCreationTool,
    ServiceTicketQueryTool,
    TicketConfirmationRequiredError,
)
from knowledgeops.models import Ticket, TicketPriority, TicketStatus
from knowledgeops.schemas import TicketCreate


class FakeTicketService:
    def __init__(self) -> None:
        self.ticket = Ticket(
            id="ticket-001",
            title="VPN 无法连接",
            description="测试工单内容。",
            priority=TicketPriority.HIGH,
            status=TicketStatus.OPEN,
            requester="alice",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.get_calls: list[tuple[str, str]] = []
        self.list_calls: list[tuple[str, int]] = []
        self.create_calls: list[tuple[TicketCreate, str]] = []

    async def get_ticket(self, ticket_id: str, *, actor: str) -> Ticket:
        self.get_calls.append((ticket_id, actor))
        return self.ticket

    async def list_tickets(self, *, actor: str, limit: int) -> list[Ticket]:
        self.list_calls.append((actor, limit))
        return [self.ticket]

    async def create_ticket(
        self,
        payload: TicketCreate,
        *,
        actor: str,
    ) -> Ticket:
        self.create_calls.append((payload, actor))
        return self.ticket


@pytest.mark.asyncio
async def test_ticket_query_tool_passes_actor_to_service() -> None:
    service = FakeTicketService()
    tool = ServiceTicketQueryTool(service)

    ticket = await tool.get_ticket("ticket-001", actor="alice")
    tickets = await tool.list_tickets(actor="alice", limit=10)

    assert ticket.id == "ticket-001"
    assert tickets[0].requester == "alice"
    assert service.get_calls == [("ticket-001", "alice")]
    assert service.list_calls == [("alice", 10)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "confirmation_status",
    [
        ConfirmationStatus.PENDING,
        ConfirmationStatus.REJECTED,
    ],
)
async def test_creation_tool_rejects_unconfirmed_state(
    confirmation_status: ConfirmationStatus,
) -> None:
    service = FakeTicketService()
    tool = ConfirmedTicketCreationTool(service)
    state = AgentState(
        actor="alice",
        user_message="创建一个 VPN 工单",
        intent=AgentIntent.TICKET_CREATE,
        pending_action=PendingAction(
            action_type="ticket.create",
            arguments={
                "title": "VPN 无法连接",
                "description": "测试工单内容。",
            },
        ),
        confirmation_status=confirmation_status,
    )

    with pytest.raises(TicketConfirmationRequiredError):
        await tool.create_from_state(state)

    assert service.create_calls == []


@pytest.mark.asyncio
async def test_creation_tool_creates_confirmed_ticket() -> None:
    service = FakeTicketService()
    tool = ConfirmedTicketCreationTool(service)
    state = AgentState(
        actor="alice",
        user_message="创建一个 VPN 工单",
        intent=AgentIntent.TICKET_CREATE,
        pending_action=PendingAction(
            action_type="ticket.create",
            arguments={
                "title": "VPN 无法连接",
                "description": "测试工单内容。",
                "priority": "high",
            },
        ),
        confirmation_status=ConfirmationStatus.CONFIRMED,
    )

    ticket = await tool.create_from_state(state)

    assert ticket.id == "ticket-001"
    assert len(service.create_calls) == 1
    assert service.create_calls[0][0].priority == TicketPriority.HIGH
    assert service.create_calls[0][1] == "alice"