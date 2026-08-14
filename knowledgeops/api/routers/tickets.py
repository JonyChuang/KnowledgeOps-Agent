"""Employee ticket list and detail endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import TicketStatus
from ...schemas import (
    TicketCommentCreate,
    TicketCreate,
    TicketDetailRead,
    TicketListRead,
    TicketRead,
    TicketReopenCreate,
)
from ...services import ResourceNotFoundError, TicketService
from ..dependencies import get_actor, get_session

tickets_router = APIRouter(prefix="/tickets", tags=["tickets"])


@tickets_router.post("", response_model=TicketRead, status_code=201)
async def create_ticket(
    payload: TicketCreate,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> TicketRead:
    """Create a standardized employee service request outside Agent chat."""
    ticket = await TicketService(session).create_ticket(payload, actor=actor)
    return TicketRead.model_validate(ticket)


@tickets_router.get("", response_model=TicketListRead)
async def list_tickets(
    status: TicketStatus | None = None,
    query: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> TicketListRead:
    """Return a searchable, paginated ticket page for the current employee."""
    service = TicketService(session)
    items = await service.list_tickets(
        actor=actor,
        status=status,
        query=query,
        limit=limit,
        offset=offset,
    )
    total = await service.count_tickets(
        actor=actor,
        status=status,
        query=query,
    )
    return TicketListRead(
        items=[TicketRead.model_validate(ticket) for ticket in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@tickets_router.get("/{ticket_id}", response_model=TicketDetailRead)
async def get_ticket(
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> TicketDetailRead:
    """Return an employee-owned ticket together with its activity history."""
    try:
        ticket = await TicketService(session).get_ticket_detail(ticket_id, actor=actor)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return TicketDetailRead.model_validate(ticket)


@tickets_router.post("/{ticket_id}/comments", response_model=TicketDetailRead)
async def add_ticket_comment(
    ticket_id: str,
    payload: TicketCommentCreate,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> TicketDetailRead:
    """Let an employee append supplemental information to their active ticket."""
    try:
        ticket = await TicketService(session).add_requester_comment(
            ticket_id,
            payload.content,
            actor=actor,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return TicketDetailRead.model_validate(ticket)


@tickets_router.post("/{ticket_id}/confirm-resolution", response_model=TicketDetailRead)
async def confirm_ticket_resolution(
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> TicketDetailRead:
    """Close a resolved ticket after the requester confirms the outcome."""
    try:
        ticket = await TicketService(session).confirm_resolution(
            ticket_id,
            actor=actor,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return TicketDetailRead.model_validate(ticket)


@tickets_router.post("/{ticket_id}/reopen", response_model=TicketDetailRead)
async def reopen_ticket(
    ticket_id: str,
    payload: TicketReopenCreate,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> TicketDetailRead:
    """Return a resolved ticket to the service queue with a requester reason."""
    try:
        ticket = await TicketService(session).reopen_ticket(
            ticket_id,
            payload.reason,
            actor=actor,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return TicketDetailRead.model_validate(ticket)
