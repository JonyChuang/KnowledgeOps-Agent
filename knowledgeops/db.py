"""Async database infrastructure shared by API routes and background tasks."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import Settings


class Database:
    """Owns one database engine and creates request-scoped sessions."""

    def __init__(self, database_url: str):
        # SQLite is used locally; PostgreSQL is used by the Docker deployment.
        is_sqlite = database_url.startswith("sqlite")

        self.engine: AsyncEngine = create_async_engine(
            database_url,
            future=True,
            # Check pooled PostgreSQL connections before every reuse.
            pool_pre_ping=not is_sqlite,
            # SQLite needs this option when accessed through test threads.
            connect_args={"check_same_thread": False} if is_sqlite else {},
        )

        # expire_on_commit=False lets API code return newly saved objects
        # without unexpectedly triggering another database query.
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield one session and guarantee that it is closed afterwards."""
        async with self.session_factory() as session:
            yield session

    async def create_schema(self) -> None:
        """Create all tables for local development and SQLite-based tests."""
        # Import inside the method to avoid a circular import during startup.
        from .models import Base

        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        """Release database connections during application shutdown."""
        await self.engine.dispose()


def create_database(settings: Settings) -> Database:
    """Build the application database from central configuration."""
    return Database(settings.database_url)