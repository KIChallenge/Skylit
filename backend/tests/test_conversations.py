from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import (
    Appointment,
    Case,
    CaseStep,
    Conversation,
    Document,
    Escalation,
    FormDraft,
    Message,
    Provider,
    User,
)
from app.seed import seed


@pytest_asyncio.fixture
async def api(db_session):
    await seed(db_session)

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


async def login(api, persona_id="maria"):
    response = await api.post("/api/auth/login", json={"persona_id": persona_id})
    assert response.status_code == 200
    return response


async def create(api, title=None):
    body = {"title": title} if title else {}
    response = await api.post("/api/conversations", json=body)
    assert response.status_code == 201
    return response.json()


async def add_steps(db, case_id, statuses):
    for position, status in enumerate(statuses):
        db.add(
            CaseStep(
                id=uuid4(),
                case_id=UUID(case_id),
                title=f"Schritt {position + 1}",
                status=status,
                category="info",
                position=position,
            )
        )
    await db.commit()


async def count(db, model, *where):
    return await db.scalar(select(func.count()).select_from(model).where(*where))


async def test_routes_require_login(api):
    some_id = uuid4()
    calls = [
        api.get("/api/conversations"),
        api.post("/api/conversations", json={}),
        api.get(f"/api/conversations/{some_id}"),
        api.delete(f"/api/conversations/{some_id}"),
        api.get(f"/api/conversations/{some_id}/case"),
        api.patch(f"/api/case-steps/{some_id}", json={"status": "done"}),
        api.post("/api/dev/reset"),
    ]
    for call in calls:
        response = await call
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"


