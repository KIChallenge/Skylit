"""Mark the provider source and allow providers without a phone number.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # "demo" for invented providers, "wien_ogd" for Stadt Wien open data.
    op.add_column(
        "providers",
        sa.Column("source", sa.Text(), server_default="demo", nullable=False),
    )
    op.add_column("providers", sa.Column("website", sa.Text(), nullable=True))
    op.alter_column("providers", "phone", existing_type=sa.Text(), nullable=True)
    op.create_index("ix_providers_kind", "providers", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_providers_kind", table_name="providers")
    op.execute("DELETE FROM providers WHERE source <> 'demo'")
    op.alter_column("providers", "phone", existing_type=sa.Text(), nullable=False)
    op.drop_column("providers", "website")
    op.drop_column("providers", "source")
