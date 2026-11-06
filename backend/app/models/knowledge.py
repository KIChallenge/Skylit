"""Knowledge documents and hybrid retrieval chunks."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, Date, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.models.base import Base, TimestampMixin, UUIDMixin


class KnowledgeDocument(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_documents"

    slug: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    bundesland: Mapped[str | None] = mapped_column(Text)
    # The day the team read the official source.
    retrieved: Mapped[date | None] = mapped_column(Date)
    content_hash: Mapped[str] = mapped_column(Text)
    chunks: Mapped[list[KnowledgeChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="KnowledgeChunk.chunk_index",
    )


class KnowledgeChunk(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index(
            "ix_knowledge_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_knowledge_chunks_tsv", "tsv", postgresql_using="gin"),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE")
    )
    chunk_index: Mapped[int]
    heading: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('german'::regconfig, content)", persisted=True)
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))
    content_hash: Mapped[str] = mapped_column(Text)
    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")
