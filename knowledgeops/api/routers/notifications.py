"""Recipient-scoped notification center endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...schemas import NotificationListRead, NotificationRead
from ...services import NotificationService, ResourceNotFoundError
from ..dependencies import get_actor, get_session

notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])


@notifications_router.get("", response_model=NotificationListRead)
async def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> NotificationListRead:
    """List only the current actor's notifications with their unread total."""
    items, total, unread_count = await NotificationService(session).list_notifications(
        recipient=actor,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    return NotificationListRead(
        items=[NotificationRead.model_validate(item) for item in items],
        total=total,
        unread_count=unread_count,
        limit=limit,
        offset=offset,
    )


@notifications_router.post("/read-all", response_model=dict[str, int])
async def mark_all_notifications_read(
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> dict[str, int]:
    """Mark every unread notification for the current actor as read."""
    count = await NotificationService(session).mark_all_read(recipient=actor)
    return {"updated_count": count}


@notifications_router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: str,
    session: AsyncSession = Depends(get_session),
    actor: str = Depends(get_actor),
) -> NotificationRead:
    """Mark one owned notification read before following its target link."""
    try:
        notification = await NotificationService(session).mark_read(
            notification_id,
            recipient=actor,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return NotificationRead.model_validate(notification)
