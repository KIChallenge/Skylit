from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.audit import router
from app.audit.log import audit
from app.deps import current_user, get_db
from app.models import Conversation, Escalation, Message, User


@pytest_asyncio.fixture
async def setup_api(db_session):
    owner = User(
        id=uuid4(),
        persona_id="audit-owner",
        display_name="Owner",
        tagline="",
        avatar_emoji="",
    )
    other = User(
        id=uuid4(),
        persona_id="audit-other",
        display_name="Other",
        tagline="",
        avatar_emoji="",
    )
    conversation = Conversation(id=uuid4(), user_id=owner.id)
    message = Message(
        id=uuid4(),
        conversation_id=conversation.id,
        role="assistant",
        content="Antwort",
        sources=[],
    )
    # Insert parents first: the unit of work does not order these rows by FK.
    for row in (owner, other, conversation, message):
        db_session.add(row)
        await db_session.flush()
    app = FastAPI()
    app.include_router(router, prefix="/api")

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[current_user] = lambda: owner
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, app, owner, other, conversation, message


@pytest.mark.asyncio
async def test_audit_and_transparency(setup_api, db_session):
    client, app, owner, other, conversation, message = setup_api
    source = {"title": "Pflege", "publisher": "PVA", "url": "https://example.org"}
    message.sources = [source, {**source, "url": "https://example.org/zwei"}]
    for kind, summary, detail in [
        ("llm_call", "Modellaufruf", {"model": "test-model", "prompt_tokens": 10}),
        (
            "retrieval",
            "Suche",
            {"chunk_count": 1, "sources": [source], "content": "Geheimer Dokumenttext"},
        ),
        ("tool_call", "Suche ausführen", {"name": "search_knowledge", "ok": True}),
        ("guardrail", "Notfall erkannt", {"reason_code": "emergency"}),
    ]:
        await audit(
            db_session,
            kind,
            summary,
            detail,
            message_id=message.id,
            conversation_id=conversation.id,
            user_id=owner.id,
        )
    await db_session.flush()
    url = f"/api/messages/{message.id}"
    response = await client.get(url + "/audit")
    assert response.status_code == 200
    assert [entry["event_type"] for entry in response.json()] == [
        "llm_call",
        "retrieval",
        "tool_call",
        "guardrail",
    ]
    assert "Geheimer Dokumenttext" not in response.text
    response = await client.get(url + "/transparency")
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "test-model"
    assert body["provider"] is None
    # The API adds the optional retrieval date of each source.
    assert body["sources"] == [
        {**source, "retrieved": None} for source in message.sources
    ]
    assert body["tools"] == [
        {"name": "search_knowledge", "label": "Suche ausführen", "ok": True}
    ]
    assert body["guardrails"] == [{"code": "emergency", "summary": "Notfall erkannt"}]
    assert body["retrieval"] == {"query": None, "chunks": []}
    assert body["confidence"]["level"] == "hoch"
    message.sources = [source]
    await db_session.flush()
    assert (await client.get(url + "/transparency")).json()["confidence"][
        "level"
    ] == "mittel"
    message.sources = []
    await db_session.flush()
    assert (await client.get(url + "/transparency")).json()["confidence"][
        "level"
    ] == "niedrig"
    message.sources = [source, {**source, "url": "https://example.org/zwei"}]
    await audit(
        db_session,
        "tool_call",
        "Fehler",
        {"name": "tool", "ok": False},
        message_id=message.id,
    )
    await db_session.flush()
    assert (await client.get(url + "/transparency")).json()["confidence"][
        "level"
    ] == "mittel"
    escalation = Escalation(
        id=uuid4(),
        conversation_id=conversation.id,
        message_id=message.id,
        reason_code="no_source",
        target={"name": "Beratung"},
        handover_summary="Privat",
    )
    db_session.add(escalation)
    await db_session.flush()
    message.escalation_id = escalation.id
    await db_session.flush()
    body = (await client.get(url + "/transparency")).json()
    assert body["confidence"]["level"] == "niedrig"
    assert body["escalation"]["reason_code"] == "no_source"
    assert "Privat" not in str(body)
    app.dependency_overrides[current_user] = lambda: other
    assert (await client.get(url + "/audit")).status_code == 404
    assert (await client.get(url + "/transparency")).status_code == 404
