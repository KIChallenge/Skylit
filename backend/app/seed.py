"""Load synthetic demo records within the caller's database transaction."""

import argparse
import asyncio
import json
import logging
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal, engine
from app.models import CalendarEntry, Leistung, Office, Profile, Provider, User
from app.models.providers import VIENNA_OGD_SOURCE
from app.providers.mock_sv_data import MockSvDataService

logger = logging.getLogger(__name__)
SEED_DIR = Path(__file__).resolve().parents[1] / "seed"
VIENNA = ZoneInfo("Europe/Vienna")


def load_records(path: Path, *, optional: bool = False) -> list[dict[str, Any]]:
    if optional and not path.exists():
        logger.info("Seed-Datei fehlt, übersprungen: %s", path.name)
        return []
    with path.open(encoding="utf-8") as source:
        return json.load(source)


async def seed(
    session: AsyncSession, *, reset: bool = False, seed_dir: Path = SEED_DIR
) -> bool:
    """Seed once, returning whether records changed. The caller commits."""
    # Serialize concurrent startup seeds before checking the sentinel table.
    await session.execute(text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))
    if not reset and await session.scalar(select(User.id).limit(1)) is not None:
        logger.info("Personas vorhanden, Seed übersprungen")
        # Open data is not demo state: refresh it on every start.
        await load_vienna_doctors(session, seed_dir)
        return False

    if reset:
        # Retain ingested knowledge; reset demo users and dependent records.
        await session.execute(
            text(
                "TRUNCATE TABLE users, providers, leistungen, offices, audit_log "
                "RESTART IDENTITY CASCADE"
            )
        )
        session.expunge_all()

    sv_data = MockSvDataService(seed_dir / "sv_register.json")
    for persona in load_records(seed_dir / "personas.json"):
        user = User(
            **{
                key: persona[key]
                for key in ("persona_id", "display_name", "tagline", "avatar_emoji")
            }
        )
        # The simulated SV data query fills the SV fields (D-041).
        record = await sv_data.lookup(persona["svnr"])
        if record is None:
            logger.error("SV-Datenabfrage ohne Treffer: %s", persona["persona_id"])
            raise ValueError(f"Keine SV-Daten für Persona {persona['persona_id']}")
        user.profile = Profile(
            **persona["profile"],
            bundesland=record.address.bundesland,
            postal_code=record.address.postal_code,
            insurer=record.insurer,
            date_of_birth=record.date_of_birth,
            svnr=record.svnr,
            sv_record=record.model_dump(mode="json"),
            sv_retrieved_at=record.retrieved_at,
            extra=persona.get("extra", {}),
        )
        session.add(user)

    for filename, model, optional in (
        ("providers.json", Provider, False),
        ("leistungen.json", Leistung, True),
        ("offices.json", Office, True),
    ):
        for record in load_records(seed_dir / filename, optional=optional):
            if model is Provider and record.get("demo") is not True:
                raise ValueError("Provider-Seeds müssen demo: true enthalten")
            # The demo marker belongs to the seed format, not the DB contract.
            values = {key: value for key, value in record.items() if key != "demo"}
            await session.execute(
                insert(model)
                .values(**values)
                .on_conflict_do_nothing(index_elements=["id"])
            )

    await load_vienna_doctors(session, seed_dir)
    await session.flush()
    await seed_calendar(session, seed_dir)
    logger.info("Seed abgeschlossen")
    return True


async def load_vienna_doctors(session: AsyncSession, seed_dir: Path) -> None:
    """Upsert the static Stadt Wien doctor list (scripts/fetch_vienna_doctors.py)."""
    records = load_records(seed_dir / "vienna_doctors.json", optional=True)
    if not records:
        return
    batch = 1000
    for start in range(0, len(records), batch):
        rows = [
            {**record, "source": VIENNA_OGD_SOURCE}
            for record in records[start : start + batch]
        ]
        statement = insert(Provider).values(rows)
        columns = {key: statement.excluded[key] for key in rows[0] if key != "id"}
        await session.execute(
            statement.on_conflict_do_update(index_elements=["id"], set_=columns)
        )
    logger.info("Ärzteliste Stadt Wien geladen: %d Einträge", len(records))


async def seed_calendar(session: AsyncSession, seed_dir: Path) -> None:
    """Add demo calendar dates relative to the seed day, so they stay upcoming."""
    records = load_records(seed_dir / "calendar.json", optional=True)
    if not records:
        return
    users = {user.persona_id: user.id for user in await session.scalars(select(User))}
    today = datetime.now(VIENNA).date()
    for record in records:
        user_id = users.get(record["persona_id"])
        if user_id is None:
            continue
        day = today + timedelta(days=record["days_from_seed"])
        all_day = bool(record.get("all_day"))
        # Practices open on weekdays: move timed dates off the weekend.
        while not all_day and day.weekday() >= 5:
            day += timedelta(days=1)
        clock = time(0) if all_day else time.fromisoformat(record["time"])
        start = datetime.combine(day, clock, tzinfo=VIENNA)
        minutes = record.get("minutes")
        session.add(
            CalendarEntry(
                user_id=user_id,
                kind=record["kind"],
                title=record["title"],
                start=start,
                end=start + timedelta(minutes=minutes) if minutes else None,
                all_day=all_day,
                location=record.get("location"),
                note=record.get("note"),
            )
        )
    await session.flush()


async def run(*, reset: bool = False) -> None:
    try:
        async with SessionLocal.begin() as session:
            await seed(session, reset=reset)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetische Demo-Daten laden")
    parser.add_argument("--reset", action="store_true", help="Demo-Daten ersetzen")
    args = parser.parse_args()
    logging.basicConfig(level=settings.log_level)
    asyncio.run(run(reset=args.reset))


if __name__ == "__main__":
    main()
