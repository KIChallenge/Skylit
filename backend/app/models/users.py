"""Demo users and their persistent profiles."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    persona_id: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    tagline: Mapped[str] = mapped_column(Text)
    avatar_emoji: Mapped[str] = mapped_column(Text)
    profile: Mapped[Profile] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Profile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "profiles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    language: Mapped[str] = mapped_column(Text, server_default="de")
    depth: Mapped[str] = mapped_column(Text, server_default="short")
    bundesland: Mapped[str | None] = mapped_column(Text)
    postal_code: Mapped[str | None] = mapped_column(Text)
    insurer: Mapped[str | None] = mapped_column(Text)
    date_of_birth: Mapped[date | None]
    extra: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    # Answer of the simulated SV data query (D-041). Read-only for the user.
    svnr: Mapped[str | None] = mapped_column(Text)
    sv_record: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    sv_retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates="profile")
