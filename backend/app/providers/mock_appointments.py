"""Deterministic demo slots; proposals never book a real appointment."""

from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Appointment
from app.providers.base import TimePreference

VIENNA = ZoneInfo("Europe/Vienna")
SLOT_DURATION = timedelta(minutes=45)


def available_slots(
    *,
    today: date,
    time_preference: TimePreference = "any",
    earliest_date: date | None = None,
) -> list[tuple[datetime, datetime]]:
    """Return slots over five weekdays, starting tomorrow or earliest_date."""
    day = max(today + timedelta(days=1), earliest_date or today)
    slots = []
    working_days = 0
    while working_days < 5:
        if day.weekday() < 5:
            working_days += 1
            start = datetime.combine(day, time(9), tzinfo=VIENNA)
            closing = datetime.combine(day, time(15), tzinfo=VIENNA)
            while start + SLOT_DURATION <= closing:
                morning = start.hour < 12
                if (
                    time_preference == "any"
                    or (time_preference == "morning" and morning)
                    or (time_preference == "afternoon" and not morning)
                ):
                    slots.append((start, start + SLOT_DURATION))
                start += SLOT_DURATION
        day += timedelta(days=1)
    return slots


class MockAppointmentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def propose(
        self,
        provider_id: str,
        *,
        user_id: UUID,
        conversation_id: UUID,
        time_preference: TimePreference = "any",
        earliest_date: date | None = None,
    ) -> Appointment:
        start, end = available_slots(
            today=datetime.now(VIENNA).date(),
            time_preference=time_preference,
            earliest_date=earliest_date,
        )[0]
        appointment = Appointment(
            provider_id=provider_id,
            user_id=user_id,
            conversation_id=conversation_id,
            start=start,
            end=end,
            status="proposed",
        )
        self.db.add(appointment)
        await self.db.flush()
        return appointment
