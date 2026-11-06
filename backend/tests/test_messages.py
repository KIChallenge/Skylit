"""Streaming chat route tests with LLM_PROVIDER=fake and a fake retriever."""

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from httpx import ASGITransport, AsyncClient
from pydantic import TypeAdapter
from sqlalchemy import select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import messages
from app.api.auth import router as auth_router
from app.api.messages import MessageCreate, stream_sessions
from app.api.messages import router as messages_router
from app.api.schema_events import router as schema_events_router
from app.config import settings
from app.db import get_db
from app.llm import client as client_module
from app.main import http_error, validation_error
from app.models import Case, Conversation, Message, User
from app.rag import retriever
from app.schemas.events import Event
from app.seed import seed

S1_INTAKE = (
    "Meine Mutter ist gerade aus dem Spital gekommen und kommt allein nicht mehr "
    "zurecht. Was muss ich tun?"
)
S3_EMERGENCY = "Meine Mutter hat plötzlich starke Atemnot."
CHUNK = {
    "heading": "Antrag",
    "content": "Das Pflegegeld beantragen Sie bei der Pensionsversicherung.",
    "source": {
        "title": "Pflegegeld",
        "url": "https://example.test/pflegegeld",
        "publisher": "Sozialministerium",
    },
}


@pytest.fixture(autouse=True)
def llm_settings(monkeypatch):
    """Fix the settings, because hackkit passes the real .env as environment."""
    monkeypatch.setattr(settings, "llm_provider", "fake")
    monkeypatch.setattr(settings, "llm_record", False)
    monkeypatch.setattr(settings, "llm_max_tool_rounds", 3)
    monkeypatch.setattr(settings, "llm_enable_thinking", False)
    client_module._build_client.cache_clear()
    yield
    client_module._build_client.cache_clear()


@pytest.fixture(autouse=True)
def fake_retriever(monkeypatch) -> list[str]:
    """Replace the hybrid search, so no embedder and no knowledge base are needed."""
    queries: list[str] = []

    async def search(session, query, **kwargs):
        queries.append(query)
        return [CHUNK]

    monkeypatch.setattr(retriever, "search", search)
    return queries


def build_app() -> FastAPI:
    # main.py belongs to another task; this app mounts the routers like main does.
    app = FastAPI()
    app.add_exception_handler(StarletteHTTPException, http_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    for router in (auth_router, messages_router, schema_events_router):
        app.include_router(router, prefix="/api")
    return app


@pytest_asyncio.fixture
async def api(db_session):
    await seed(db_session)
    await db_session.commit()
    app = build_app()

    async def override_db():
        yield db_session

    @asynccontextmanager
    async def shared_session():
        # The test transaction must stay open, so the stream must not close it.
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[stream_sessions] = lambda: shared_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield SimpleNamespace(client=client, session=db_session)


async def login(api, persona_id: str = "maria") -> User:
    response = await api.client.post(
        "/api/auth/login", json={"persona_id": persona_id}
    )
    assert response.status_code == 200
    return await api.session.scalar(select(User).where(User.persona_id == persona_id))


async def add_conversation(session, user_id) -> Conversation:
    conversation = Conversation(id=uuid4(), user_id=user_id, title="Neuer Fall")
    session.add(conversation)
    await session.flush()
    session.add(
        Case(id=uuid4(), conversation_id=conversation.id, title="Mein Fall")
    )
    await session.commit()
    return conversation


def parse_sse(body: str) -> list[Any]:
    adapter = TypeAdapter(Event)
    events = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        data = json.loads(lines["data"])
        assert "type" not in data
        events.append(adapter.validate_python({"type": lines["event"], **data}))
    return events


async def post(api, conversation_id, content: str = S1_INTAKE, **extra):
    return await api.client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": content, **extra},
    )


def types(events: list[Any]) -> list[str]:
    return [event.type for event in events]


