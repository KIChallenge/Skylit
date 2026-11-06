"""Add personal calendar entries.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calendar_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("all_day", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("ix_calendar_entries_user_id", "calendar_entries", ["user_id"])
    # One calendar entry per saved appointment proposal.
    op.create_index(
        "uq_calendar_entries_appointment",
        "calendar_entries",
        ["appointment_id"],
        unique=True,
        postgresql_where=sa.text("appointment_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_calendar_entries_appointment", table_name="calendar_entries")
    op.drop_index("ix_calendar_entries_user_id", table_name="calendar_entries")
    op.drop_table("calendar_entries")
