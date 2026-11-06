"""Provider discovery, demo proposals and owner-only RFC 5545 downloads."""

import re
from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.appointments import calendar_content, router
from app.deps import SESSION_COOKIE, get_db, sign_session
from app.llm.types import ToolCall
from app.models import Appointment, Case, Conversation, Provider, User
from app.providers.mock_appointments import available_slots
from app.seed import seed
from app.tools import ToolContext, registry

VIENNA = ZoneInfo("Europe/Vienna")
PROVIDER_ID = "demo-care-counselling-1030"


@pytest_asyncio.fixture
async def ctx(db_session):
    await seed(db_session)
    user = await db_session.scalar(select(User).where(User.persona_id == "maria"))
    conversation = Conversation(user_id=user.id, title="Pflegeberatung organisieren")
    db_session.add(conversation)
    await db_session.flush()
    case = Case(conversation_id=conversation.id, title="Pflegeberatung", steps=[])
    db_session.add(case)
    await db_session.flush()
    return ToolContext(
        db=db_session,
        user=user,
        conversation=conversation,
        case=case,
        audit=AsyncMock(),
    )


@pytest_asyncio.fixture
async def api(ctx):
    app = FastAPI()
    # The manager registers this router in main.py after integrating the task.
    app.include_router(router, prefix="/api")

    async def override_db():
        yield ctx.db

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def execute(ctx, name, **arguments):
    return await registry.execute(
        ToolCall(id="appointment-test", name=name, arguments=arguments), ctx
    )


async def test_find_providers_returns_demo_care_counselling_by_distance(ctx):
    result = await execute(
        ctx, "find_providers", kind="care_counselling", postal_code="1030"
    )
    assert result.ok
    assert result.card.type == "provider_list"
    assert result.card.demo is True
    providers = result.card.providers
    assert len(providers) == 3
    assert providers[0].id == PROVIDER_ID
    assert providers[0].distance_km == 0
    assert all(p.kind == "care_counselling" and p.demo is True for p in providers)
    distances = [p.distance_km for p in providers]
    assert distances == sorted(distances)
    assert distances[1] == pytest.approx(3.09, abs=0.1)
    assert result.result == {
        "providers": [p.model_dump(mode="json") for p in providers],
        "demo": True,
        "distance_from": "postleitzahl",
    }
    assert result.card.origin == "postal_code"
    assert not result.case_changed


async def test_provider_filters_limit_and_unknown_postal_code(ctx):
    result = await execute(
        ctx,
        "find_providers",
        kind="therapy",
        postal_code="1030",
        specialty="Ergotherapie",
        limit=1,
    )
    assert result.ok
    assert [p.id for p in result.card.providers] == ["demo-therapy-1100"]
    result = await execute(
        ctx, "find_providers", kind="care_counselling", postal_code="8010"
    )
    assert result.ok
    assert result.card.providers == []


async def test_missing_coordinates_sort_last(ctx):
    row = await ctx.db.get(Provider, PROVIDER_ID)
    row.lat = None
    row.lon = None
    await ctx.db.flush()
    result = await execute(
        ctx, "find_providers", kind="care_counselling", postal_code="1030"
    )
    assert result.ok
    assert result.card.providers[-1].id == PROVIDER_ID
    assert result.card.providers[-1].distance_km is None


