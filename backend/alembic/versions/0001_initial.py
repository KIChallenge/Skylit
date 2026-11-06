"""Create the initial application and hybrid retrieval schema.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        )
    ]


def record_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        *timestamps(),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "users",
        *record_columns(),
        sa.Column("persona_id", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("tagline", sa.Text(), nullable=False),
        sa.Column("avatar_emoji", sa.Text(), nullable=False),
    )
    op.create_table(
        "profiles",
        *record_columns(),
        sa.Column(
            "user_id",
            pg.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("language", sa.Text(), nullable=False, server_default="de"),
        sa.Column("depth", sa.Text(), nullable=False, server_default="short"),
        sa.Column("bundesland", sa.Text()),
        sa.Column("postal_code", sa.Text()),
        sa.Column("insurer", sa.Text()),
        sa.Column("date_of_birth", sa.Date()),
        sa.Column(
            "extra", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
    )
    op.create_table(
        "leistungen",
        *timestamps(),
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("short", sa.Text(), nullable=False),
        sa.Column(
            "conditions",
            pg.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("office_kind", sa.Text(), nullable=False),
        sa.Column(
            "form_ids",
            pg.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "documents_needed",
            pg.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
    )
    op.create_table(
        "offices",
        *timestamps(),
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("organisation", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("bundesland", sa.Text(), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("postal_code", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("email", sa.Text()),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("hours", sa.Text()),
        sa.Column("lat", sa.Float()),
        sa.Column("lon", sa.Float()),
        sa.Column("source_url", sa.Text()),
    )
    op.create_table(
        "providers",
        *timestamps(),
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("specialty", sa.Text()),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("postal_code", sa.Text(), nullable=False),
        sa.Column("lat", sa.Float()),
        sa.Column("lon", sa.Float()),
        sa.Column("phone", sa.Text(), nullable=False),
    )
    op.create_table(
        "conversations",
        *record_columns(),
        sa.Column(
            "user_id",
            pg.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False, server_default="Neuer Fall"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_table(
        "cases",
        *record_columns(),
        sa.Column(
            "conversation_id",
            pg.UUID(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("title", sa.Text(), nullable=False, server_default="Mein Fall"),
        sa.Column("subject", sa.Text(), nullable=False, server_default="self"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_table(
        "case_steps",
        *record_columns(),
        sa.Column(
            "case_id",
            pg.UUID(),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column(
            "leistung_id",
            sa.Text(),
            sa.ForeignKey("leistungen.id", ondelete="SET NULL"),
        ),
        sa.Column("due_hint", sa.Text()),
        sa.Column("related_card", pg.JSONB()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "documents",
        *record_columns(),
        sa.Column(
            "user_id",
            pg.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            pg.UUID(),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
        ),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="uploaded"),
        sa.Column("kind", sa.Text()),
        sa.Column("extracted", pg.JSONB()),
        sa.Column("error", sa.Text()),
    )
    op.create_table(
        "form_drafts",
        *record_columns(),
        sa.Column(
            "user_id",
            pg.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            pg.UUID(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("form_id", sa.Text(), nullable=False),
        sa.Column(
            "values", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "missing", pg.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("pdf_path", sa.Text()),
    )
    op.create_table(
        "appointments",
        *record_columns(),
        sa.Column(
            "user_id",
            pg.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            pg.UUID(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider_id", sa.Text(), sa.ForeignKey("providers.id"), nullable=False
        ),
        sa.Column("start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="booked"),
    )
    # Create the message/escalation cycle in two stages.
    op.create_table(
        "escalations",
        *record_columns(),
        sa.Column(
            "conversation_id",
            pg.UUID(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message_id", pg.UUID()),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("target", pg.JSONB(), nullable=False),
        sa.Column("handover_summary", sa.Text(), nullable=False),
    )
    op.create_table(
        "messages",
        *record_columns(),
        sa.Column(
            "conversation_id",
            pg.UUID(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "document_ids",
            pg.ARRAY(pg.UUID()),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
        sa.Column(
            "cards", pg.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "sources", pg.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "tool_calls",
            pg.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "escalation_id",
            pg.UUID(),
            sa.ForeignKey("escalations.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "usage", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
    )
    op.create_foreign_key(
        "fk_escalations_message_id",
        "escalations",
        "messages",
        ["message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "knowledge_documents",
        *record_columns(),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("publisher", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("bundesland", sa.Text()),
        sa.Column("content_hash", sa.Text(), nullable=False),
    )
    op.create_table(
        "knowledge_chunks",
        *record_columns(),
        sa.Column(
            "document_id",
            pg.UUID(),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "tsv",
            pg.TSVECTOR(),
            sa.Computed("to_tsvector('german'::regconfig, content)", persisted=True),
            nullable=False,
        ),
        # Changing the embedding dimension requires a new migration.
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_knowledge_chunks_embedding",
        "knowledge_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_knowledge_chunks_tsv",
        "knowledge_chunks",
        ["tsv"],
        postgresql_using="gin",
    )
    op.create_table(
        "audit_log",
        *record_columns(),
        sa.Column("conversation_id", pg.UUID()),
        sa.Column("message_id", pg.UUID()),
        sa.Column("user_id", pg.UUID()),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "detail", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
    )
    op.create_index("ix_audit_log_message_id", "audit_log", ["message_id"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_constraint("fk_escalations_message_id", "escalations", type_="foreignkey")
    for table in (
        "messages",
        "escalations",
        "appointments",
        "form_drafts",
        "documents",
        "case_steps",
        "cases",
        "conversations",
        "providers",
        "offices",
        "leistungen",
        "profiles",
        "users",
    ):
        op.drop_table(table)
    # Extensions can serve other schemas; keep them on downgrade.
