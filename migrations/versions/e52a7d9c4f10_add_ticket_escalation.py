"""add ticket escalation level

Revision ID: e52a7d9c4f10
Revises: c4d1e9f7a32b
Create Date: 2026-08-13 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e52a7d9c4f10"
down_revision: str | Sequence[str] | None = "c4d1e9f7a32b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tickets", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "escalation_level",
                sa.Enum(
                    "none",
                    "team_lead",
                    "manager",
                    name="ticket_escalation_level",
                    native_enum=False,
                ),
                nullable=False,
                server_default="none",
            )
        )
        batch_op.create_index(
            batch_op.f("ix_tickets_escalation_level"),
            ["escalation_level"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("tickets", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tickets_escalation_level"))
        batch_op.drop_column("escalation_level")