@pytest.mark.parametrize("preference", ["morning", "afternoon", "any"])
async def test_propose_appointment_persists_proposed_slot(ctx, preference):
    today = datetime.now(VIENNA).date()
    result = await execute(
        ctx,
        "propose_appointment",
        provider_id=PROVIDER_ID,
        time_preference=preference,
        earliest_date="2099-01-03",
    )
    assert result.ok
    assert result.card.type == "appointment"
    assert result.card.demo is True
    appointment = result.card.appointment
    assert appointment.demo is True
    assert appointment.provider.demo is True
    assert appointment.provider.id == PROVIDER_ID
    start, end = (
        appointment.start.astimezone(VIENNA),
        appointment.end.astimezone(VIENNA),
    )
    assert start.date() >= max(today + timedelta(days=1), date(2099, 1, 3))
    assert start.weekday() < 5
    assert time(9) <= start.time() < end.time() <= time(15)
    assert end - start == timedelta(minutes=45)
    if preference == "morning":
        assert start.hour < 12
    elif preference == "afternoon":
        assert start.hour >= 12
    assert appointment.ics_url == f"/api/appointments/{appointment.id}/ics"
    assert result.result["appointment"] == appointment.model_dump(mode="json")
    assert result.result["demo"] is True
    row = await ctx.db.get(Appointment, appointment.id)
    assert row.status == "proposed"
    assert row.user_id == ctx.user.id
    assert row.conversation_id == ctx.conversation.id
    assert row.start == appointment.start
    assert row.end == appointment.end


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("find_providers", {"kind": "invalid", "postal_code": "1030"}),
        ("find_providers", {"kind": "gp", "postal_code": "invalid"}),
        ("find_providers", {"kind": "gp", "postal_code": "1030", "limit": 0}),
        ("propose_appointment", {"provider_id": "unknown"}),
        (
            "propose_appointment",
            {"provider_id": PROVIDER_ID, "time_preference": "evening"},
        ),
        (
            "propose_appointment",
            {"provider_id": PROVIDER_ID, "earliest_date": "invalid"},
        ),
    ],
)
async def test_invalid_input_returns_tool_error_without_appointments(
    ctx, name, arguments
):
    result = await execute(ctx, name, **arguments)
    assert not result.ok
    assert result.error
    assert result.card is None
    assert await ctx.db.scalar(select(func.count()).select_from(Appointment)) == 0


def test_slots_cover_next_five_weekdays_and_skip_weekend():
    slots = available_slots(today=date(2026, 11, 6))  # Friday
    assert len(slots) == 40
    days = sorted({start.date() for start, _ in slots})
    assert days == [date(2026, 11, day) for day in range(9, 14)]
    assert slots[0][0].time() == time(9)
    assert slots[-1][1].time() == time(15)
    assert all(end - start == timedelta(minutes=45) for start, end in slots)
    assert slots == available_slots(today=date(2026, 11, 6))


@pytest.mark.parametrize("preference", ["morning", "afternoon"])
def test_slot_preference_and_earliest_date(preference):
    slots = available_slots(
        today=date(2026, 11, 5),
        earliest_date=date(2026, 11, 14),  # Saturday
        time_preference=preference,
    )
    assert slots[0][0].date() == date(2026, 11, 16)
    assert len({start.date() for start, _ in slots}) == 5
    assert all((start.hour < 12) == (preference == "morning") for start, _ in slots)


def _parse_calendar(content):
    """Parse content lines and component nesting without adding a dependency."""
    assert content.startswith(b"BEGIN:VCALENDAR\r\n")
    assert content.endswith(b"END:VCALENDAR\r\n")
    assert b"\n" not in content.replace(b"\r\n", b"")
    assert b"\r" not in content.replace(b"\r\n", b"")
    assert all(len(line) <= 75 for line in content.split(b"\r\n"))
    text = re.sub(r"\r\n[ \t]", "", content.decode("utf-8"))
    components = []
    event = {}
    for line in text.split("\r\n"):
        if not line:
            continue
        name, value = line.split(":", 1)
        if name == "BEGIN":
            components.append(value)
        elif name == "END":
            assert components.pop() == value
        elif components[-1] == "VEVENT":
            assert name not in event
            event[name] = value
    assert not components
    return event


async def test_calendar_download_parses_and_rejects_another_user(ctx, api):
    result = await execute(
        ctx, "propose_appointment", provider_id=PROVIDER_ID, time_preference="morning"
    )
    assert result.ok
    appointment = result.card.appointment
    assert (await api.get(appointment.ics_url)).status_code == 401
    api.cookies.set(SESSION_COOKIE, sign_session(ctx.user.id))
    response = await api.get(appointment.ics_url)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert response.headers["content-disposition"].endswith(f'{appointment.id}.ics"')
    event = _parse_calendar(response.content)
    assert event["UID"] == f"{appointment.id}@sv-ki-lotse"
    assert datetime.strptime(event["DTSTAMP"], "%Y%m%dT%H%M%SZ")
    for key, expected in (("DTSTART", appointment.start), ("DTEND", appointment.end)):
        value = event[f"{key};TZID=Europe/Vienna"]
        parsed = datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=VIENNA)
        assert parsed == expected
    assert "Pflegeberatung" in event["SUMMARY"]
    assert event["LOCATION"] == r"Demogasse 2\, 1030 Wien"
    assert event["DESCRIPTION"] == "Demo-Termin – keine echte Buchung"
    assert event["STATUS"] == "TENTATIVE"
    assert (await api.get(appointment.ics_url)).content == response.content
    assert (await api.get(f"/api/appointments/{uuid4()}/ics")).status_code == 404
    for persona_id in ("stefan", "elif"):
        user = await ctx.db.scalar(select(User).where(User.persona_id == persona_id))
        api.cookies.set(SESSION_COOKIE, sign_session(user.id))
        assert (await api.get(appointment.ics_url)).status_code == 404


