"""Escalation targets and administrative handover summaries."""

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Escalation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "escalations"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "messages.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_escalations_message_id",
        )
    )
    reason_code: Mapped[str] = mapped_column(Text)
    target: Mapped[dict[str, Any]] = mapped_column(JSONB)
    handover_summary: Mapped[str] = mapped_column(Text)
