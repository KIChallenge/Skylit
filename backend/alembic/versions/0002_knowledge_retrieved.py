"""Store the retrieval date of each knowledge document.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents", sa.Column("retrieved", sa.Date(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("knowledge_documents", "retrieved")
