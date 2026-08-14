import pytest
from sqlalchemy import select

from knowledgeops.db import Database
from knowledgeops.models import AuditEvent, TicketPriority, TicketStatus
from knowledgeops.schemas import TicketCreate
from knowledgeops.services import ResourceNotFoundError, TicketService


@pytest.mark.asyncio
async def test_ticket_service_creates_ticket_and_audit_event(tmp_path) -> None:
    database_path = (tmp_path / "tickets.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")

    try:
        await database.create_schema()

        async for session in database.session():
            service = TicketService(session)

            ticket = await service.create_ticket(
                TicketCreate(
                    title="VPN 无法连接",
                    description="员工无法连接企业 VPN。",
                    priority=TicketPriority.HIGH,
                ),
                actor="alice",
            )

        async for session in database.session():
            service = TicketService(session)
            saved_ticket = await service.get_ticket(
                ticket.id,
                actor="alice",
            )
            event = await session.scalar(
                select(AuditEvent)
                .where(AuditEvent.entity_id == ticket.id)
                .order_by(AuditEvent.created_at.desc())
            )

            assert saved_ticket.id == ticket.id
            assert saved_ticket.requester == "alice"
            assert saved_ticket.priority == TicketPriority.HIGH
            assert saved_ticket.status == TicketStatus.OPEN
            assert saved_ticket.sla_due_at is not None
            assert event is not None
            assert event.event_type == "ticket.created"
            assert "description" not in event.payload
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_ticket_service_records_requester_collaboration_timeline(tmp_path) -> None:
    database_path = (tmp_path / "ticket-collaboration.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")

    try:
        await database.create_schema()

        async for session in database.session():
            service = TicketService(session)
            ticket = await service.create_ticket(
                TicketCreate(
                    title="VPN 无法连接",
                    description="登录后无法访问内网。",
                    priority=TicketPriority.HIGH,
                    category="network",
                ),
                actor="alice",
            )
            after_comment = await service.add_requester_comment(
                ticket.id,
                "已补充错误截图和发生时间。",
                actor="alice",
            )

            assert [item.event_type for item in after_comment.activities] == [
                "ticket.created",
                "requester.comment_added",
            ]
            assert after_comment.category == "network"
            assert after_comment.sla_due_at is not None

            ticket.status = TicketStatus.RESOLVED
            await session.commit()
            reopened = await service.reopen_ticket(
                ticket.id,
                "问题仍然存在，请继续处理。",
                actor="alice",
            )

            assert reopened.status == TicketStatus.IN_PROGRESS
            assert reopened.activities[-1].event_type == "ticket.reopened"
            assert reopened.activities[-1].details == {
                "from_status": "resolved",
                "to_status": "in_progress",
            }
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_ticket_service_isolates_tickets_by_requester(tmp_path) -> None:
    database_path = (tmp_path / "ticket-isolation.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")

    try:
        await database.create_schema()

        async for session in database.session():
            service = TicketService(session)
            ticket = await service.create_ticket(
                TicketCreate(
                    title="账号被锁定",
                    description="测试工单。",
                ),
                actor="alice",
            )

        async for session in database.session():
            service = TicketService(session)

            with pytest.raises(ResourceNotFoundError):
                await service.get_ticket(ticket.id, actor="bob")

            tickets = await service.list_tickets(actor="bob")

            assert tickets == []
    finally:
        await database.dispose()
