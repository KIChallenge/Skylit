"""Golden-path tools and read routes with PostgreSQL and synthetic personas."""

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pypdf import PdfReader
from sqlalchemy import func, select

from app.api.auth import router as auth_router
from app.api.escalations import router as escalations_router
from app.api.form_drafts import router as form_drafts_router
from app.config import settings
from app.deps import get_db
from app.forms.registry import FILLED_BY_OTHERS, get_field_map
from app.guardrails.escalation import load_contacts
from app.llm.types import ToolCall
from app.models import (
    Case,
    CaseStep,
    Conversation,
    Document,
    Escalation,
    FormDraft,
    KnowledgeChunk,
    KnowledgeDocument,
    User,
)
from app.rag import retriever
from app.seed import seed
from app.tools import ToolContext, registry
from app.tools.form_tools import to_form_draft
from scripts import record_demo

# Anna Berger is the synthetic patient from the SV-Box.
ANNA = {
    "applicant.last_name": "Berger",
    "applicant.first_name": "Anna",
    "applicant.date_of_birth": "14.03.1948",
    "applicant.svnr": "1234 140348",
    "applicant.address.street": "Musterstraße",
    "applicant.address.house_number": "12",
    "applicant.address.zip": "1030",
    "applicant.address.city": "Wien",
    "application.type": "zuerkennung",
    "application.attachments": "Entlassungsbefund (Kopie)",
}


async def execute(ctx, name, **arguments):
    return await registry.execute(
        ToolCall(id="call-test", name=name, arguments=arguments), ctx
    )


