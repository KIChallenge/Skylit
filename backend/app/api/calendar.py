"""Owner-only calendar: doctor visits, deadlines and other dates of one user."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import api_error, current_user, get_db
from app.models import Appointment, CalendarEntry, Conversation, Provider, User
from app.schemas import calendar as schemas

router = APIRouter(tags=["calendar"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]


@router.get("/calendar-entries", response_model=list[schemas.CalendarEntry])
async def list_entries(db: DbSession, user: CurrentUser) -> list[CalendarEntry]:
    rows = await db.scalars(
        select(CalendarEntry)
        .where(CalendarEntry.user_id == user.id)
        .order_by(CalendarEntry.start, CalendarEntry.created_at)
    )
    return list(rows)


async def _from_appointment(
    appointment_id: UUID, db: AsyncSession, user: User
) -> CalendarEntry:
    appointment = await db.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id, Appointment.user_id == user.id
        )
    )
    if appointment is None:
        raise api_error(404, "not_found", "Dieser Demo-Termin wurde nicht gefunden.")
    existing = await db.scalar(
        select(CalendarEntry).where(CalendarEntry.appointment_id == appointment.id)
    )
    if existing is not None:
        return existing
    provider = await db.get(Provider, appointment.provider_id)
    if provider is None:
        raise api_error(404, "not_found", "Dieser Demo-Anbieter wurde nicht gefunden.")
    entry = CalendarEntry(
        user_id=user.id,
        conversation_id=appointment.conversation_id,
        appointment_id=appointment.id,
        kind="appointment",
        title=f"{provider.specialty or 'Termin'} – {provider.name}",
        start=appointment.start,
        end=appointment.end,
        location=provider.address,
        note="Demo-Termin – keine Buchung. Bitte telefonisch vereinbaren.",
    )
    db.add(entry)
    return entry


@router.post("/calendar-entries", response_model=schemas.CalendarEntry, status_code=201)
async def create_entry(
    body: schemas.CalendarEntryCreate, db: DbSession, user: CurrentUser
) -> CalendarEntry:
    if body.appointment_id is not None:
        entry = await _from_appointment(body.appointment_id, db, user)
    else:
        if body.conversation_id is not None:
            owned = await db.scalar(
                select(Conversation.id).where(
                    Conversation.id == body.conversation_id,
                    Conversation.user_id == user.id,
                )
            )
            if owned is None:
                raise api_error(
                    404, "not_found", "Dieses Gespräch wurde nicht gefunden."
                )
        entry = CalendarEntry(
            user_id=user.id,
            conversation_id=body.conversation_id,
            kind=body.kind,
            title=body.title,
            start=body.start,
            end=body.end,
            all_day=body.all_day,
            location=body.location,
            note=body.note,
        )
        db.add(entry)
    try:
        await db.commit()
    except IntegrityError:
        # A parallel request saved the same proposal first.
        await db.rollback()
        if body.appointment_id is None:
            raise
        existing = await db.scalar(
            select(CalendarEntry).where(
                CalendarEntry.appointment_id == body.appointment_id,
                CalendarEntry.user_id == user.id,
            )
        )
        if existing is None:
            raise
        return existing
    await db.refresh(entry)
    return entry


@router.delete("/calendar-entries/{id}", status_code=204, response_class=Response)
async def delete_entry(id: UUID, db: DbSession, user: CurrentUser) -> Response:
    entry = await db.scalar(
        select(CalendarEntry).where(
            CalendarEntry.id == id, CalendarEntry.user_id == user.id
        )
    )
    if entry is None:
        raise api_error(
            404, "not_found", "Dieser Kalendereintrag wurde nicht gefunden."
        )
    await db.delete(entry)
    await db.commit()
    return Response(status_code=204)
