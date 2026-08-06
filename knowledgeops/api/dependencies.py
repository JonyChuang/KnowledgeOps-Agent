"""FastAPI dependencies shared by all HTTP routers."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import Database


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide one database session for a single HTTP request."""
    database: Database = request.app.state.database

    async for session in database.session():
        yield session