@pytest_asyncio.fixture
async def ctx(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    await seed(db_session)
    user = await db_session.scalar(select(User).where(User.persona_id == "maria"))
    conversation = Conversation(user_id=user.id, title="Hilfe für Anna Berger")
    db_session.add(conversation)
    await db_session.flush()
    case = Case(
        conversation_id=conversation.id,
        title="Versorgung organisieren",
        subject="parent",
        summary="Anna Berger lebt allein in Wien. Maria organisiert Unterstützung.",
        steps=[],
    )
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
    app.include_router(auth_router, prefix="/api")
    app.include_router(form_drafts_router, prefix="/api")
    app.include_router(escalations_router, prefix="/api")

    async def override_db():
        yield ctx.db

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def test_search_knowledge_uses_retriever_and_preserves_sources(ctx, monkeypatch):
    class FixedEmbedder:
        async def embed_query(self, query):
            assert query == "Pflegegeld beantragen"
            return [1.0] + [0.0] * (settings.embedding_dim - 1)

    monkeypatch.setattr(retriever, "get_embedder", FixedEmbedder)
    for category in ("pflege", "kosten"):
        document = KnowledgeDocument(
            slug=f"{category}/pflegegeld",
            title=f"Pflegegeld ({category})",
            source_url="https://www.pv.at/web/pflegegeld",
            publisher="pv.at",
            category=category,
            content_hash=category,
        )
        ctx.db.add(document)
        await ctx.db.flush()
        ctx.db.add(
            KnowledgeChunk(
                document_id=document.id,
                chunk_index=0,
                heading="Antrag",
                content="Pflegegeld beantragen Sie bei der PVA.",
                embedding=[1.0] + [0.0] * (settings.embedding_dim - 1),
                content_hash=category,
            )
        )
    await ctx.db.flush()
    result = await execute(
        ctx,
        "search_knowledge",
        query="Pflegegeld beantragen",
        category="pflege",
        top_k=1,
    )
    assert result.ok
    assert result.card is None
    assert result.result["chunks"] == [
        {
            "heading": "Antrag",
            "content": "Pflegegeld beantragen Sie bei der PVA.",
            "source": {
                "title": "Pflegegeld (pflege)",
                "url": "https://www.pv.at/web/pflegegeld",
                "publisher": "pv.at",
                "retrieved": None,
            },
        }
    ]
    # An empty or unknown category falls back to all categories.
    fallback = await execute(
        ctx, "search_knowledge", query="Pflegegeld beantragen",
        category="pflegekarenz", top_k=2,
    )
    assert fallback.ok
    assert {c["source"]["title"] for c in fallback.result["chunks"]} == {
        "Pflegegeld (pflege)", "Pflegegeld (kosten)",
    }


async def test_get_leistung_returns_conditions_source_and_card(ctx):
    result = await execute(ctx, "get_leistung", leistung_id="pflegegeld")
    assert result.ok
    assert result.card.type == "leistung"
    leistung = result.card.leistung
    assert leistung.conditions
    assert leistung.form_ids == ["pva_pflegegeld"]
    assert leistung.source.url.startswith("https://www.oesterreich.gv.at/")
    assert leistung.source.publisher == "www.oesterreich.gv.at"
    assert "Pensionsversicherungsanstalt" in leistung.office_hint
    assert result.result["leistung"] == leistung.model_dump(mode="json")


async def test_find_office_for_pflegegeld_in_1030_returns_pva(ctx):
    result = await execute(
        ctx, "find_office", leistung_id="pflegegeld", postal_code="1030"
    )
    assert result.ok
    office = result.card.office
    assert result.card.type == "office"
    assert office.id == "pva_landesstelle_wien"
    assert office.postal_code == "1030"
    maps = urlsplit(office.maps_url)
    assert maps.netloc == "www.google.com"
    assert parse_qs(maps.query)["query"] == [
        f"{office.address}, {office.postal_code} {office.city}"
    ]
    assert result.result["offices"] == [office.model_dump(mode="json")]


async def test_find_office_filters_kind_and_bundesland(ctx):
    result = await execute(
        ctx, "find_office", office_kind="care_services_wien", bundesland="wien"
    )
    assert result.ok
    assert result.card.office.id == "fsw_beratungszentrum_pflege"
    empty = await execute(
        ctx, "find_office", leistung_id="pflegegeld", bundesland="Tirol"
    )
    assert not empty.ok and "error" in empty.result


@pytest.mark.parametrize(
    "office_kind",
    ["pension_insurer", "health_insurer", "care_services_wien", "ministry_hotline"],
)
async def test_find_office_accepts_each_seeded_kind(ctx, office_kind):
    result = await execute(ctx, "find_office", office_kind=office_kind)
    assert result.ok
    seed_path = Path(__file__).resolve().parents[1] / "seed/offices.json"
    offices = json.loads(seed_path.read_text(encoding="utf-8"))
    expected_ids = {office["id"] for office in offices if office["kind"] == office_kind}
    assert {office["id"] for office in result.result["offices"]} == expected_ids
    assert result.card.office.id in expected_ids


@pytest.mark.parametrize("office_kind", ["beratung_pflege", "beratung_pflegetelefon"])
async def test_find_office_unknown_kind_lists_allowed_values(office_kind):
    # Invalid arguments must fail before the handler accesses the database.
    result = await execute(None, "find_office", office_kind=office_kind)
    assert not result.ok
    assert result.card is None
    assert "office_kind" in result.result["error"]
    for allowed in (
        "pension_insurer", "health_insurer", "care_services_wien", "ministry_hotline"
    ):
        assert allowed in result.result["error"]


async def test_prepare_form_persists_accepted_values_and_readable_pdf(ctx):
    mappings = get_field_map("pva_pflegegeld")
    protected = {
        key: "Darf nicht übernommen werden"
        for key, mapping in mappings.items()
        if mapping.filled_by in FILLED_BY_OTHERS
    }
    result = await execute(
        ctx,
        "prepare_form",
        form_id="pva_pflegegeld",
        values={**ANNA, **protected, "invented.key": "Unbekannt"},
    )
    assert result.ok
    assert result.card.type == "form_draft"
    draft = result.card.form_draft
    filled = {field.key: field.value for field in draft.filled}
    assert filled["applicant.first_name"] == "Anna"
    assert filled["applicant.last_name"] == "Berger"
    assert "applicant.phone" in {field.key for field in draft.missing}
    assert set(protected) == {field.key for field in draft.to_be_filled_by_others}
    assert set(result.result["rejected"]) == {*protected, "invented.key"}
    assert set(protected).isdisjoint(filled)
    assert draft.pdf_url == f"/api/form-drafts/{draft.id}/pdf"

    row = await ctx.db.get(FormDraft, draft.id)
    assert row.user_id == ctx.user.id
    assert row.conversation_id == ctx.conversation.id
    assert row.values == filled
    path = Path(settings.upload_dir) / "form_drafts" / f"{draft.id}.pdf"
    assert Path(row.pdf_path) == path
    reader = PdfReader(path)
    assert len(reader.pages) > 0
    fields = reader.get_fields()
    assert fields["Vorname"]["/V"] == "Anna"
    assert fields["Fam.Name"]["/V"] == "Berger"
    assert not path.with_suffix(".tmp").exists()


@pytest.mark.parametrize(
    "target_kind",
    [
        None,
        "gp",
        "treating_team",
        "hausaerztin_behandelndes_team",
        "health_advice",
        "gesundheitsberatung_1450",
    ],
)
async def test_escalate_medical_question_builds_factual_handover(ctx, target_kind):
    ctx.db.add_all(
        [
            CaseStep(
                case_id=ctx.case.id,
                title="Pflegegeldantrag vorbereitet",
                description="",
                category="form",
                status="done",
                position=0,
            ),
            CaseStep(
                case_id=ctx.case.id,
                title="Noch nicht erledigter Schritt",
                description="",
                category="contact",
                status="open",
                position=1,
            ),
            Document(
                user_id=ctx.user.id,
                conversation_id=ctx.conversation.id,
                filename="entlassungsbefund.pdf",
                mime_type="application/pdf",
                storage_path="/synthetic/document.pdf",
                status="ready",
                extracted={"diagnosis": "Nicht in die Übergabe kopieren"},
            ),
        ]
    )
    await ctx.db.flush()
    target = {"target_kind": target_kind} if target_kind is not None else {}
    result = await execute(
        ctx,
        "escalate",
        reason_code="medical_question",
        **target,
        open_question="Bitte die Frage zur Medikation mit der Hausärztin klären.",
    )
    assert result.ok
    assert result.card.type == "escalation"
    escalation = result.card.escalation
    contact = next(
        contact for contact in load_contacts()
        if contact["id"] == "gesundheitsberatung_1450"
    )
    assert escalation.target.name == contact["name"]
    assert escalation.target.phone == contact["phone"] == "1450"
    summary = escalation.handover_summary
    assert "Elternteil" in summary
    assert ctx.case.summary in summary
    assert "Pflegegeldantrag vorbereitet" in summary
    assert "entlassungsbefund.pdf" in summary
    assert "Frage zur Medikation" in summary
    assert "Hausärztin" in summary
    assert "Noch nicht erledigter Schritt" not in summary
    assert "Nicht in die Übergabe kopieren" not in summary
    assert "diagnosis" not in summary
    row = await ctx.db.get(Escalation, escalation.id)
    assert row.handover_summary == summary
    assert row.conversation_id == ctx.conversation.id
    ctx.audit.assert_awaited_once()
    assert "Anna Berger" not in str(ctx.audit.call_args)


def test_escalation_seed_has_no_visible_placeholders():
    contacts = load_contacts()
    assert contacts
    for contact in contacts:
        for field in ("name", "phone", "url", "hours", "note"):
            value = (contact[field] or "").upper()
            for placeholder in ("UNVERIFIED", "TODO", "PLACEHOLDER", "TBD"):
                assert placeholder not in value, (contact["id"], field)


@pytest.mark.parametrize(
    ("check", "fallback_turn", "expected_exit"),
    [(True, 0, 1), (True, 3, 1), (True, None, 0), (False, 0, 0)],
)
def test_record_demo_check_rejects_replay_fallback(
    monkeypatch, capsys, check, fallback_turn, expected_exit
):
    sent_turns = []
    transparency_turns = []
    client_class = httpx.Client

    def respond(request):
        path = request.url.path
        if path.endswith("/transparency"):
            index = int(path.split("/")[-2])
            transparency_turns.append(index)
            # A successful final round must not hide an earlier fallback.
            model = None if index == 4 else settings.eustella_model
            entries = [] if index == 4 else [
                {
                    "event_type": "llm_call",
                    "detail": {
                        "model": "fake" if index == fallback_turn else model,
                    },
                },
                {"event_type": "llm_call", "detail": {"model": model}},
            ]
            return httpx.Response(200, json={"model": model, "entries": entries})
        if path.endswith("/messages"):
            index = len(sent_turns)
            sent_turns.append(index)
            events = [
                [{"type": "case.updated"}],
                [],
                [{"type": "tool.result", "card": {"type": "form_draft"}}],
                [{"type": "escalation"}],
                [{"type": "emergency"}],
                [{"type": "text.delta", "delta": "Your child can get the check-ups."}],
            ][index]
            events.append({"type": "message.completed", "message_id": str(index)})
            body = "".join(
                f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
                for event in events
            )
            return httpx.Response(200, text=body)
        return httpx.Response(200, json={"id": "synthetic-conversation"})

    monkeypatch.setattr(
        record_demo.httpx, "Client",
        lambda **kwargs: client_class(transport=httpx.MockTransport(respond), **kwargs),
    )
    monkeypatch.setattr(record_demo, "upload", lambda *_: "synthetic-document")
    argv = ["record_demo", "--base-url", "http://test"]
    if check:
        argv.append("--check")
    monkeypatch.setattr(record_demo.sys, "argv", argv)
    assert record_demo.main() == expected_exit
    if expected_exit:
        assert f"Turn {fallback_turn + 1}: Replay-Miss" in capsys.readouterr().err
        assert sent_turns == list(range(fallback_turn + 1))
    else:
        assert len(sent_turns) == 6
    assert transparency_turns == (sent_turns if check else [])


def test_record_demo_check_rejects_fake_final_model():
    with httpx.Client(
        base_url="http://test",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"model": "fake", "entries": []})
        ),
    ) as client:
        with pytest.raises(RuntimeError, match="Turn 3: Replay-Miss"):
            record_demo.check_replay_turn(
                client, [{"type": "message.completed", "message_id": "synthetic"}], 2
            )


