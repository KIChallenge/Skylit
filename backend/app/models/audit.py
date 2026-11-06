"""Audit events retain identifiers after application records disappear."""

from typing import Any
from uuid import UUID

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class AuditLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "audit_log"

    conversation_id: Mapped[UUID | None]
    message_id: Mapped[UUID | None] = mapped_column(index=True)
    user_id: Mapped[UUID | None]
    event_type: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
