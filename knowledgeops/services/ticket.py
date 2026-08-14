"""Business rules for ticket creation and lookup."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    AuditEvent,
    NotificationType,
    Ticket,
    TicketActivity,
    TicketEscalationLevel,
    TicketPriority,
    TicketStatus,
)
from ..repositories import AuditEventRepository, TicketRepository
from ..schemas import TicketCreate
from .knowledge import ResourceNotFoundError
from .notification import NotificationService


class TicketService:
    """Coordinate ticket persistence, requester isolation, and auditing."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.tickets = TicketRepository(session)
        self.audit_events = AuditEventRepository(session)
        self.notifications = NotificationService(session)

    async def create_ticket(
        self,
        payload: TicketCreate,
        *,
        actor: str,
    ) -> Ticket:
        """Persist a ticket and append a safe audit event."""
        ticket = await self.tickets.create(
            Ticket(
                title=payload.title,
                description=payload.description,
                category=payload.category,
                impact=payload.impact,
                priority=payload.priority,
                status=TicketStatus.OPEN,
                requester=actor,
                sla_due_at=self._sla_due_at(payload.priority),
            )
        )
        await self.tickets.create_activity(
            TicketActivity(
                ticket_id=ticket.id,
                event_type="ticket.created",
                actor=actor,
                content="已提交服务请求。",
                details={
                    "status": ticket.status.value,
                    "priority": ticket.priority.value,
                    "category": ticket.category,
                },
            )
        )

        await self.audit_events.create(
            AuditEvent(
                event_type="ticket.created",
                actor=actor,
                entity_type="ticket",
                entity_id=ticket.id,
                payload={
                    "priority": ticket.priority.value,
                    "status": ticket.status.value,
                    "category": ticket.category,
                },
            )
        )

        await self.session.commit()
        await self.session.refresh(ticket)
        return ticket

    async def get_ticket_detail(
        self,
        ticket_id: str,
        *,
        actor: str,
    ) -> Ticket:
        """Return an employee-owned ticket and its immutable activity history."""
        ticket = await self.tickets.get_detail_for_requester(
            ticket_id,
            requester=actor,
        )
        if ticket is None:
            raise ResourceNotFoundError("Ticket not found.")
        return ticket

    async def add_requester_comment(
        self,
        ticket_id: str,
        content: str,
        *,
        actor: str,
    ) -> Ticket:
        """Let the requester add information while preserving a full timeline."""
        ticket = await self.get_ticket(ticket_id, actor=actor)
        if ticket.status == TicketStatus.CLOSED:
            raise ValueError("Closed tickets cannot receive more information.")

        await self.tickets.create_activity(
            TicketActivity(
                ticket_id=ticket.id,
                event_type="requester.comment_added",
                actor=actor,
                content=content.strip(),
                details={},
            )
        )
        await self.audit_events.create(
            AuditEvent(
                event_type="ticket.comment_added",
                actor=actor,
                entity_type="ticket",
                entity_id=ticket.id,
                payload={},
            )
        )
        if ticket.status == TicketStatus.AWAITING_REQUESTER:
            previous_status = ticket.status
            ticket.status = TicketStatus.IN_PROGRESS
            await self._record_status_change(
                ticket,
                actor=actor,
                previous_status=previous_status,
                reason="请求人已补充信息，等待服务团队继续处理。",
            )
        if ticket.assignee:
            await self._notify_ticket(
                recipient=ticket.assignee,
                actor=actor,
                ticket=ticket,
                title="申请人补充了工单信息",
                content=f"申请人已补充工单“{ticket.title}”的信息，请继续处理。",
                target_view="service-desk",
            )
        await self.session.commit()
        return await self.get_ticket_detail(ticket.id, actor=actor)

    async def list_service_desk_tickets(
        self,
        *,
        operator: str,
        scope: str,
        status: TicketStatus | None = None,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Ticket]:
        """Expose the operational queue only to the service-desk router."""
        return await self.tickets.list_for_service_desk(
            operator=operator,
            scope=scope,
            status=status,
            query=query,
            limit=limit,
            offset=offset,
        )

    async def count_service_desk_tickets(
        self,
        *,
        operator: str,
        scope: str,
        status: TicketStatus | None = None,
        query: str | None = None,
    ) -> int:
        """Count the service-desk queue with the same scope and filters."""
        return await self.tickets.count_for_service_desk(
            operator=operator,
            scope=scope,
            status=status,
            query=query,
        )

    async def get_service_desk_ticket_detail(self, ticket_id: str) -> Ticket:
        """Read any ticket from the service queue after role authorization."""
        ticket = await self.tickets.get_detail(ticket_id)
        if ticket is None:
            raise ResourceNotFoundError("Ticket not found.")
        return ticket

    async def accept_ticket(self, ticket_id: str, *, operator: str) -> Ticket:
        """Claim an unassigned open ticket and begin processing it."""
        ticket = await self.get_service_desk_ticket_detail(ticket_id)
        if ticket.status != TicketStatus.OPEN:
            raise ValueError("Only open tickets can be accepted.")
        if ticket.assignee and ticket.assignee != operator:
            raise ValueError("This ticket has already been assigned to another operator.")

        previous_status = ticket.status
        ticket.assignee = operator
        ticket.status = TicketStatus.IN_PROGRESS
        await self._record_status_change(
            ticket,
            actor=operator,
            previous_status=previous_status,
            reason="工单已受理，开始处理。",
            event_type="ticket.accepted",
        )
        await self._notify_ticket(
            recipient=ticket.requester,
            actor=operator,
            ticket=ticket,
            title="工单已受理",
            content=f"{operator} 已受理你的工单“{ticket.title}”，正在开始处理。",
            target_view="tickets",
        )
        await self.session.commit()
        return await self.get_service_desk_ticket_detail(ticket.id)

    async def assign_ticket(
        self,
        ticket_id: str,
        assignee: str,
        *,
        operator: str,
    ) -> Ticket:
        """Assign an open ticket or hand off active work to another operator."""
        ticket = await self.get_service_desk_ticket_detail(ticket_id)
        if ticket.status not in {TicketStatus.OPEN, TicketStatus.IN_PROGRESS}:
            raise ValueError("Only open or in-progress tickets can be assigned.")
        if ticket.status == TicketStatus.IN_PROGRESS and ticket.assignee != operator:
            raise ValueError("Only the assigned operator can transfer an in-progress ticket.")
        if ticket.status == TicketStatus.OPEN and ticket.assignee and ticket.assignee != operator:
            raise ValueError("Only the assigned operator can change an open ticket assignment.")

        previous_assignee = ticket.assignee
        normalized_assignee = assignee.strip()
        if normalized_assignee == previous_assignee:
            raise ValueError("This ticket is already assigned to that operator.")

        ticket.assignee = normalized_assignee
        await self.tickets.create_activity(
            TicketActivity(
                ticket_id=ticket.id,
                event_type="ticket.assigned",
                actor=operator,
                content=f"已转派给 {normalized_assignee}。",
                details={
                    "from_assignee": previous_assignee,
                    "to_assignee": normalized_assignee,
                },
            )
        )
        await self.audit_events.create(
            AuditEvent(
                event_type="ticket.assigned",
                actor=operator,
                entity_type="ticket",
                entity_id=ticket.id,
                payload={
                    "from_assignee": previous_assignee,
                    "to_assignee": normalized_assignee,
                },
            )
        )
        await self._notify_ticket(
            recipient=normalized_assignee,
            actor=operator,
            ticket=ticket,
            title="有工单转派给你",
            content=f"{operator} 将工单“{ticket.title}”转派给你，请及时处理。",
            target_view="service-desk",
        )
        await self._notify_ticket(
            recipient=ticket.requester,
            actor=operator,
            ticket=ticket,
            title="工单已转派",
            content=f"你的工单“{ticket.title}”已转派给 {normalized_assignee} 继续处理。",
            target_view="tickets",
        )
        await self.session.commit()
        return await self.get_service_desk_ticket_detail(ticket.id)

    async def request_requester_information(
        self,
        ticket_id: str,
        reason: str,
        *,
        operator: str,
    ) -> Ticket:
        """Pause active work until the requester supplies a needed detail."""
        return await self._transition_for_service_desk(
            ticket_id,
            target_status=TicketStatus.AWAITING_REQUESTER,
            reason=reason,
            operator=operator,
        )

    async def update_ticket_priority(
        self,
        ticket_id: str,
        priority: TicketPriority,
        reason: str,
        *,
        operator: str,
    ) -> Ticket:
        """Change an active ticket's urgency without changing its owner or state."""
        ticket = await self._require_assigned_active_ticket(ticket_id, operator=operator)
        previous_priority = ticket.priority
        if priority == previous_priority:
            raise ValueError("This ticket already has that priority.")

        ticket.priority = priority
        ticket.sla_due_at = self._sla_due_at(priority)
        await self._record_activity(
            ticket,
            actor=operator,
            event_type="ticket.priority_changed",
            content=reason.strip(),
            details={
                "from_priority": previous_priority.value,
                "to_priority": priority.value,
            },
        )
        await self._notify_ticket(
            recipient=ticket.requester,
            actor=operator,
            ticket=ticket,
            title="工单优先级已调整",
            content=f"你的工单“{ticket.title}”已调整为{priority.value}优先级：{reason.strip()}",
            target_view="tickets",
        )
        await self.session.commit()
        return await self.get_service_desk_ticket_detail(ticket.id)

    async def escalate_ticket(
        self,
        ticket_id: str,
        level: TicketEscalationLevel,
        reason: str,
        *,
        operator: str,
    ) -> Ticket:
        """Escalate an active ticket while preserving its current lifecycle state."""
        ticket = await self._require_assigned_active_ticket(ticket_id, operator=operator)
        if level == TicketEscalationLevel.NONE:
            raise ValueError("Choose a higher escalation level for this action.")
        if level == ticket.escalation_level:
            raise ValueError("This ticket is already at that escalation level.")

        previous_level = ticket.escalation_level
        ticket.escalation_level = level
        await self._record_activity(
            ticket,
            actor=operator,
            event_type="ticket.escalated",
            content=reason.strip(),
            details={
                "from_level": previous_level.value,
                "to_level": level.value,
            },
        )
        await self._notify_ticket(
            recipient=ticket.requester,
            actor=operator,
            ticket=ticket,
            title="工单已升级处理",
            content=f"你的工单“{ticket.title}”已升级至{level.value}处理：{reason.strip()}",
            target_view="tickets",
        )
        await self.session.commit()
        return await self.get_service_desk_ticket_detail(ticket.id)

    async def resolve_ticket(
        self,
        ticket_id: str,
        resolution: str,
        *,
        operator: str,
    ) -> Ticket:
        """Mark an in-progress ticket solved with a requester-visible result."""
        return await self._transition_for_service_desk(
            ticket_id,
            target_status=TicketStatus.RESOLVED,
            reason=resolution,
            operator=operator,
        )

    async def _transition_for_service_desk(
        self,
        ticket_id: str,
        *,
        target_status: TicketStatus,
        reason: str,
        operator: str,
    ) -> Ticket:
        ticket = await self._require_assigned_active_ticket(ticket_id, operator=operator)

        ticket.status = target_status
        await self._record_status_change(
            ticket,
            actor=operator,
            previous_status=TicketStatus.IN_PROGRESS,
            reason=reason.strip(),
        )
        if target_status == TicketStatus.AWAITING_REQUESTER:
            await self._notify_ticket(
                recipient=ticket.requester,
                actor=operator,
                ticket=ticket,
                title="工单需要你补充信息",
                content=f"请补充工单“{ticket.title}”所需信息：{reason.strip()}",
                target_view="tickets",
            )
        elif target_status == TicketStatus.RESOLVED:
            await self._notify_ticket(
                recipient=ticket.requester,
                actor=operator,
                ticket=ticket,
                title="工单已标记解决",
                content=f"工单“{ticket.title}”已有处理结果：{reason.strip()}",
                target_view="tickets",
            )
        await self.session.commit()
        return await self.get_service_desk_ticket_detail(ticket.id)

    async def _require_assigned_active_ticket(
        self,
        ticket_id: str,
        *,
        operator: str,
    ) -> Ticket:
        ticket = await self.get_service_desk_ticket_detail(ticket_id)
        if ticket.status != TicketStatus.IN_PROGRESS:
            raise ValueError("Only in-progress tickets can be updated by the service desk.")
        if ticket.assignee != operator:
            raise ValueError("Only the assigned operator can update this ticket.")
        return ticket

    async def confirm_resolution(
        self,
        ticket_id: str,
        *,
        actor: str,
    ) -> Ticket:
        """Allow the requester to close only a ticket already marked resolved."""
        ticket = await self.get_ticket(ticket_id, actor=actor)
        if ticket.status != TicketStatus.RESOLVED:
            raise ValueError("Only resolved tickets can be confirmed and closed.")
        previous_status = ticket.status
        ticket.status = TicketStatus.CLOSED
        await self._record_status_change(
            ticket,
            actor=actor,
            previous_status=previous_status,
            reason="请求人已确认解决。",
        )
        if ticket.assignee:
            await self._notify_ticket(
                recipient=ticket.assignee,
                actor=actor,
                ticket=ticket,
                title="工单已确认关闭",
                content=f"申请人已确认工单“{ticket.title}”解决，工单现已关闭。",
                target_view="service-desk",
            )
        await self.session.commit()
        return await self.get_ticket_detail(ticket.id, actor=actor)

    async def reopen_ticket(
        self,
        ticket_id: str,
        reason: str,
        *,
        actor: str,
    ) -> Ticket:
        """Reopen a resolved ticket when the requester provides a reason."""
        ticket = await self.get_ticket(ticket_id, actor=actor)
        if ticket.status != TicketStatus.RESOLVED:
            raise ValueError("Only resolved tickets can be reopened.")
        previous_status = ticket.status
        ticket.status = TicketStatus.IN_PROGRESS
        await self._record_status_change(
            ticket,
            actor=actor,
            previous_status=previous_status,
            reason=reason.strip(),
            event_type="ticket.reopened",
        )
        if ticket.assignee:
            await self._notify_ticket(
                recipient=ticket.assignee,
                actor=actor,
                ticket=ticket,
                title="工单已重新打开",
                content=f"申请人重新打开了工单“{ticket.title}”：{reason.strip()}",
                target_view="service-desk",
            )
        await self.session.commit()
        return await self.get_ticket_detail(ticket.id, actor=actor)

    async def _record_status_change(
        self,
        ticket: Ticket,
        *,
        actor: str,
        previous_status: TicketStatus,
        reason: str,
        event_type: str = "ticket.status_changed",
    ) -> None:
        await self._record_activity(
            ticket,
            actor=actor,
            event_type=event_type,
            content=reason,
            details={
                "from_status": previous_status.value,
                "to_status": ticket.status.value,
            },
        )

    async def _record_activity(
        self,
        ticket: Ticket,
        *,
        actor: str,
        event_type: str,
        content: str,
        details: dict[str, object],
    ) -> None:
        """Append matching customer-visible and audit events for an operation."""
        await self.tickets.create_activity(
            TicketActivity(
                ticket_id=ticket.id,
                event_type=event_type,
                actor=actor,
                content=content,
                details=details,
            )
        )
        await self.audit_events.create(
            AuditEvent(
                event_type=event_type,
                actor=actor,
                entity_type="ticket",
                entity_id=ticket.id,
                payload=details,
            )
        )

    async def _notify_ticket(
        self,
        *,
        recipient: str,
        actor: str,
        ticket: Ticket,
        title: str,
        content: str,
        target_view: str,
    ) -> None:
        """Append a recipient-scoped notification as part of the ticket transaction."""
        if recipient.strip() == actor.strip():
            return
        await self.notifications.notify(
            recipient=recipient,
            title=title,
            content=content,
            entity_type="ticket",
            entity_id=ticket.id,
            target_view=target_view,
            notification_type=NotificationType.TICKET,
        )

    @staticmethod
    def _sla_due_at(priority: TicketPriority):
        """Use transparent service targets until per-category SLA policy is added."""
        hours = {
            TicketPriority.LOW: 72,
            TicketPriority.MEDIUM: 24,
            TicketPriority.HIGH: 8,
            TicketPriority.URGENT: 2,
        }[priority]
        from ..models.base import utc_now

        return utc_now() + timedelta(hours=hours)

    async def get_ticket(
        self,
        ticket_id: str,
        *,
        actor: str,
    ) -> Ticket:
        """Return a ticket only when it belongs to the current actor."""
        ticket = await self.tickets.get_for_requester(
            ticket_id,
            requester=actor,
        )
        if ticket is None:
            raise ResourceNotFoundError("Ticket not found.")

        return ticket

    async def list_tickets(
        self,
        *,
        actor: str,
        status: TicketStatus | None = None,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Ticket]:
        """List only tickets belonging to the current actor."""
        return await self.tickets.list_for_requester(
            requester=actor,
            status=status,
            query=query,
            limit=limit,
            offset=offset,
        )

    async def count_tickets(
        self,
        *,
        actor: str,
        status: TicketStatus | None = None,
        query: str | None = None,
    ) -> int:
        """Return the total matching records for pagination metadata."""
        return await self.tickets.count_for_requester(
            requester=actor,
            status=status,
            query=query,
        )