@pytest.mark.parametrize("day", [date(2026, 3, 30), date(2026, 10, 26)])
def test_calendar_escapes_and_folds_utf8_without_changing_local_times(day):
    start = datetime.combine(day, time(9), tzinfo=VIENNA)
    appointment = Appointment(
        id=uuid4(),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        start=start,
        end=start + timedelta(minutes=45),
    )
    provider = Provider(
        name="Ö" * 80,
        specialty="Pflegeberatung",
        address="Demogasse 2, Wien; Hof\\Stiege\r\nStock 1",
    )
    content = calendar_content(appointment, provider)
    event = _parse_calendar(content)
    assert event["SUMMARY"] == "Pflegeberatung – " + "Ö" * 80
    assert event["LOCATION"] == r"Demogasse 2\, Wien\; Hof\\Stiege\nStock 1"
    value = event["DTSTART;TZID=Europe/Vienna"]
    parsed = datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=VIENNA)
    assert parsed.astimezone(UTC) == start.astimezone(UTC)
    assert b"BEGIN:VTIMEZONE\r\nTZID:Europe/Vienna\r\n" in content


async def test_doctors_come_from_vienna_open_data(ctx):
    result = await execute(ctx, "find_providers", kind="gp", postal_code="1030")
    assert result.ok
    providers = result.card.providers
    # The demo GP sits at the district centre; real practices follow by distance.
    assert any(not p.demo and p.id.startswith("wien-arzt-") for p in providers)
    assert result.card.demo is True
    real = await execute(
        ctx,
        "find_providers",
        kind="specialist",
        postal_code="1030",
        specialty="kardiologie",
    )
    assert real.ok
    assert real.card.providers
    assert all(not p.demo for p in real.card.providers)
    assert all("Kardiologie" in p.specialty for p in real.card.providers)
    assert real.card.demo is False
    assert real.result["demo"] is False


async def test_shared_location_ranks_from_there(ctx):
    by_postal_code = await execute(
        ctx, "find_providers", kind="specialist", postal_code="1030", limit=1
    )
    # Floridsdorf, far from the 1030 centre.
    ctx.location = (48.2775, 16.4100)
    by_location = await execute(
        ctx, "find_providers", kind="specialist", postal_code="1030", limit=1
    )
    assert by_location.card.origin == "location"
    assert by_location.result["distance_from"] == "standort"
    assert by_location.card.providers[0].postal_code == "1210"
    assert by_location.card.providers[0].id != by_postal_code.card.providers[0].id
    # Distances from the location would reveal it: the LLM result omits them.
    assert by_location.card.providers[0].distance_km is not None
    assert all("distance_km" not in p for p in by_location.result["providers"])
    assert "distance_km" in by_postal_code.result["providers"][0]
    # A location outside Vienna falls back to the postal code.
    ctx.location = (47.07, 15.44)
    fallback = await execute(
        ctx, "find_providers", kind="specialist", postal_code="1030", limit=1
    )
    assert fallback.card.origin == "postal_code"


async def test_no_demo_appointments_at_real_practices(ctx):
    found = await execute(
        ctx, "find_providers", kind="specialist", postal_code="1030", limit=1
    )
    result = await execute(
        ctx, "propose_appointment", provider_id=found.card.providers[0].id
    )
    assert not result.ok
    assert await ctx.db.scalar(select(func.count()).select_from(Appointment)) == 0
