"""Human-reviewed form drafts."""

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class FormDraft(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "form_drafts"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    form_id: Mapped[str] = mapped_column(Text)
    values: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    missing: Mapped[list[Any]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    pdf_path: Mapped[str | None] = mapped_column(Text)
