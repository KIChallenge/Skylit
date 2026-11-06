import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException

from app.api.auth import router as auth_router
from app.api.documents import background_sessions
from app.api.documents import router as documents_router
from app.config import settings
from app.deps import get_db
from app.documents import extract as extract_module
from app.llm.types import LLMError, ToolCall
from app.main import http_error
from app.models import Case, Conversation, Document, User
from app.seed import seed
from app.tools import ToolContext, registry
from tests.test_documents import PDF, SAMPLE_PDF, StubLLM, golden_reply

POLL_ATTEMPTS = 20


@pytest_asyncio.fixture
async def stub_llm(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    stub = StubLLM(json.dumps(golden_reply()))
    monkeypatch.setattr(extract_module, "get_llm_client", lambda: stub)
    return stub


@pytest_asyncio.fixture
async def seeded(db_session) -> None:
    await seed(db_session)
    # A savepoint left open here would break the savepoints of the request sessions.
    await db_session.commit()


@pytest.fixture
def opened_sessions() -> dict[str, list[AsyncSession]]:
    return {"request": [], "background": []}


@pytest_asyncio.fixture
async def api(
    db_session, seeded, stub_llm, opened_sessions
) -> AsyncIterator[AsyncClient]:
    """Each request and background task gets its own session, as in production."""

    @asynccontextmanager
    async def new_session(kind: str) -> AsyncIterator[AsyncSession]:
        async with AsyncSession(
            bind=db_session.bind,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            opened_sessions[kind].append(session)
            yield session

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with new_session("request") as session:
            yield session

    app = FastAPI()
    app.include_router(auth_router, prefix="/api")
    app.include_router(documents_router, prefix="/api")
    app.add_exception_handler(HTTPException, http_error)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[background_sessions] = lambda: lambda: new_session(
        "background"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def login(api: AsyncClient, persona_id: str) -> None:
    response = await api.post("/api/auth/login", json={"persona_id": persona_id})
    assert response.status_code == 200


async def upload(
    api: AsyncClient,
    filename: str = "entlassungsbefund.pdf",
    data: bytes | None = None,
    mime_type: str = PDF,
    form: dict[str, str] | None = None,
):
    content = SAMPLE_PDF.read_bytes() if data is None else data
    return await api.post(
        "/api/documents",
        files={"file": (filename, content, mime_type)},
        data=form or {},
    )


async def poll(api: AsyncClient, document_id: str) -> dict:
    for _ in range(POLL_ATTEMPTS):
        response = await api.get(f"/api/documents/{document_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] != "processing":
            return body
    raise AssertionError("The document stayed in status processing")


async def tool_context(db: AsyncSession, persona_id: str) -> ToolContext:
    user = await db.scalar(select(User).where(User.persona_id == persona_id))
    conversation = Conversation(user_id=user.id, title="Hilfe für Anna Berger")
    db.add(conversation)
    await db.flush()
    case = Case(
        conversation_id=conversation.id,
        title="Versorgung organisieren",
        subject="parent",
        summary="",
        steps=[],
    )
    db.add(case)
    await db.flush()
    return ToolContext(
        db=db, user=user, conversation=conversation, case=case, audit=AsyncMock()
    )


async def get_document(ctx: ToolContext, document_id):
    call = ToolCall(
        id="call-test", name="get_document", arguments={"document_id": str(document_id)}
    )
    return await registry.execute(call, ctx)


async def test_upload_processes_the_discharge_letter(api, opened_sessions):
    await login(api, "maria")

    response = await upload(api)

    assert response.status_code == 201
    created = response.json()
    assert created["status"] == "processing"
    assert created["extracted"] is None
    assert created["filename"] == "entlassungsbefund.pdf"
    assert created["mime_type"] == PDF

    ready = await poll(api, created["id"])
    assert ready["status"] == "ready"
    assert ready["kind"] == "discharge_letter"
    assert len(ready["extracted"]["documented_recommendations"]) == 5
    # The extraction ran in its own session, not in the request session.
    assert len(opened_sessions["background"]) == 1
    assert opened_sessions["background"][0] not in opened_sessions["request"]


async def test_upload_returns_original_file_to_the_owner(api):
    await login(api, "maria")
    created = (await upload(api)).json()

    response = await api.get(f"/api/documents/{created['id']}/file")

    assert response.status_code == 200
    assert response.content == SAMPLE_PDF.read_bytes()
    assert response.headers["content-type"] == PDF
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_missing_stored_file_returns_contract_error(api, db_session):
    await login(api, "maria")
    created = (await upload(api)).json()
    document = await db_session.get(Document, UUID(created["id"]))
    Path(document.storage_path).unlink()

    response = await api.get(f"/api/documents/{created['id']}/file")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_other_user_cannot_read_the_document(api):
    await login(api, "maria")
    created = (await upload(api)).json()

    await login(api, "elif")
    for suffix in ("", "/file"):
        response = await api.get(f"/api/documents/{created['id']}{suffix}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


async def test_read_routes_need_a_login(api):
    response = await api.get(f"/api/documents/{uuid4()}")
    assert response.status_code == 401
    assert (await upload(api)).status_code == 401


async def test_text_file_returns_415_and_stores_nothing(api, tmp_path, stub_llm):
    await login(api, "maria")

    response = await upload(
        api, filename="notiz.txt", data=b"Hallo", mime_type="text/plain"
    )

    assert response.status_code == 415
    error = response.json()["error"]
    assert error["code"] == "unsupported_type"
    assert "PDF" in error["message"]
    assert not (tmp_path / "uploads").exists()
    assert stub_llm.calls == []


async def test_large_file_returns_413(api, monkeypatch, stub_llm):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    await login(api, "maria")

    response = await upload(api, data=b"x" * (1024 * 1024 + 1))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    assert stub_llm.calls == []


async def test_empty_file_returns_400(api):
    await login(api, "maria")

    response = await upload(api, data=b"")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_file"


async def test_mime_type_parameters_are_ignored(api):
    await login(api, "maria")

    response = await upload(api, mime_type="Application/PDF; name=brief.pdf")

    assert response.status_code == 201
    assert response.json()["mime_type"] == PDF


async def test_upload_links_only_an_own_conversation(api, db_session):
    ctx = await tool_context(db_session, "maria")
    await db_session.commit()
    form = {"conversation_id": str(ctx.conversation.id)}

    await login(api, "elif")
    assert (await upload(api, form=form)).status_code == 404

    await login(api, "maria")
    created = (await upload(api, form=form)).json()
    document = await db_session.get(Document, UUID(created["id"]))
    assert document.conversation_id == ctx.conversation.id


async def test_llm_failure_ends_in_status_failed(api, stub_llm):
    stub_llm.error = LLMError("timeout", "Der Dienst antwortet nicht.")
    await login(api, "maria")

    created = (await upload(api)).json()

    failed = await poll(api, created["id"])
    assert failed["status"] == "failed"
    assert failed["extracted"] is None


async def test_get_document_returns_extraction_and_card(api, db_session):
    await login(api, "maria")
    created = (await upload(api)).json()
    ctx = await tool_context(db_session, "maria")

    result = await get_document(ctx, created["id"])

    assert result.ok
    assert len(result.result["documented_recommendations"]) == 5
    assert result.card.type == "document_summary"
    assert str(result.card.document_id) == created["id"]
    assert result.card.extraction == result.result


async def test_get_document_is_owner_only(api, db_session):
    await login(api, "maria")
    created = (await upload(api)).json()
    ctx = await tool_context(db_session, "elif")

    result = await get_document(ctx, created["id"])

    assert not result.ok
    assert result.card is None
    assert "document_id" in result.result["error"]


async def test_get_document_tells_the_model_to_wait(db_session, seeded, tmp_path):
    ctx = await tool_context(db_session, "maria")
    document = Document(
        user_id=ctx.user.id,
        filename="brief.pdf",
        mime_type=PDF,
        storage_path=str(tmp_path / "brief.pdf"),
        status="processing",
    )
    db_session.add(document)
    await db_session.flush()

    result = await get_document(ctx, document.id)

    assert not result.ok
    assert "Warte" in result.result["error"]
    assert result.card is None


async def test_get_document_reads_a_status_change_in_the_same_session(
    db_session, seeded, tmp_path
):
    ctx = await tool_context(db_session, "maria")
    document = Document(
        user_id=ctx.user.id,
        filename="brief.pdf",
        mime_type=PDF,
        storage_path=str(tmp_path / "brief.pdf"),
        status="processing",
    )
    db_session.add(document)
    await db_session.flush()
    async with AsyncSession(
        bind=db_session.bind, join_transaction_mode="create_savepoint"
    ) as other:
        row = await other.get(Document, document.id)
        row.status = "failed"
        row.error = "Die Datei ist leer."
        await other.commit()

    result = await get_document(ctx, document.id)

    assert not result.ok
    assert result.result["error"] == "Die Datei ist leer."