@pytest.mark.parametrize("placeholder", ["", "None", "null"])
async def test_draft_email_treats_placeholder_address_as_missing(ctx, placeholder):
    result = await execute(
        ctx, "draft_email", to_label="Ordination", to_email=placeholder,
        subject="Termin", body="Sehr geehrte Damen und Herren",
    )
    assert result.ok
    assert result.card.email.to_email is None


async def test_draft_email_returns_a_draft_without_persistence(ctx):
    result = await execute(
        ctx,
        "draft_email",
        to_label="PVA Wien",
        to_email="pva-lsw@pv.at",
        subject="Frage zum Pflegegeldantrag",
        body="Bitte informieren Sie mich über die erforderlichen Unterlagen.",
    )
    assert result.ok
    assert result.card.type == "email_draft"
    assert result.card.email.subject == "Frage zum Pflegegeldantrag"
    assert result.result["ok"] is True
    assert result.result["email"] == result.card.email.model_dump(mode="json")
    assert not ctx.db.new
    without_address = await execute(
        ctx,
        "draft_email",
        to_label="Hausärztin",
        subject="Rückfrage",
        body="Bitte anrufen.",
    )
    assert without_address.ok
    assert without_address.card.email.to_email is None


async def test_case_tools_remain_registered(ctx):
    summary = await execute(
        ctx,
        "set_case_summary",
        title="Pflege",
        subject="parent",
        summary="Hilfe in Wien.",
    )
    assert summary.ok and summary.case_changed
    step = await execute(
        ctx, "upsert_case_step", title="Pflegegeld beantragen", category="form"
    )
    assert step.ok and step.case_changed


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("search_knowledge", {"query": "   "}),
        ("search_knowledge", {"query": "Pflegegeld", "top_k": 0}),
        ("get_leistung", {}),
        ("get_leistung", {"leistung_id": "unknown"}),
        ("find_office", {"postal_code": "invalid"}),
        ("find_office", {"leistung_id": "unknown"}),
        ("find_office", {"leistung_id": "pflegegeld", "office_kind": "health_insurer"}),
        ("prepare_form", {"form_id": "unknown", "values": {}}),
        ("prepare_form", {"form_id": "pva_pflegegeld", "values": {"a": {"b": 1}}}),
        (
            "escalate",
            {"reason_code": "invalid", "target_kind": "gp", "open_question": "?"},
        ),
        (
            "escalate",
            {
                "reason_code": "medical_question",
                "target_kind": "unknown",
                "open_question": "?",
            },
        ),
        (
            "escalate",
            {
                "reason_code": "emergency",
                "target_kind": "treating_team",
                "open_question": "?",
            },
        ),
        ("draft_email", {"to_label": "PVA", "subject": "", "body": "Frage"}),
        (
            "draft_email",
            {
                "to_label": "PVA",
                "to_email": "invalid",
                "subject": "Frage",
                "body": "Frage",
            },
        ),
    ],
)
async def test_invalid_input_returns_error_result(ctx, name, arguments):
    result = await execute(ctx, name, **arguments)
    assert not result.ok
    assert result.result["error"]
    assert result.error
    assert result.card is None
    assert await ctx.db.scalar(select(func.count()).select_from(FormDraft)) == 0
    assert await ctx.db.scalar(select(func.count()).select_from(Escalation)) == 0
    assert await ctx.db.scalar(select(User.id).where(User.id == ctx.user.id))


