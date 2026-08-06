"""Tests for the database infrastructure without requiring PostgreSQL."""

import pytest
from sqlalchemy import text

from knowledgeops.db import Database


@pytest.mark.asyncio
async def test_database_session_executes_query(tmp_path):
    # A temporary SQLite file keeps this test isolated from local data.
    database_path = (tmp_path / "knowledgeops.db").as_posix()
    database = Database(f"sqlite+aiosqlite:///{database_path}")

    try:
        async for session in database.session():
            result = await session.execute(text("SELECT 1"))
            assert result.scalar_one() == 1
    finally:
        # Tests must release the engine so Windows can remove temporary files.
        await database.dispose()