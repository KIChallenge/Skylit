"""Calendar entry DTOs for the „Kalender“ panel."""

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.cards import Schema

CalendarKind = Literal["appointment", "deadline", "other"]


class CalendarEntry(Schema):
    id: UUID
    kind: CalendarKind
    title: str
    start: datetime
    end: datetime | None = None
    all_day: bool = False
    location: str | None = None
    note: str | None = None
    conversation_id: UUID | None = None
    appointment_id: UUID | None = None


class CalendarEntryCreate(BaseModel):
    """Either `appointment_id` alone, or a manual entry with `title` and `start`."""

    model_config = ConfigDict(extra="forbid")

    appointment_id: UUID | None = None
    conversation_id: UUID | None = None
    kind: CalendarKind = "other"
    title: str | None = Field(default=None, min_length=1, max_length=200)
    start: datetime | None = None
    end: datetime | None = None
    all_day: bool = False
    location: str | None = Field(default=None, max_length=300)
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _complete(self) -> Self:
        if self.appointment_id is None and (not self.title or self.start is None):
            raise ValueError("title and start are required without appointment_id")
        for value in (self.start, self.end):
            if value is not None and value.tzinfo is None:
                raise ValueError("start and end need a time zone offset")
        if self.start and self.end and self.end < self.start:
            raise ValueError("end must not be before start")
        return self
