"""Persona login and profile models from docs/contracts.md section 1."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Language = Literal["de", "de-simple", "en"]
Depth = Literal["short", "detailed"]
Insurer = Literal["OEGK", "BVAEB", "SVS"]


class Persona(BaseModel):
    id: str
    display_name: str
    tagline: str
    avatar_emoji: str


class CoInsuredPerson(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    relation: str


class Profile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    language: Language
    depth: Depth
    bundesland: str | None
    postal_code: str | None
    insurer: Insurer | None
    date_of_birth: date | None
    # From the simulated SV data query (D-041). The user cannot change these.
    first_name: str | None = None
    last_name: str | None = None
    svnr: str | None = None
    insurance_status: str | None = None
    street: str | None = None
    city: str | None = None
    co_insured: list[CoInsuredPerson] | None = None
    sv_retrieved_at: datetime | None = None


class Me(BaseModel):
    user_id: UUID
    persona_id: str
    display_name: str
    profile: Profile


class ProfileUpdate(BaseModel):
    """Partial profile: only the fields the client sends change."""

    model_config = ConfigDict(extra="forbid")

    language: Language | None = None
    depth: Depth | None = None
    bundesland: str | None = Field(default=None, min_length=1, max_length=40)
    postal_code: str | None = Field(default=None, pattern=r"^\d{4}$")
    insurer: Insurer | None = None
    date_of_birth: date | None = None

    @field_validator("language", "depth")
    @classmethod
    def reject_null(cls, value: str | None) -> str:
        # The columns are NOT NULL; omit the field to keep the stored value.
        if value is None:
            raise ValueError("must not be null")
        return value


class LoginRequest(BaseModel):
    persona_id: str = Field(min_length=1, max_length=64)
