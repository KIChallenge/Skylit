"""Conversation history and messages."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.cases import Case


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text, server_default="Neuer Fall")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at",
    )
    case: Mapped[Case | None] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, server_default="")
    document_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)), server_default=text("'{}'::uuid[]")
    )
    cards: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    escalation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("escalations.id", ondelete="SET NULL")
    )
    usage: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    conversation: Mapped[Conversation] = relationship(back_populates="messages")
