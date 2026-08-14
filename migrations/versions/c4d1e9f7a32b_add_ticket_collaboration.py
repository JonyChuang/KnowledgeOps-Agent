"""add ticket collaboration records

Revision ID: c4d1e9f7a32b
Revises: a8105c4e7b2d
Create Date: 2026-08-13 15:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d1e9f7a32b"
down_revision: str | Sequence[str] | None = "a8105c4e7b2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tickets", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("category", sa.String(length=80), nullable=False, server_default="general")
        )
        batch_op.add_column(
            sa.Column(
                "impact",
                sa.Enum(
                    "single_user",
                    "team",
                    "department",
                    "company",
                    name="ticket_impact",
                    native_enum=False,
                ),
                nullable=False,
                server_default="single_user",
            )
        )
        batch_op.add_column(sa.Column("assignee", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f("ix_tickets_category"), ["category"], unique=False)
        batch_op.create_index(batch_op.f("ix_tickets_sla_due_at"), ["sla_due_at"], unique=False)

    op.create_table(
        "ticket_activities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ticket_activities", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ticket_activities_ticket_id"), ["ticket_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_ticket_activities_event_type"), ["event_type"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("ticket_activities", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ticket_activities_event_type"))
        batch_op.drop_index(batch_op.f("ix_ticket_activities_ticket_id"))
    op.drop_table("ticket_activities")

    with op.batch_alter_table("tickets", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tickets_sla_due_at"))
        batch_op.drop_index(batch_op.f("ix_tickets_category"))
        batch_op.drop_column("sla_due_at")
        batch_op.drop_column("assignee")
        batch_op.drop_column("impact")
        batch_op.drop_column("category")