async def test_routes_return_persisted_resources_and_reject_other_users(ctx, api):
    form = await execute(ctx, "prepare_form", form_id="pva_pflegegeld", values=ANNA)
    escalation = await execute(
        ctx,
        "escalate",
        reason_code="medical_question",
        target_kind="health_advice",
        open_question="Frage zur Medikation klären.",
    )
    assert form.ok and escalation.ok
    draft = form.card.form_draft
    handover = escalation.card.escalation
    paths = [
        f"/api/form-drafts/{draft.id}",
        draft.pdf_url,
        f"/api/escalations/{handover.id}",
    ]
    for path in paths:
        assert (await api.get(path)).status_code == 401

    login = await api.post("/api/auth/login", json={"persona_id": "maria"})
    assert login.status_code == 200
    await ctx.db.refresh(ctx.case)
    response = await api.get(paths[0])
    assert response.status_code == 200
    assert response.json() == draft.model_dump(mode="json")
    response = await api.get(paths[1])
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert PdfReader(BytesIO(response.content)).get_fields()["Vorname"]["/V"] == "Anna"
    response = await api.get(paths[2])
    assert response.status_code == 200
    assert response.json() == handover.model_dump(mode="json")

    for path in (f"/api/form-drafts/{uuid4()}", f"/api/escalations/{uuid4()}"):
        assert (await api.get(path)).status_code == 404

    for persona_id in ("stefan", "elif"):
        login = await api.post("/api/auth/login", json={"persona_id": persona_id})
        assert login.status_code == 200
        for path in paths:
            assert (await api.get(path)).status_code == 404


