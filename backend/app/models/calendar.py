"""Personal calendar entries: doctor visits, deadlines and other dates."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text, false, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class CalendarEntry(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "calendar_entries"
    # One calendar entry per saved appointment proposal.
    __table_args__ = (
        Index(
            "uq_calendar_entries_appointment",
            "appointment_id",
            unique=True,
            postgresql_where=text("appointment_id IS NOT NULL"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    appointment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("appointments.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    all_day: Mapped[bool] = mapped_column(Boolean, server_default=false())
    location: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