async def test_turn_streams_the_events_in_contract_order(api, fake_retriever):
    user = await login(api)
    conversation = await add_conversation(api.session, user.id)

    response = await post(api, conversation.id)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    events = parse_sse(response.text)
    kinds = types(events)
    assert kinds[0] == "message.created"
    assert kinds[-1] == "message.completed"
    assert kinds.count("message.created") == kinds.count("message.completed") == 1
    assert "error" not in kinds
    assert "text.delta" in kinds
    assert events[0].conversation_id == conversation.id
    assert fake_retriever and S1_INTAKE in fake_retriever[0]


async def test_turn_persists_both_messages(api):
    user = await login(api)
    conversation = await add_conversation(api.session, user.id)

    events = parse_sse((await post(api, conversation.id)).text)

    stored = (
        await api.session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
        )
    ).all()
    assert [message.role for message in stored] == ["user", "assistant"]
    assert stored[0].content == S1_INTAKE
    assistant = stored[1]
    assert assistant.id == events[0].message_id == events[-1].message_id
    streamed = "".join(event.delta for event in events if event.type == "text.delta")
    assert assistant.content == streamed


async def test_emergency_comes_before_any_text(api, fake_retriever):
    user = await login(api)
    conversation = await add_conversation(api.session, user.id)

    events = parse_sse((await post(api, conversation.id, S3_EMERGENCY)).text)

    kinds = types(events)
    assert kinds[0] == "message.created"
    assert kinds[-1] == "message.completed"
    assert "emergency" in kinds and "text.delta" in kinds
    assert kinds.index("emergency") < kinds.index("text.delta")
    emergency = events[kinds.index("emergency")]
    assert emergency.contacts
    # An emergency answer needs no knowledge search.
    assert fake_retriever == []


async def test_conversation_of_another_user_is_not_found(api):
    stefan = await login(api, "stefan")
    conversation = await add_conversation(api.session, stefan.id)
    await login(api, "maria")

    response = await post(api, conversation.id)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    count = await api.session.scalar(
        select(Message.id).where(Message.conversation_id == conversation.id)
    )
    assert count is None


async def test_unknown_conversation_is_not_found(api):
    await login(api)
    response = await post(api, uuid4())
    assert response.status_code == 404


async def test_turn_requires_a_session_cookie(api):
    maria = await api.session.scalar(select(User).where(User.persona_id == "maria"))
    conversation = await add_conversation(api.session, maria.id)

    response = await post(api, conversation.id)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("content", ["", "x" * 4001])
async def test_content_length_is_validated(api, content):
    user = await login(api)
    conversation = await add_conversation(api.session, user.id)

    response = await post(api, conversation.id, content)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_disconnect_stops_the_turn(api):
    user = await login(api)
    conversation = await add_conversation(api.session, user.id)

    class Request:
        checks = 0

        async def is_disconnected(self) -> bool:
            # The client leaves after the first event.
            self.checks += 1
            return self.checks > 1

    @asynccontextmanager
    async def shared_session():
        yield api.session

    chunks = [
        chunk
        async for chunk in messages._turn_events(
            Request(),
            lambda: shared_session(),
            user.id,
            conversation.id,
            MessageCreate(content=S1_INTAKE),
        )
    ]

    assert len(chunks) == 1
    assert chunks[0].startswith("event: message.created\n")
    roles = (
        await api.session.scalars(
            select(Message.role).where(Message.conversation_id == conversation.id)
        )
    ).all()
    assert roles == ["user"]


async def test_event_schema_is_in_openapi(api):
    await login(api)
    response = await api.client.get("/api/_schema/events")
    assert response.status_code == 200
    assert response.json()["type"] == "status"

    schema = (await api.client.get("/openapi.json")).json()
    operation = schema["paths"]["/api/_schema/events"]["get"]
    content = operation["responses"]["200"]["content"]["application/json"]
    assert "discriminator" in json.dumps(content["schema"])
    components = schema["components"]["schemas"]
    for name in ("MessageCreated", "EmergencyEvent", "TextDelta", "MessageCompleted"):
        assert name in components
