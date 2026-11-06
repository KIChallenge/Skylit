"""Store the simulated SV data query on the profile.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("svnr", sa.Text(), nullable=True))
    op.add_column(
        "profiles",
        sa.Column("sv_record", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "profiles",
        sa.Column("sv_retrieved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("profiles", "sv_retrieved_at")
    op.drop_column("profiles", "sv_record")
    op.drop_column("profiles", "svnr")
