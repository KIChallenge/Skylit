"""Leistung records."""

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Leistung(TimestampMixin, Base):
    __tablename__ = "leistungen"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    short: Mapped[str] = mapped_column(Text)
    conditions: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    office_kind: Mapped[str] = mapped_column(Text)
    form_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    documents_needed: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    source_url: Mapped[str] = mapped_column(Text)
