"""Shared PostgreSQL record defaults."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UUIDMixin:
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
