"""Simulated SV data query over a synthetic register (D-041)."""

import json
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.sv_data import SvRecord, is_valid_svnr

DEFAULT_REGISTER = Path(__file__).resolve().parents[2] / "seed" / "sv_register.json"


class MockSvDataService:
    """Answers like a real SV data query, but from seed/sv_register.json."""

    def __init__(self, register: Path = DEFAULT_REGISTER) -> None:
        self.register = register

    async def lookup(self, svnr: str) -> SvRecord | None:
        if not is_valid_svnr(svnr):
            raise ValueError("Die SV-Nummer hat kein gültiges Format.")
        with self.register.open(encoding="utf-8") as source:
            entry = json.load(source).get(svnr)
        if entry is None:
            return None
        return SvRecord.model_validate(
            {**entry, "svnr": svnr, "retrieved_at": datetime.now(UTC)}
        )
