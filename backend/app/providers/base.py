"""Replaceable system interfaces (D-010)."""

from datetime import date
from typing import Literal, Protocol
from uuid import UUID

from app.models import Appointment
from app.schemas.cards import Provider, ProviderKind
from app.schemas.sv_data import SvRecord

TimePreference = Literal["morning", "afternoon", "any"]


class ProviderDirectory(Protocol):
    async def find(
        self,
        kind: ProviderKind,
        postal_code: str,
        *,
        specialty: str | None = None,
        limit: int = 3,
        origin: tuple[float, float] | None = None,
    ) -> list[Provider]: ...

    async def get(self, provider_id: str) -> Provider | None: ...


class AppointmentService(Protocol):
    async def propose(
        self,
        provider_id: str,
        *,
        user_id: UUID,
        conversation_id: UUID,
        time_preference: TimePreference = "any",
        earliest_date: date | None = None,
    ) -> Appointment: ...


class SvDataService(Protocol):
    """Returns the SV record for an SV-Nummer, or None for an unknown number."""

    async def lookup(self, svnr: str) -> SvRecord | None: ...
