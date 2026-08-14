"""Service-desk ticket queue and lifecycle action endpoints."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import TicketStatus
from ...schemas import (
    TicketAssignCreate,
    TicketDetailRead,
    TicketEscalateCreate,
    TicketListRead,
    TicketPriorityUpdateCreate,
    TicketRead,
    TicketWorkflowReasonCreate,
)
from ...services import ResourceNotFoundError, TicketService
from ..dependencies import get_service_desk_actor, get_session

service_desk_router = APIRouter(prefix="/service-desk/tickets", tags=["service-desk"])


@service_desk_router.get("", response_model=TicketListRead)
async def list_service_desk_tickets(
    scope: Literal["all", "mine", "unassigned"] = "mine",
    status: TicketStatus | None = None,
    query: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    operator: str = Depends(get_service_desk_actor),
) -> TicketListRead:
    """Return an operator-scoped queue after explicit service-desk authorization."""
    service = TicketService(session)
    items = await service.list_service_desk_tickets(
        operator=operator,
        scope=scope,
        status=status,
        query=query,
        limit=limit,
        offset=offset,
    )
    total = await service.count_service_desk_tickets(
        operator=operator,
        scope=scope,
        status=status,
        query=query,
    )
    return TicketListRead(
        items=[TicketRead.model_validate(ticket) for ticket in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@service_desk_router.get("/{ticket_id}", response_model=TicketDetailRead)
async def get_service_desk_ticket(
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(get_service_desk_actor),
) -> TicketDetailRead:
    """Return one ticket's details for a service-desk operator."""
    try:
        ticket = await TicketService(session).get_service_desk_ticket_detail(ticket_id)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return TicketDetailRead.model_validate(ticket)


@service_desk_router.post("/{ticket_id}/accept", response_model=TicketDetailRead)
async def accept_service_desk_ticket(
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
    operator: str = Depends(get_service_desk_actor),
) -> TicketDetailRead:
    """Let an operator claim one unassigned open ticket."""
    try:
        ticket = await TicketService(session).accept_ticket(ticket_id, operator=operator)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return TicketDetailRead.model_validate(ticket)


@service_desk_router.post("/{ticket_id}/assign", response_model=TicketDetailRead)
async def assign_service_desk_ticket(
    ticket_id: str,
    payload: TicketAssignCreate,
    session: AsyncSession = Depends(get_session),
    operator: str = Depends(get_service_desk_actor),
) -> TicketDetailRead:
    """Transfer an active ticket to a named operator."""
    try:
        ticket = await TicketService(session).assign_ticket(
            ticket_id,
            payload.assignee,
            operator=operator,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return TicketDetailRead.model_validate(ticket)


@service_desk_router.post("/{ticket_id}/request-information", response_model=TicketDetailRead)
async def request_service_desk_information(
    ticket_id: str,
    payload: TicketWorkflowReasonCreate,
    session: AsyncSession = Depends(get_session),
    operator: str = Depends(get_service_desk_actor),
) -> TicketDetailRead:
    """Ask the requester for a specific missing piece of information."""
    try:
        ticket = await TicketService(session).request_requester_information(
            ticket_id,
            payload.reason,
            operator=operator,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return TicketDetailRead.model_validate(ticket)


@service_desk_router.post("/{ticket_id}/priority", response_model=TicketDetailRead)
async def update_service_desk_ticket_priority(
    ticket_id: str,
    payload: TicketPriorityUpdateCreate,
    session: AsyncSession = Depends(get_session),
    operator: str = Depends(get_service_desk_actor),
) -> TicketDetailRead:
    """Update the priority and recalculate the ticket's current SLA target."""
    try:
        ticket = await TicketService(session).update_ticket_priority(
            ticket_id,
            payload.priority,
            payload.reason,
            operator=operator,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return TicketDetailRead.model_validate(ticket)


@service_desk_router.post("/{ticket_id}/escalate", response_model=TicketDetailRead)
async def escalate_service_desk_ticket(
    ticket_id: str,
    payload: TicketEscalateCreate,
    session: AsyncSession = Depends(get_session),
    operator: str = Depends(get_service_desk_actor),
) -> TicketDetailRead:
    """Escalate an assigned active ticket to a higher support level."""
    try:
        ticket = await TicketService(session).escalate_ticket(
            ticket_id,
            payload.level,
            payload.reason,
            operator=operator,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return TicketDetailRead.model_validate(ticket)


@service_desk_router.post("/{ticket_id}/resolve", response_model=TicketDetailRead)
async def resolve_service_desk_ticket(
    ticket_id: str,
    payload: TicketWorkflowReasonCreate,
    session: AsyncSession = Depends(get_session),
    operator: str = Depends(get_service_desk_actor),
) -> TicketDetailRead:
    """Mark an assigned in-progress ticket as resolved."""
    try:
        ticket = await TicketService(session).resolve_ticket(
            ticket_id,
            payload.reason,
            operator=operator,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return TicketDetailRead.model_validate(ticket)
