"""Synthetic provider appointments."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Appointment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "appointments"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"))
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default="booked")
