"""Verify that Alembic can build a fresh KnowledgeOps database."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


# The repository root is needed because Alembic reads alembic.ini from here.
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_alembic_upgrade_creates_knowledgeops_tables(tmp_path):
    """Alembic should create all domain tables in a brand-new SQLite database."""
    # Use a temporary database, so the test never depends on local knowledgeops.db.
    database_path = tmp_path / "migration-test.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"

    # Preserve the current environment, then override only this test's database.
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    environment["AUTO_CREATE_SCHEMA"] = "false"

    # Run the same Alembic command used in deployment, in a separate process.
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    # Print Alembic output when the test fails, making migration errors diagnosable.
    assert result.returncode == 0, (
        f"Alembic migration failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    # Inspect the generated SQLite database with the standard library.
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()

    table_names = {row[0] for row in rows}

    # Alembic's version table and all four business tables must exist.
    assert {
        "alembic_version",
        "knowledge_bases",
        "documents",
        "document_chunks",
        "audit_events",
    }.issubset(table_names)