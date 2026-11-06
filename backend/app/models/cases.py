"""Persistent cases and ordered administrative steps."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.conversations import Conversation


class Case(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "cases"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), unique=True
    )
    title: Mapped[str] = mapped_column(Text, server_default="Mein Fall")
    subject: Mapped[str] = mapped_column(Text, server_default="self")
    summary: Mapped[str] = mapped_column(Text, server_default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    conversation: Mapped[Conversation] = relationship(back_populates="case")
    steps: Mapped[list[CaseStep]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CaseStep.position",
    )


class CaseStep(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "case_steps"

    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[str] = mapped_column(Text, server_default="open")
    category: Mapped[str] = mapped_column(Text)
    leistung_id: Mapped[str | None] = mapped_column(
        ForeignKey("leistungen.id", ondelete="SET NULL")
    )
    due_hint: Mapped[str | None] = mapped_column(Text)
    related_card: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    position: Mapped[int] = mapped_column(server_default="0")
    case: Mapped[Case] = relationship(back_populates="steps")
