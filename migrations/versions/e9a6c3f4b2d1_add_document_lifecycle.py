"""add document business lifecycle

Revision ID: e9a6c3f4b2d1
Revises: da813a5b4c29
Create Date: 2026-08-15 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9a6c3f4b2d1"
down_revision: str | Sequence[str] | None = "da813a5b4c29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "lifecycle",
                sa.Enum(
                    "draft",
                    "active",
                    "archived",
                    name="document_lifecycle",
                    native_enum=False,
                ),
                nullable=False,
                server_default="active",
            )
        )
        batch_op.create_index(batch_op.f("ix_documents_lifecycle"), ["lifecycle"])


def downgrade() -> None:
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_documents_lifecycle"))
        batch_op.drop_column("lifecycle")