async def test_create_list_get_patch_delete(api, db_session):
    await login(api)
    created = await create(api, "Pflegegeld für Mama")
    assert created["title"] == "Pflegegeld für Mama"
    assert created["messages"] == []
    assert created["case"]["title"] == "Mein Fall"
    assert created["case"]["subject"] == "self"
    assert created["case"]["steps"] == []
    conversation_id = created["id"]

    await add_steps(db_session, created["case"]["id"], ["open", "done"])
    start = datetime.now(UTC)
    source = {"title": "Pflegegeld", "url": "https://www.pv.at", "publisher": "PVA"}
    # Insert the newer message first: the API must sort, not the insert order.
    for offset, role, content in [(1, "assistant", "Antwort"), (0, "user", "Frage")]:
        db_session.add(
            Message(
                id=uuid4(),
                conversation_id=UUID(conversation_id),
                role=role,
                content=content,
                created_at=start + timedelta(seconds=offset),
                sources=[source],
            )
        )
    await db_session.commit()

    response = await api.get("/api/conversations")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": conversation_id,
            "title": "Pflegegeld für Mama",
            "updated_at": created["updated_at"],
            "open_steps": 1,
        }
    ]

    response = await api.get(f"/api/conversations/{conversation_id}")
    assert response.status_code == 200
    body = response.json()
    assert [m["content"] for m in body["messages"]] == ["Frage", "Antwort"]
    assert body["messages"][0]["sources"][0]["publisher"] == "PVA"
    assert body["messages"][0]["document_ids"] == []
    assert body["messages"][0]["escalation_id"] is None
    steps = body["case"]["steps"]
    assert [s["position"] for s in steps] == [0, 1]

    response = await api.get(f"/api/conversations/{conversation_id}/case")
    assert response.status_code == 200
    case = response.json()
    assert case["id"] == created["case"]["id"]

    response = await api.patch(
        f"/api/case-steps/{steps[0]['id']}", json={"status": "done"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "done"
    response = await api.get(f"/api/conversations/{conversation_id}/case")
    assert response.json()["updated_at"] > case["updated_at"]
    response = await api.get("/api/conversations")
    assert response.json()[0]["open_steps"] == 0

    response = await api.patch(
        f"/api/case-steps/{steps[0]['id']}", json={"status": "finished"}
    )
    assert response.status_code == 422

    response = await api.delete(f"/api/conversations/{conversation_id}")
    assert response.status_code == 204
    assert (await api.get("/api/conversations")).json() == []
    response = await api.get(f"/api/conversations/{conversation_id}")
    assert response.status_code == 404
    assert await count(db_session, Case, Case.id == UUID(case["id"])) == 0
    assert (
        await count(
            db_session, Message, Message.conversation_id == UUID(conversation_id)
        )
        == 0
    )


async def test_post_without_body_uses_default_title(api):
    await login(api)
    response = await api.post("/api/conversations")
    assert response.status_code == 201
    assert response.json()["title"] == "Neuer Fall"


async def test_list_is_newest_first_with_open_steps(api, db_session):
    await login(api)
    first = await create(api, "Erster Fall")
    second = await create(api, "Zweiter Fall")
    await add_steps(db_session, first["case"]["id"], ["open", "in_progress", "done"])
    await add_steps(db_session, second["case"]["id"], ["blocked"])

    summaries = (await api.get("/api/conversations")).json()
    assert [s["title"] for s in summaries] == ["Zweiter Fall", "Erster Fall"]
    assert [s["open_steps"] for s in summaries] == [1, 2]


def test_display_title_follows_the_event_of_the_conversation():
    from app.services.conversation_service import display_title

    assert display_title("Neuer Fall", "Pflege nach Spitalsentlassung", "Hallo") == (
        "Pflege nach Spitalsentlassung"
    )
    assert display_title("Reha für Mama", "Mein Fall", "Hallo") == "Reha für Mama"
    assert display_title("Neuer Fall", "Mein Fall", "  Kopfweh   seit gestern ") == (
        "Kopfweh seit gestern"
    )
    long = "Meine Mutter ist gerade aus dem Spital gekommen und kommt nicht zurecht"
    title = display_title("Neuer Fall", "Mein Fall", long)
    assert title == "Meine Mutter ist gerade aus dem Spital gekommen…"
    assert len(title) <= 49
    assert display_title("Neuer Fall", "Mein Fall", None) == "Neuer Fall"


async def test_list_names_conversations_after_case_or_first_message(api, db_session):
    await login(api)
    with_case = await create(api)
    with_message = await create(api)
    empty = await create(api)
    case = await db_session.get(Case, UUID(with_case["case"]["id"]))
    case.title = "Onkologische Reha beantragen"
    now = datetime.now(UTC)
    db_session.add(
        Message(
            id=uuid4(),
            conversation_id=UUID(with_message["id"]),
            role="user",
            content="Ich habe seit gestern Kopfschmerzen, wohin soll ich gehen?",
            created_at=now,
        )
    )
    await db_session.commit()

    titles = {s["id"]: s["title"] for s in (await api.get("/api/conversations")).json()}
    assert titles[with_case["id"]] == "Onkologische Reha beantragen"
    expected = "Ich habe seit gestern Kopfschmerzen, wohin soll…"
    assert titles[with_message["id"]] == expected
    assert titles[empty["id"]] == "Neuer Fall"


async def test_other_persona_ids_return_not_found(api, db_session):
    await login(api, "maria")
    created = await create(api, "Marias Fall")
    await add_steps(db_session, created["case"]["id"], ["open"])
    step_id = (await api.get(f"/api/conversations/{created['id']}")).json()["case"][
        "steps"
    ][0]["id"]

    await login(api, "stefan")
    assert (await api.get("/api/conversations")).json() == []
    for response in [
        await api.get(f"/api/conversations/{created['id']}"),
        await api.get(f"/api/conversations/{created['id']}/case"),
        await api.delete(f"/api/conversations/{created['id']}"),
        await api.patch(f"/api/case-steps/{step_id}", json={"status": "done"}),
        await api.get(f"/api/conversations/{uuid4()}"),
    ]:
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    await login(api, "maria")
    body = (await api.get(f"/api/conversations/{created['id']}")).json()
    assert body["case"]["steps"][0]["status"] == "open"


async def add_demo_rows(db, persona_id, conversation_id):
    user = await db.scalar(select(User).where(User.persona_id == persona_id))
    provider_id = await db.scalar(select(Provider.id).limit(1))
    now = datetime.now(UTC)
    db.add_all(
        [
            Document(
                id=uuid4(),
                user_id=user.id,
                conversation_id=UUID(conversation_id),
                filename="entlassungsbrief.pdf",
                mime_type="application/pdf",
                storage_path="/tmp/entlassungsbrief.pdf",
            ),
            FormDraft(
                id=uuid4(),
                user_id=user.id,
                conversation_id=UUID(conversation_id),
                form_id="pva_pflegegeld",
            ),
            Appointment(
                id=uuid4(),
                user_id=user.id,
                conversation_id=UUID(conversation_id),
                provider_id=provider_id,
                start=now,
                end=now + timedelta(minutes=30),
            ),
            Escalation(
                id=uuid4(),
                conversation_id=UUID(conversation_id),
                reason_code="user_stuck",
                target={"name": "ÖGK Kundenservice"},
                handover_summary="Die Person braucht Hilfe beim Antrag.",
            ),
        ]
    )
    await db.commit()
    return user


async def test_dev_reset_wipes_only_the_current_persona(api, db_session):
    await login(api, "stefan")
    stefans = await create(api, "Stefans Fall")
    stefan = await add_demo_rows(db_session, "stefan", stefans["id"])

    await login(api, "maria")
    marias = await create(api, "Marias Fall")
    maria = await add_demo_rows(db_session, "maria", marias["id"])

    response = await api.post("/api/dev/reset")
    assert response.status_code == 204
    assert (await api.get("/api/conversations")).json() == []
    for model in (Document, FormDraft, Appointment):
        assert await count(db_session, model, model.user_id == maria.id) == 0
        assert await count(db_session, model, model.user_id == stefan.id) == 1
    assert await count(db_session, Conversation, Conversation.user_id == maria.id) == 0
    assert (
        await count(
            db_session, Escalation, Escalation.conversation_id == UUID(stefans["id"])
        )
        == 1
    )

    await login(api, "stefan")
    summaries = (await api.get("/api/conversations")).json()
    assert [s["id"] for s in summaries] == [stefans["id"]]


async def test_dev_reset_is_hidden_in_production(api, monkeypatch):
    await login(api)
    monkeypatch.setattr(settings, "app_env", "production")
    response = await api.post("/api/dev/reset")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
