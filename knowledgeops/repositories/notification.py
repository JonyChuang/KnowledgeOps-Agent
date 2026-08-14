"""Data access methods for recipient-owned notifications."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Notification
from ..models.base import utc_now


class NotificationRepository:
    """Persist and read notifications without owning request transactions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, notification: Notification) -> Notification:
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def list_for_recipient(
        self,
        *,
        recipient: str,
        unread_only: bool,
        limit: int,
        offset: int,
    ) -> list[Notification]:
        statement = select(Notification).where(Notification.recipient == recipient)
        if unread_only:
            statement = statement.where(Notification.is_read.is_(False))
        result = await self.session.scalars(
            statement.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result)

    async def count_for_recipient(self, *, recipient: str, unread_only: bool) -> int:
        statement = select(func.count(Notification.id)).where(Notification.recipient == recipient)
        if unread_only:
            statement = statement.where(Notification.is_read.is_(False))
        count = await self.session.scalar(statement)
        return count or 0

    async def count_unread_for_recipient(self, *, recipient: str) -> int:
        return await self.count_for_recipient(recipient=recipient, unread_only=True)

    async def get_for_recipient(self, notification_id: str, *, recipient: str) -> Notification | None:
        return await self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.recipient == recipient,
            )
        )

    async def mark_all_read(self, *, recipient: str) -> int:
        items = await self.session.scalars(
            select(Notification).where(
                Notification.recipient == recipient,
                Notification.is_read.is_(False),
            )
        )
        count = 0
        for item in items:
            item.is_read = True
            item.read_at = utc_now()
            count += 1
        await self.session.flush()
        return count
