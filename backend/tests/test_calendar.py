"""Owner-only calendar entries: list, manual create, save a proposal, delete."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.calendar import router
from app.deps import SESSION_COOKIE, get_db, sign_session
from app.llm.types import ToolCall
from app.models import Case, Conversation, User
from app.seed import seed
from app.tools import ToolContext, registry

VIENNA = ZoneInfo("Europe/Vienna")


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
    app.include_router(router, prefix="/api")

    async def override_db():
        yield ctx.db

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.cookies.set(SESSION_COOKIE, sign_session(ctx.user.id))
        yield client


async def test_seed_adds_upcoming_entries_sorted_by_start(api):
    response = await api.get("/api/calendar-entries")
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 4
    starts = [datetime.fromisoformat(entry["start"]) for entry in entries]
    assert starts == sorted(starts)
    assert starts[0] > datetime.now(VIENNA)
    assert {entry["kind"] for entry in entries} == {"appointment", "deadline", "other"}


async def test_manual_entry_is_owner_only(api, ctx):
    start = datetime.now(VIENNA).replace(microsecond=0) + timedelta(days=1)
    response = await api.post(
        "/api/calendar-entries",
        json={
            "kind": "deadline",
            "title": "Befund abholen",
            "start": start.isoformat(),
            "conversation_id": str(ctx.conversation.id),
        },
    )
    assert response.status_code == 201
    created = response.json()
    assert created["title"] == "Befund abholen"
    assert created["conversation_id"] == str(ctx.conversation.id)

    other = await ctx.db.scalar(select(User).where(User.persona_id == "stefan"))
    api.cookies.set(SESSION_COOKIE, sign_session(other.id))
    listed = (await api.get("/api/calendar-entries")).json()
    assert created["id"] not in {entry["id"] for entry in listed}
    assert (
        await api.delete(f"/api/calendar-entries/{created['id']}")
    ).status_code == 404
    foreign = await api.post(
        "/api/calendar-entries",
        json={
            "title": "x",
            "start": start.isoformat(),
            "conversation_id": str(ctx.conversation.id),
        },
    )
    assert foreign.status_code == 404

    api.cookies.set(SESSION_COOKIE, sign_session(ctx.user.id))
    assert (
        await api.delete(f"/api/calendar-entries/{created['id']}")
    ).status_code == 204
    listed = (await api.get("/api/calendar-entries")).json()
    assert created["id"] not in {entry["id"] for entry in listed}


async def test_invalid_entries_are_rejected(api):
    assert (
        await api.post("/api/calendar-entries", json={"title": "Ohne Datum"})
    ).status_code == 422
    assert (
        await api.post(
            "/api/calendar-entries",
            json={
                "title": "Ohne Zeitzone",
                "start": "2099-01-01T10:00:00",
            },
        )
    ).status_code == 422
    assert (
        await api.post(
            "/api/calendar-entries",
            json={
                "title": "Ende vor Beginn",
                "start": "2099-01-01T10:00:00+01:00",
                "end": "2099-01-01T09:00:00+01:00",
            },
        )
    ).status_code == 422


async def test_saving_a_proposal_is_idempotent(api, ctx):
    result = await registry.execute(
        ToolCall(
            id="cal",
            name="propose_appointment",
            arguments={
                "provider_id": "demo-care-counselling-1030",
                "time_preference": "any",
            },
        ),
        ctx,
    )
    appointment = result.card.appointment
    first = await api.post(
        "/api/calendar-entries", json={"appointment_id": str(appointment.id)}
    )
    second = await api.post(
        "/api/calendar-entries", json={"appointment_id": str(appointment.id)}
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    entry = first.json()
    assert entry["kind"] == "appointment"
    assert entry["conversation_id"] == str(ctx.conversation.id)
    assert datetime.fromisoformat(entry["start"]) == appointment.start
    assert appointment.provider.name in entry["title"]
