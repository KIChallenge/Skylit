"""Office records."""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Office(TimestampMixin, Base):
    __tablename__ = "offices"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    organisation: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    bundesland: Mapped[str] = mapped_column(Text)
    address: Mapped[str] = mapped_column(Text)
    postal_code: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(Text)
    phone: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    hours: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    source_url: Mapped[str | None] = mapped_column(Text)