async def test_missing_pdf_returns_404(ctx, api):
    result = await execute(ctx, "prepare_form", form_id="pva_pflegegeld", values=ANNA)
    assert result.ok
    draft = result.card.form_draft
    (Path(settings.upload_dir) / "form_drafts" / f"{draft.id}.pdf").unlink()
    await api.post("/api/auth/login", json={"persona_id": "maria"})
    assert (await api.get(draft.pdf_url)).status_code == 404


def test_form_draft_metadata_survives_jsonb_key_order():
    row = FormDraft(
        id=uuid4(),
        created_at=datetime.now(UTC),
        form_id="pva_pflegegeld",
        values={
            "applicant.first_name": "Anna",
            "application.type": "Zuerkennung",
            "applicant.last_name": "Berger",
        },
        missing=[{"key": "applicant.phone", "label": "Telefon", "hint": None}],
    )
    expected = to_form_draft(row).model_dump(mode="json")
    assert [field["key"] for field in expected["filled"]] == [
        "application.type", "applicant.last_name", "applicant.first_name"
    ]
    # PostgreSQL JSONB does not preserve object key order.
    row.values = dict(reversed(list(row.values.items())))
    assert to_form_draft(row).model_dump(mode="json") == expected


def test_registered_tool_descriptions_state_when_not_to_use_them():
    descriptions = {
        tool["function"]["name"]: tool["function"]["description"]
        for tool in registry.openai_tools()
    }
    for name in (
        "search_knowledge",
        "get_leistung",
        "find_office",
        "prepare_form",
        "escalate",
        "draft_email",
    ):
        assert "nicht" in descriptions[name]
