"""Provider records: invented demo providers and Stadt Wien open data."""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

DEMO_SOURCE = "demo"
VIENNA_OGD_SOURCE = "wien_ogd"


class Provider(TimestampMixin, Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text, index=True)
    specialty: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str] = mapped_column(Text)
    postal_code: Mapped[str] = mapped_column(Text)
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    phone: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, server_default=DEMO_SOURCE)

    @property
    def demo(self) -> bool:
        return self.source == DEMO_SOURCE
