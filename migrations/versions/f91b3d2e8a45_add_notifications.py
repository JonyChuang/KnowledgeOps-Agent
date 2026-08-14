"""add notifications

Revision ID: f91b3d2e8a45
Revises: e52a7d9c4f10
Create Date: 2026-08-13 17:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f91b3d2e8a45"
down_revision: str | Sequence[str] | None = "e52a7d9c4f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("recipient", sa.String(length=120), nullable=False),
        sa.Column(
            "type",
            sa.Enum("ticket", "system", name="notification_type", native_enum=False),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("target_view", sa.String(length=40), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_notifications_recipient"), ["recipient"], unique=False)
        batch_op.create_index(batch_op.f("ix_notifications_type"), ["type"], unique=False)
        batch_op.create_index(batch_op.f("ix_notifications_entity_type"), ["entity_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_notifications_entity_id"), ["entity_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_notifications_is_read"), ["is_read"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_notifications_is_read"))
        batch_op.drop_index(batch_op.f("ix_notifications_entity_id"))
        batch_op.drop_index(batch_op.f("ix_notifications_entity_type"))
        batch_op.drop_index(batch_op.f("ix_notifications_type"))
        batch_op.drop_index(batch_op.f("ix_notifications_recipient"))
    op.drop_table("notifications")
