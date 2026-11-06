"""Answer of the SV data query for one SV-Nummer (D-041)."""

from datetime import date, datetime

from pydantic import BaseModel, field_validator

from app.schemas.auth import Insurer

# Source: Anfragebeantwortung 4690/AB XXIII. GP (BMGFJ, 2008). Digit 4 is the
# check digit; the other nine digits carry these weights.
_WEIGHTS = (3, 7, 9, 0, 5, 8, 4, 2, 1, 6)


def is_valid_svnr(svnr: str) -> bool:
    """Check the format "LLLP DDMMYY" and the mod-11 check digit."""
    if len(svnr) != 10 or not svnr.isascii() or not svnr.isdigit():
        return False
    remainder = sum(int(digit) * w for digit, w in zip(svnr, _WEIGHTS)) % 11
    # Remainder 10 never gives a valid number: the register skips that serial.
    return remainder != 10 and remainder == int(svnr[3])


class SvAddress(BaseModel):
    street: str
    postal_code: str
    city: str
    bundesland: str


class CoInsured(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    relation: str


class SvRecord(BaseModel):
    svnr: str
    first_name: str
    last_name: str
    date_of_birth: date
    address: SvAddress
    insurer: Insurer
    insurance_status: str
    co_insured: list[CoInsured] = []
    retrieved_at: datetime

    @field_validator("svnr")
    @classmethod
    def check_svnr(cls, value: str) -> str:
        if not is_valid_svnr(value):
            raise ValueError("ungültige SV-Nummer")
        return value
