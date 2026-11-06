"""Uploaded documents and their extraction state."""

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Document(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    filename: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="uploaded")
    kind: Mapped[str | None] = mapped_column(Text)
    extracted: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
