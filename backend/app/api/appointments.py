"""Owner-only calendar downloads for synthetic appointment proposals."""

from datetime import UTC
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import api_error, current_user, get_db
from app.models import Appointment, Provider, User

router = APIRouter(tags=["appointments"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]
VIENNA = ZoneInfo("Europe/Vienna")


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def _fold(line: str) -> str:
    """Fold at 75 UTF-8 octets without splitting a character (RFC 5545 §3.1)."""
    parts = []
    part = ""
    length = 0
    for character in line:
        size = len(character.encode("utf-8"))
        if length + size > 75:
            parts.append(part)
            part, length = " ", 1
        part += character
        length += size
    parts.append(part)
    return "\r\n".join(parts)


def calendar_content(appointment: Appointment, provider: Provider) -> bytes:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SV KI-Lotse//Demo-Termine//DE",
        "CALSCALE:GREGORIAN",
        "BEGIN:VTIMEZONE",
        "TZID:Europe/Vienna",
        "BEGIN:DAYLIGHT",
        "DTSTART:19960331T020000",
        "TZOFFSETFROM:+0100",
        "TZOFFSETTO:+0200",
        "TZNAME:CEST",
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
        "END:DAYLIGHT",
        "BEGIN:STANDARD",
        "DTSTART:19961027T030000",
        "TZOFFSETFROM:+0200",
        "TZOFFSETTO:+0100",
        "TZNAME:CET",
        "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
        "END:STANDARD",
        "END:VTIMEZONE",
        "BEGIN:VEVENT",
        f"UID:{appointment.id}@sv-ki-lotse",
        f"DTSTAMP:{appointment.created_at.astimezone(UTC):%Y%m%dT%H%M%SZ}",
        f"DTSTART;TZID=Europe/Vienna:{appointment.start.astimezone(VIENNA):%Y%m%dT%H%M%S}",
        f"DTEND;TZID=Europe/Vienna:{appointment.end.astimezone(VIENNA):%Y%m%dT%H%M%S}",
        f"SUMMARY:{_escape(provider.specialty or 'Beratungstermin')}"
        f" – {_escape(provider.name)}",
        f"LOCATION:{_escape(provider.address)}",
        "DESCRIPTION:Demo-Termin – keine echte Buchung",
        "STATUS:TENTATIVE",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return ("\r\n".join(_fold(line) for line in lines) + "\r\n").encode("utf-8")


@router.get(
    "/appointments/{id}/ics",
    response_class=Response,
    responses={200: {"content": {"text/calendar": {}}}},
)
async def download_appointment(id: UUID, db: DbSession, user: CurrentUser) -> Response:
    row = await db.scalar(
        select(Appointment).where(Appointment.id == id, Appointment.user_id == user.id)
    )
    if row is None:
        raise api_error(404, "not_found", "Dieser Demo-Termin wurde nicht gefunden.")
    provider = await db.get(Provider, row.provider_id)
    if provider is None:
        raise api_error(404, "not_found", "Dieser Demo-Anbieter wurde nicht gefunden.")
    return Response(
        content=calendar_content(row, provider),
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="termin-{row.id}.ics"',
            "Cache-Control": "private, no-store",
        },
    )
