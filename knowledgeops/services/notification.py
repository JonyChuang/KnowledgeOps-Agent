"""Business operations for recipient-scoped notification history."""

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Notification, NotificationType
from ..repositories import NotificationRepository
from .knowledge import ResourceNotFoundError


class NotificationService:
    """Create and read notifications without leaking them across recipients."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.notifications = NotificationRepository(session)

    async def notify(
        self,
        *,
        recipient: str,
        title: str,
        content: str,
        entity_type: str,
        entity_id: str,
        target_view: str,
        notification_type: NotificationType = NotificationType.TICKET,
    ) -> Notification:
        return await self.notifications.create(
            Notification(
                recipient=recipient,
                title=title,
                content=content,
                entity_type=entity_type,
                entity_id=entity_id,
                target_view=target_view,
                type=notification_type,
            )
        )

    async def list_notifications(
        self,
        *,
        recipient: str,
        unread_only: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Notification], int, int]:
        items = await self.notifications.list_for_recipient(
            recipient=recipient,
            unread_only=unread_only,
            limit=limit,
            offset=offset,
        )
        total = await self.notifications.count_for_recipient(
            recipient=recipient,
            unread_only=unread_only,
        )
        unread_count = await self.notifications.count_unread_for_recipient(recipient=recipient)
        return items, total, unread_count

    async def mark_read(self, notification_id: str, *, recipient: str) -> Notification:
        notification = await self.notifications.get_for_recipient(notification_id, recipient=recipient)
        if notification is None:
            raise ResourceNotFoundError("Notification not found.")
        if not notification.is_read:
            from ..models.base import utc_now

            notification.is_read = True
            notification.read_at = utc_now()
            await self.session.commit()
        return notification

    async def mark_all_read(self, *, recipient: str) -> int:
        count = await self.notifications.mark_all_read(recipient=recipient)
        await self.session.commit()
        return count
