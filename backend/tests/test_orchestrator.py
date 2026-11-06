"""Agent turn tests with LLM_PROVIDER=fake or a scripted client, no network."""

import json
from copy import deepcopy
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from pydantic import BaseModel, TypeAdapter
from sqlalchemy import select

from app.audit.log import audit
from app.config import settings
from app.llm import client as client_module
from app.llm import orchestrator
from app.llm.context import build_messages, load_system_prompt
from app.llm.orchestrator import run_turn
from app.llm.types import BaseLLMClient, LLMChunk, LLMError, Usage, parse_tool_call
from app.models import (
    AuditLog,
    Case,
    CaseStep,
    Conversation,
    Document,
    Escalation,
    Leistung,
    Message,
    Office,
    Profile,
    User,
)
from app.schemas import cards
from app.schemas.events import Event, TextDelta, to_sse
from app.tools import registry
from app.tools.registry import Tool, ToolOutput

S1_INTAKE = (
    "Meine Mutter ist gerade aus dem Spital gekommen und kommt allein nicht mehr "
    "zurecht. Was muss ich tun?"
)
S1_DOCUMENT = "Ja, sie wohnt in Wien. Hier ist der Brief."
S3_EMERGENCY = "Meine Mutter hat plötzlich starke Atemnot."
SOURCE = {
    "title": "Pflegegeld",
    "url": "https://example.test/pflegegeld",
    "publisher": "Sozialministerium",
}
CHUNK = {
    "heading": "Antrag",
    "content": "Der Antrag geht an die PVA.",
    "source": SOURCE,
}


def no_flag(text: str) -> SimpleNamespace:
    return SimpleNamespace(hit=False, contact_ids=[])


def emergency_flag(text: str) -> SimpleNamespace:
    return SimpleNamespace(hit=True, contact_ids=["rettung_144", "euronotruf_112"])


async def no_chunks(query: str) -> list[Any]:
    return []


def call(name: str, arguments: dict[str, Any], id: str = "call_1"):
    return parse_tool_call(id, name, json.dumps(arguments))


STEP_ARGUMENTS = {"title": "Pflegegeld beantragen", "category": "form"}


class ScriptedClient(BaseLLMClient):
    """Plays one scripted reply per call and records each request."""

    def __init__(self, *replies: Any) -> None:
        self.model = "scripted"
        self.replies = list(replies)
        self.requests: list[dict[str, Any]] = []

    async def stream_chat(
        self,
        messages,
        tools=None,
        tool_choice="auto",
        thinking=False,
        max_tokens=None,
        response_format=None,
    ):
        self.requests.append(
            {
                "messages": deepcopy(messages),
                "tools": tools,
                "tool_choice": tool_choice,
            }
        )
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        for item in reply if isinstance(reply, list) else [reply]:
            if isinstance(item, Exception):
                raise item
            if isinstance(item, str):
                yield LLMChunk(type="text", text=item)
        tool_calls = [
            item for item in (reply if isinstance(reply, list) else [])
            if not isinstance(item, str | Exception)
        ]
        yield LLMChunk(
            type="finish",
            finish_reason="tool_calls" if tool_calls else "stop",
            tool_calls=tool_calls,
            usage=Usage(prompt_tokens=10, completion_tokens=5, cached_tokens=2),
            model=self.model,
            request_id="req-test",
        )


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


def use_client(monkeypatch, client: ScriptedClient) -> ScriptedClient:
    monkeypatch.setattr(orchestrator, "get_llm_client", lambda: client)
    return client


async def add_user(session, persona_id: str) -> User:
    user = User(
        id=uuid4(),
        persona_id=persona_id,
        display_name="Maria Berger",
        tagline="Synthetische Persona",
        avatar_emoji="M",
    )
    session.add(user)
    await session.flush()
    session.add(
        Profile(
            id=uuid4(),
            user_id=user.id,
            language="de",
            depth="short",
            bundesland="Wien",
            postal_code="1030",
            insurer="OEGK",
        )
    )
    await session.flush()
    return user


async def add_conversation(session, user: User) -> SimpleNamespace:
    conversation = Conversation(id=uuid4(), user_id=user.id, title="Neuer Fall")
    session.add(conversation)
    await session.flush()
    case = Case(
        id=uuid4(),
        conversation_id=conversation.id,
        title="Mein Fall",
        subject="self",
        summary="",
    )
    session.add(case)
    await session.flush()
    return SimpleNamespace(conversation=conversation, case_id=case.id)


@pytest_asyncio.fixture
async def env(db_session) -> SimpleNamespace:
    user = await add_user(db_session, f"maria-{uuid4()}")
    created = await add_conversation(db_session, user)
    db_session.add(
        Leistung(
            id="pflegegeld",
            title="Pflegegeld",
            category="pflege",
            short="Beitrag zu pflegebedingten Mehraufwendungen.",
            conditions=[],
            office_kind="pension_insurer",
            form_ids=[],
            documents_needed=[],
            source_url=SOURCE["url"],
        )
    )
    await db_session.commit()
    return SimpleNamespace(
        session=db_session,
        user=user,
        user_id=user.id,
        conversation=created.conversation,
        conversation_id=created.conversation.id,
        case_id=created.case_id,
    )


async def turn(
    env: SimpleNamespace,
    content: str = S1_INTAKE,
    document_ids: list[Any] | None = None,
    red_flag_check: Any = no_flag,
    retrieve: Any = no_chunks,
) -> list[Any]:
    return [
        event
        async for event in run_turn(
            env.session,
            env.user,
            env.conversation,
            content,
            document_ids,
            red_flag_check=red_flag_check,
            retrieve=retrieve,
        )
    ]


def types(events: list[Any]) -> list[str]:
    return [event.type for event in events]


def assert_order_guarantee(events: list[Any]) -> None:
    kinds = types(events)
    assert kinds[0] == "message.created"
    assert kinds.count("message.created") == 1
    assert kinds[-1] in ("message.completed", "error")
    assert kinds.count("message.completed") + kinds.count("error") == 1


async def messages_of(env: SimpleNamespace) -> list[Message]:
    statement = (
        select(Message)
        .where(Message.conversation_id == env.conversation_id)
        .order_by(Message.created_at)
        .execution_options(populate_existing=True)
    )
    return list((await env.session.scalars(statement)).all())


async def steps_of(env: SimpleNamespace) -> list[CaseStep]:
    statement = (
        select(CaseStep)
        .where(CaseStep.case_id == env.case_id)
        .order_by(CaseStep.position)
        .execution_options(populate_existing=True)
    )
    return list((await env.session.scalars(statement)).all())


async def audits_of(env: SimpleNamespace, event_type: str) -> list[AuditLog]:
    statement = select(AuditLog).where(
        AuditLog.conversation_id == env.conversation_id,
        AuditLog.event_type == event_type,
    )
    return list((await env.session.scalars(statement)).all())


# --- Scenarios ---


async def test_s1_intake_streams_text_and_completes(env):
    events = await turn(env)

    assert_order_guarantee(events)
    kinds = types(events)
    assert kinds[-2:] == ["sources", "message.completed"]
    assert "retrieving" in [e.stage for e in events if e.type == "status"]
    text = "".join(e.delta for e in events if e.type == "text.delta")
    assert 1 <= text.count("?") <= 2

    user_message, assistant = await messages_of(env)
    assert (user_message.role, user_message.content) == ("user", S1_INTAKE)
    assert (assistant.role, assistant.content) == ("assistant", text)
    assert assistant.id == events[0].message_id == events[-1].message_id
    assert assistant.usage["model"] == "fake"
    assert await audits_of(env, "llm_call")


async def test_tool_turn_emits_case_updated_and_persists_the_step(env):
    events = await turn(env, S1_DOCUMENT)

    assert_order_guarantee(events)
    kinds = types(events)
    called = kinds.index("tool.called")
    assert kinds[called : called + 3] == ["tool.called", "tool.result", "case.updated"]
    # Text may come in several rounds, around the tool events.
    assert kinds.index("text.delta") < called < len(kinds) - 1 - kinds[::-1].index(
        "text.delta"
    )

    tool_result = next(e for e in events if e.type == "tool.result")
    assert (tool_result.name, tool_result.ok) == ("upsert_case_step", True)
    updated = next(e for e in events if e.type == "case.updated")
    assert [step.title for step in updated.case.steps] == ["Pflegegeld beantragen"]

    step = (await steps_of(env))[0]
    assert (step.title, step.leistung_id, step.status) == (
        "Pflegegeld beantragen",
        "pflegegeld",
        "open",
    )
    assistant = (await messages_of(env))[-1]
    stored = assistant.tool_calls[0]["calls"][0]
    assert stored["name"] == "upsert_case_step"
    assert stored["result"]["step"]["id"] == str(step.id)
    tool_audit = (await audits_of(env, "tool_call"))[0]
    assert tool_audit.detail["ok"] is True
    assert "leistung_id" in tool_audit.detail["argument_keys"]
    # The audit names the arguments but does not store their values.
    assert "Pflegegeld beantragen" not in json.dumps(tool_audit.detail)


async def test_emergency_comes_before_any_text(env, monkeypatch):
    client = use_client(monkeypatch, ScriptedClient(["Bitte rufen Sie 144 an."]))
    searched: list[str] = []

    async def retrieve(query: str) -> list[Any]:
        searched.append(query)
        return []

    events = await turn(
        env, S3_EMERGENCY, red_flag_check=emergency_flag, retrieve=retrieve
    )

    assert_order_guarantee(events)
    kinds = types(events)
    assert kinds[1] == "emergency"
    assert kinds.index("emergency") < kinds.index("text.delta")
    emergency = events[1]
    assert [contact.phone for contact in emergency.contacts] == ["144", "112"]
    assert "144" in emergency.message
    system = client.requests[0]["messages"][0]["content"]
    assert "## NOTFALL" in system and "144" in system
    assert searched == []
    guardrail = (await audits_of(env, "guardrail"))[0]
    assert guardrail.detail["reason_code"] == "emergency"


@pytest.mark.parametrize("language", ["de", "en"])
def test_emergency_banner_names_contacts_without_assessing(language):
    contacts = [cards.Contact(name="Rettungsdienst (Notruf)", phone="144")]
    message = orchestrator._emergency_message(contacts, language)
    assert "Rettungsdienst (Notruf) (144)" in message
    banned = ("klingt nach", "könnte", "wahrscheinlich", "sounds like", "probably")
    for phrase in banned:
        assert phrase not in message


async def test_emergency_with_unknown_contacts_shows_defaults(env, monkeypatch):
    use_client(monkeypatch, ScriptedClient(["Bitte rufen Sie 144 an."]))

    def unknown(text: str) -> SimpleNamespace:
        return SimpleNamespace(hit=True, contact_ids=["gibt_es_nicht"])

    events = await turn(env, S3_EMERGENCY, red_flag_check=unknown)

    assert [contact.phone for contact in events[1].contacts] == ["144", "112"]


async def test_emergency_survives_an_llm_failure(env, monkeypatch):
    use_client(monkeypatch, ScriptedClient(LLMError("overloaded", "Ausgelastet.")))

    events = await turn(env, S3_EMERGENCY, red_flag_check=emergency_flag)

    assert types(events)[1] == "emergency"
    assert types(events)[-1] == "error"


async def test_llm_error_ends_with_an_error_event(env, monkeypatch):
    error = LLMError("rate_limited", "Bitte warten.", retry_after=6.0, status=429)
    use_client(monkeypatch, ScriptedClient(error))

    events = await turn(env)

    assert_order_guarantee(events)
    last = events[-1]
    assert (last.type, last.code, last.message, last.retry_after) == (
        "error",
        "rate_limited",
        "Bitte warten.",
        6.0,
    )
    assert "message.completed" not in types(events)
    # Without output there is no assistant row, and the user message stays.
    assert [message.role for message in await messages_of(env)] == ["user"]
    assert (await audits_of(env, "error"))[0].detail["status"] == 429


async def test_llm_error_after_text_keeps_the_partial_answer(env, monkeypatch):
    use_client(
        monkeypatch, ScriptedClient(["Guten ", LLMError("unavailable", "Kein Dienst.")])
    )

    events = await turn(env)

    assert types(events)[-1] == "error"
    assert (await messages_of(env))[-1].content == "Guten "


async def test_llm_error_in_round_two_keeps_step_and_history(env, monkeypatch):
    client = use_client(
        monkeypatch,
        ScriptedClient(
            [call("upsert_case_step", STEP_ARGUMENTS)],
            LLMError("unavailable", "Kein Dienst."),
            ["Weiter geht es."],
        ),
    )

    events = await turn(env)
    assert types(events)[-1] == "error"
    assert len(await steps_of(env)) == 1

    await turn(env, "Noch einmal bitte.")
    roles = [message["role"] for message in client.requests[-1]["messages"]]
    assert roles == ["system", "user", "assistant", "tool", "system", "user"]


async def test_empty_reply_ends_with_an_error_event(env, monkeypatch):
    use_client(monkeypatch, ScriptedClient([]))

    events = await turn(env)

    assert events[-1].code == "empty_response"
    assert_order_guarantee(events)


async def test_unexpected_failure_ends_with_a_readable_error(env):
    def broken(text: str) -> None:
        raise RuntimeError("secret internals")

    events = await turn(env, red_flag_check=broken)

    assert_order_guarantee(events)
    assert events[-1].code == "internal_error"
    assert "secret internals" not in events[-1].message
    assert "text.delta" not in types(events)


# --- Tool loop ---


async def test_tool_loop_stops_after_max_rounds_and_forces_text(env, monkeypatch):
    arguments = {"title": "A", "subject": "parent", "summary": ""}
    client = use_client(
        monkeypatch, ScriptedClient([call("set_case_summary", arguments)])
    )

    events = await turn(env)

    assert_order_guarantee(events)
    # The stub always offers a call. The fourth request forbids it.
    choices = [request["tool_choice"] for request in client.requests]
    assert choices == ["auto", "auto", "auto", "none"]
    assert types(events).count("tool.called") == 3
    assert events[-1].code == "empty_response"


@pytest.mark.parametrize(
    "bad_call",
    [
        call("gibt_es_nicht", {}),
        call("upsert_case_step", {"title": "Ohne Kategorie"}),
        call("upsert_case_step", {**STEP_ARGUMENTS, "step_id": str(uuid4())}),
        parse_tool_call("call_1", "upsert_case_step", '{"title": '),
    ],
    ids=["unknown", "invalid", "foreign_step", "broken_json"],
)
async def test_tool_errors_go_to_the_model_and_never_crash(env, monkeypatch, bad_call):
    client = use_client(
        monkeypatch, ScriptedClient([bad_call], ["Das hat nicht geklappt."])
    )

    events = await turn(env)

    assert_order_guarantee(events)
    assert types(events)[-1] == "message.completed"
    result = next(e for e in events if e.type == "tool.result")
    assert result.ok is False
    assert result.error == "Dieser Schritt konnte nicht abgeschlossen werden."
    assert "case.updated" not in types(events)
    tool_message = client.requests[1]["messages"][-1]
    assert tool_message["role"] == "tool"
    assert "error" in json.loads(tool_message["content"])
    assert await steps_of(env) == []
    # Arguments in the history stay valid JSON, or the provider would reject them.
    arguments = client.requests[1]["messages"][-2]["tool_calls"][0]["function"]
    assert isinstance(json.loads(arguments["arguments"]), dict)


async def test_unknown_leistung_id_still_saves_the_step(env, monkeypatch):
    client = use_client(
        monkeypatch,
        ScriptedClient(
            [call("upsert_case_step", {**STEP_ARGUMENTS, "leistung_id": "erfunden"})],
            ["Erledigt."],
        ),
    )

    events = await turn(env)

    result = next(e for e in events if e.type == "tool.result")
    assert result.ok is True
    assert "case.updated" in types(events)
    [step] = await steps_of(env)
    assert step.leistung_id is None
    tool_message = client.requests[1]["messages"][-1]
    assert "erfunden" in json.loads(tool_message["content"])["note"]


def test_leistung_id_fields_list_the_catalogue_ids():
    tools = {tool["function"]["name"]: tool for tool in registry.openai_tools()}
    for name in ("upsert_case_step", "get_leistung", "find_office"):
        schema = tools[name]["function"]["parameters"]["properties"]["leistung_id"]
        assert "pflegegeld" in schema["description"], name
        assert "fahrtkostenzuschuss" in schema["description"], name


async def test_failing_handler_rolls_back_and_the_turn_goes_on(env, monkeypatch):
    summary = {"title": "Vor", "subject": "parent", "summary": ""}
    client = use_client(
        monkeypatch,
        ScriptedClient(
            [
                call("set_case_summary", summary),
                call("upsert_case_step", STEP_ARGUMENTS, id="call_2"),
            ],
            ["Fertig."],
        ),
    )
    tool = registry._tools["set_case_summary"]

    async def broken(input: Any, ctx: Any) -> Any:
        ctx.case.title = "Halb geschrieben"
        await ctx.db.flush()
        raise RuntimeError("boom")

    monkeypatch.setitem(
        registry._tools,
        "set_case_summary",
        Tool(tool.name, tool.description, tool.label, tool.input_model, broken),
    )

    events = await turn(env)

    assert [e.ok for e in events if e.type == "tool.result"] == [False, True]
    assert "boom" not in client.requests[1]["messages"][-2]["content"]
    case = await env.session.scalar(
        select(Case)
        .where(Case.id == env.case_id)
        .execution_options(populate_existing=True)
    )
    assert case.title == "Mein Fall"
    assert len(await steps_of(env)) == 1


async def run_prepared_form(env, monkeypatch, form_id, leistung_id, title, message):
    """Run a turn whose model prepares `form_id`; return the client and the events."""
    client = use_client(
        monkeypatch,
        ScriptedClient(
            [call("prepare_form", {"form_id": form_id, "values": {}})],
            ["Der Antrag ist vorbereitet."],
        ),
    )
    leistung = await env.session.get(Leistung, leistung_id)
    if leistung is None:
        records = json.loads(
            (orchestrator.SEED_DIR / "leistungen.json").read_text("utf-8")
        )
        leistung = Leistung(**next(r for r in records if r["id"] == leistung_id))
        env.session.add(leistung)
    leistung.form_ids = [form_id]
    offices = json.loads((orchestrator.SEED_DIR / "offices.json").read_text("utf-8"))
    env.session.add_all(
        Office(**{key: value for key, value in record.items() if key != "maps_url"})
        for record in offices
        if record["id"] in ("pva_landesstelle_wien", "fsw_beratungszentrum_pflege")
    )
    await env.session.commit()
    tool = registry._tools["prepare_form"]
    draft = cards.FormDraftCard(
        form_draft={
            "id": str(uuid4()),
            "form_id": form_id,
            "title": title,
            "filled": [],
            "missing": [],
            "to_be_filled_by_others": [],
            "pdf_url": "/api/form-drafts/x/pdf",
            "created_at": datetime.now(UTC).isoformat(),
        }
    )

    async def prepared(input: Any, ctx: Any) -> ToolOutput:
        return ToolOutput(result={"ok": True}, card=draft)

    monkeypatch.setitem(
        registry._tools,
        "prepare_form",
        Tool(tool.name, tool.description, tool.label, tool.input_model, prepared),
    )
    return client, await turn(env, message)


def office_ids_of(events: list[Any]) -> list[str]:
    return [
        e.card.office.id
        for e in events
        if e.type == "tool.result" and e.name == "find_office"
    ]


async def test_prepared_form_adds_office_cards_without_find_office(env, monkeypatch):
    client, events = await run_prepared_form(
        env, monkeypatch, "pva_pflegegeld", "pflegegeld",
        "Antrag auf Pflegegeld", "Bitte füll den Pflegegeldantrag aus.",
    )

    assert office_ids_of(events) == [
        "pva_landesstelle_wien", "fsw_beratungszentrum_pflege"
    ]
    stored = (await messages_of(env))[-1].cards
    assert [card["type"] for card in stored] == ["form_draft", "office", "office"]
    # The model sees only the prepare_form result, never the added office cards.
    assert "Ghegastraße" not in json.dumps(client.requests[1]["messages"])


async def test_turn_with_a_card_but_no_text_completes(env, monkeypatch):
    email = {"to_label": "Ordination", "subject": "Termin", "body": "Guten Tag."}
    use_client(monkeypatch, ScriptedClient([call("draft_email", email)], []))

    events = await turn(env, "Bitte entwerfen Sie eine E-Mail.")

    assert types(events)[-1] == "message.completed"
    assistant = (await messages_of(env))[-1]
    assert assistant.content == ""
    assert assistant.cards[0]["type"] == "email_draft"


def test_prepare_form_description_lists_every_fillable_form():
    tool = next(
        t for t in registry.openai_tools() if t["function"]["name"] == "prepare_form"
    )
    description = tool["function"]["description"]
    assert "pva_pflegegeld" in description
    assert "kur_reha" in description


async def test_reha_form_adds_the_pva_but_not_the_care_counselling(env, monkeypatch):
    _, events = await run_prepared_form(
        env, monkeypatch, "kur_reha", "rehabilitation",
        "Antrag auf Rehabilitations-, Kur- bzw. Erholungsaufenthalt",
        "Bitte füll den Reha-Antrag aus.",
    )

    assert office_ids_of(events) == ["pva_landesstelle_wien"]


async def test_repeated_step_updates_without_undoing_the_user_tick(env, monkeypatch):
    use_client(
        monkeypatch,
        ScriptedClient([call("upsert_case_step", STEP_ARGUMENTS)], ["Eingetragen."]),
    )
    await turn(env)
    step = (await steps_of(env))[0]
    step.status = "done"
    await env.session.commit()

    use_client(
        monkeypatch,
        ScriptedClient(
            [call("upsert_case_step", {**STEP_ARGUMENTS, "description": "Neu"})],
            ["Eingetragen."],
        ),
    )
    await turn(env, "Weiter.")

    steps = await steps_of(env)
    assert [(s.status, s.description) for s in steps] == [("done", "Neu")]


async def test_step_id_updates_the_status_and_new_steps_get_positions(env, monkeypatch):
    reha = {"title": "Reha", "category": "info"}
    use_client(
        monkeypatch,
        ScriptedClient(
            [
                call("upsert_case_step", STEP_ARGUMENTS),
                call("upsert_case_step", reha, id="call_2"),
            ],
            ["Eingetragen."],
        ),
    )
    await turn(env)
    first, second = await steps_of(env)
    assert (first.position, second.position) == (0, 1)

    arguments = {**STEP_ARGUMENTS, "step_id": str(first.id), "status": "in_progress"}
    use_client(
        monkeypatch,
        ScriptedClient([call("upsert_case_step", arguments)], ["Geändert."]),
    )
    events = await turn(env, "Weiter.")

    assert (await steps_of(env))[0].status == "in_progress"
    updated = next(e for e in events if e.type == "case.updated")
    assert [step.status for step in updated.case.steps] == ["in_progress", "open"]


async def test_set_case_summary_updates_the_case(env, monkeypatch):
    arguments = {"title": "Pflege Anna", "subject": "parent", "summary": "Lebt allein."}
    use_client(
        monkeypatch,
        ScriptedClient([call("set_case_summary", arguments)], ["Erledigt."]),
    )

    events = await turn(env)

    updated = next(e for e in events if e.type == "case.updated")
    assert (updated.case.title, updated.case.subject) == ("Pflege Anna", "parent")


async def test_escalation_card_emits_the_event_and_links_the_message(env, monkeypatch):
    use_client(
        monkeypatch, ScriptedClient([call("escalate_test", {})], ["Übergabe bereit."])
    )
    escalation_id = uuid4()
    contact = {"name": "Gesundheitsberatung", "phone": "1450"}
    env.session.add(
        Escalation(
            id=escalation_id,
            created_at=datetime.now(UTC),
            conversation_id=env.conversation_id,
            reason_code="medical_question",
            target=contact,
            handover_summary="Offene Frage an das behandelnde Team.",
        )
    )
    await env.session.commit()

    class EmptyInput(BaseModel):
        pass

    async def handler(input: EmptyInput, ctx: Any) -> ToolOutput:
        card = cards.EscalationCard(
            escalation=cards.Escalation(
                id=escalation_id,
                reason_code="medical_question",
                target=cards.Contact(**contact),
                handover_summary="Offene Frage an das behandelnde Team.",
                created_at=datetime.now(UTC),
            )
        )
        return ToolOutput(result={"ok": True}, card=card)

    monkeypatch.setitem(
        registry._tools,
        "escalate_test",
        Tool("escalate_test", "Test.", "Übergabe", EmptyInput, handler),
    )

    events = await turn(env)

    kinds = types(events)
    assert kinds.index("tool.result") < kinds.index("escalation")
    assistant = (await messages_of(env))[-1]
    assert assistant.escalation_id == escalation_id
    assert assistant.cards[0]["type"] == "escalation"
    row = await env.session.scalar(
        select(Escalation)
        .where(Escalation.id == escalation_id)
        .execution_options(populate_existing=True)
    )
    assert row.message_id == assistant.id


# --- Context and sources ---


SAMPLER_ARGUMENTS = {
    "step": "S_O",
    "question": "Seit wann haben Sie die Kopfschmerzen?",
    "options": ["Seit heute", "Seit einigen Tagen", "Seit Wochen", "Seit Wochen"],
}


async def test_sampler_question_ends_the_turn_with_one_card(env, monkeypatch):
    client = use_client(
        monkeypatch,
        ScriptedClient(
            ["Eine kurze Frage.", call("ask_sampler", SAMPLER_ARGUMENTS)],
            ["Diese zweite Antwort darf nie kommen."],
        ),
    )

    events = await turn(env, "Wohin mit Kopfschmerzen?")

    assert_order_guarantee(events)
    assert len(client.requests) == 1
    result = next(e for e in events if e.type == "tool.result")
    card = result.card
    assert isinstance(card, cards.SamplerQuestionCard)
    assert (card.question.step_label, card.question.position) == (
        "Beschwerde · Beginn",
        1,
    )
    assert card.question.total == 12
    # Duplicate options collapse; the describe field always has a label.
    assert card.question.options == ["Seit heute", "Seit einigen Tagen", "Seit Wochen"]
    assert card.question.free_text_label
    assistant = (await messages_of(env))[-1]
    assert assistant.content == "Eine kurze Frage."
    assert assistant.cards[0]["type"] == "sampler_question"


async def test_sampler_question_without_text_is_a_complete_turn(env, monkeypatch):
    use_client(monkeypatch, ScriptedClient([call("ask_sampler", SAMPLER_ARGUMENTS)]))

    events = await turn(env, "Wohin mit Kopfschmerzen?")

    assert types(events)[-1] == "message.completed"
    assistant = (await messages_of(env))[-1]
    assert assistant.content == ""
    assert assistant.cards[0]["question"]["step"] == "S_O"


async def test_emergency_turn_never_shows_a_sampler_question(env, monkeypatch):
    client = use_client(
        monkeypatch,
        ScriptedClient(
            [call("ask_sampler", SAMPLER_ARGUMENTS)],
            ["Rufen Sie sofort den Notruf an."],
        ),
    )

    events = await turn(
        env, "Meine Mutter hat starke Atemnot.", red_flag_check=emergency_flag
    )

    kinds = types(events)
    assert kinds.index("emergency") < kinds.index("tool.called")
    result = next(e for e in events if e.type == "tool.result")
    assert result.ok is False and result.card is None
    # The model gets the refusal and answers in text in the next round.
    assert len(client.requests) == 2
    second_request = json.dumps(client.requests[1]["messages"], ensure_ascii=False)
    assert "Notfall erkannt" in second_request
    assistant = (await messages_of(env))[-1]
    assert assistant.cards == []
    assert assistant.content == "Rufen Sie sofort den Notruf an."


async def test_sampler_rejects_a_single_option(env, monkeypatch):
    arguments = {**SAMPLER_ARGUMENTS, "options": ["Ja"]}
    client = use_client(
        monkeypatch,
        ScriptedClient([call("ask_sampler", arguments)], ["Frage ohne Karte."]),
    )

    events = await turn(env, "Wohin mit Kopfschmerzen?")

    result = next(e for e in events if e.type == "tool.result")
    assert result.ok is False
    # The error goes back to the model, and the turn continues.
    assert len(client.requests) == 2


async def test_context_order_and_stable_prefix_across_turns(env, monkeypatch):
    client = use_client(
        monkeypatch,
        ScriptedClient(
            [call("upsert_case_step", STEP_ARGUMENTS)], ["Eingetragen."], ["Gut."]
        ),
    )

    async def retrieve(query: str) -> list[Any]:
        return [CHUNK]

    await turn(env, "Erste Frage", retrieve=retrieve)
    await turn(env, "Zweite Frage", retrieve=retrieve)

    first, tool_round, second = client.requests
    prompt = load_system_prompt()
    for request in client.requests:
        assert request["messages"][0]["content"].startswith(prompt)

    messages = second["messages"]
    assert [m["role"] for m in messages] == [
        "system", "user", "assistant", "tool", "assistant", "system", "user",
    ]
    assert messages[-1] == {"role": "user", "content": "Zweite Frage"}
    assert "# Kontext für diese Antwort" in messages[-2]["content"]
    assert "Der Antrag geht an die PVA." in messages[-2]["content"]
    # The block of the first turn is not part of the history.
    assert messages[1] == {"role": "user", "content": "Erste Frage"}
    # History comes back byte-identical, which keeps the provider's prefix cache.
    assert messages[2:4] == tool_round["messages"][-2:]
    assert "- Heute:" not in prompt
    assert "Schritt step_id=" in messages[0]["content"]


async def test_retrieve_query_includes_the_last_answer(env, monkeypatch):
    use_client(monkeypatch, ScriptedClient(["Lebt sie in Wien?"]))
    queries: list[str] = []

    async def retrieve(query: str) -> list[Any]:
        queries.append(query)
        return []

    await turn(env, "Erste Frage", retrieve=retrieve)
    await turn(env, "Ja", retrieve=retrieve)

    assert queries == ["Erste Frage", "Lebt sie in Wien?\nJa"]


async def test_sources_event_lists_used_sources_once(env, monkeypatch):
    use_client(monkeypatch, ScriptedClient(["Antwort."]))

    async def retrieve(query: str) -> list[Any]:
        return [CHUNK, {**CHUNK, "heading": "Frist"}]

    events = await turn(env, retrieve=retrieve)

    sources = next(e for e in events if e.type == "sources").sources
    assert [source.url for source in sources] == [SOURCE["url"]]
    assert (await messages_of(env))[-1].sources == [{**SOURCE, "retrieved": None}]
    retrieval = (await audits_of(env, "retrieval"))[0]
    assert "Der Antrag geht" not in json.dumps(retrieval.detail)


async def test_failed_retrieval_tells_the_model_it_has_no_source(env, monkeypatch):
    client = use_client(monkeypatch, ScriptedClient(["Dazu habe ich keine Quelle."]))

    async def retrieve(query: str) -> list[Any]:
        raise RuntimeError("database gone")

    events = await turn(env, retrieve=retrieve)

    assert types(events)[-1] == "message.completed"
    assert "nichts gefunden" in client.requests[0]["messages"][-2]["content"]


async def test_documents_are_injected_only_for_their_owner(env, monkeypatch):
    client = use_client(monkeypatch, ScriptedClient(["Danke."], ["Weiter."]))
    other = await add_user(env.session, f"elif-{uuid4()}")
    extracted = {"issuer": "Klinik Test", "kind": "discharge_letter"}
    own = Document(
        id=uuid4(),
        user_id=env.user_id,
        filename="brief.pdf",
        mime_type="application/pdf",
        storage_path="brief",
        status="ready",
        extracted=extracted,
    )
    foreign = Document(
        id=uuid4(),
        user_id=other.id,
        filename="fremd.pdf",
        mime_type="application/pdf",
        storage_path="fremd",
        status="ready",
        extracted={"issuer": "Fremde Klinik"},
    )
    env.session.add_all([own, foreign])
    await env.session.commit()

    events = await turn(env, "Der Brief", [str(own.id), foreign.id, "keine-id"])
    block = client.requests[0]["messages"][-2]["content"]
    assert "Klinik Test" in block and "Fremde Klinik" not in block
    sources = next(e for e in events if e.type == "sources").sources
    assert [source.title for source in sources] == ["brief.pdf"]
    assert (await messages_of(env))[0].document_ids == [own.id]

    # The quotations card arrives before any text, without a get_document call.
    results = [e for e in events if e.type == "tool.result"]
    assert [(r.name, r.card.document_id) for r in results] == [("get_document", own.id)]
    assert types(events).index("tool.result") < types(events).index("text.delta")
    assert (await messages_of(env))[1].cards == [
        {
            "type": "document_summary",
            "document_id": str(own.id),
            "extraction": extracted,
        }
    ]

    # A later turn still knows the facts: it fills forms from them.
    await turn(env, "Füll das Formular aus.")
    assert "Klinik Test" in client.requests[1]["messages"][-2]["content"]


async def test_audit_removes_document_content(env):
    entry = await audit(
        env.session,
        "tool_call",
        "Test",
        {
            "content": "Geheimer Brieftext",
            "nested": [{"quote": "Zitat", "ok": True}],
            "long": "x" * 600,
            "id": uuid4(),
        },
        conversation_id=env.conversation_id,
    )

    assert entry.detail["content"] == "[entfernt]"
    assert entry.detail["nested"] == [{"quote": "[entfernt]", "ok": True}]
    assert len(entry.detail["long"]) < 600
    assert isinstance(entry.detail["id"], str)


# --- No database ---


def test_to_sse_renders_type_line_and_one_line_json():
    rendered = to_sse(TextDelta(delta="Zeile 1\nZeile 2 – äöü"))

    assert rendered.startswith("event: text.delta\ndata: ")
    assert rendered.endswith("\n\n")
    event_line, data_line = rendered.strip().split("\n")
    assert json.loads(data_line.removeprefix("data: ")) == {
        "delta": "Zeile 1\nZeile 2 – äöü"
    }
    assert "ä" in data_line


def test_event_union_parses_every_contract_event():
    ids = {"message_id": str(uuid4()), "conversation_id": str(uuid4())}
    contact = {"name": "Rettung", "phone": "144"}
    escalation = {
        "id": str(uuid4()),
        "reason_code": "emergency",
        "target": contact,
        "handover_summary": "",
        "created_at": "2026-11-05T10:00:00Z",
    }
    card = {"type": "escalation", "escalation": escalation}
    case = {
        "id": str(uuid4()),
        "title": "Mein Fall",
        "subject": "self",
        "summary": "",
        "steps": [],
        "updated_at": "2026-11-05T10:00:00Z",
    }
    samples = [
        {"type": "message.created", **ids},
        {"type": "emergency", "contacts": [contact], "message": "Notfall"},
        {"type": "status", "stage": "tool", "label": "Suche"},
        {"type": "text.delta", "delta": "x"},
        {"type": "tool.called", "call_id": "1", "name": "n", "label": "l"},
        {"type": "tool.result", "call_id": "1", "name": "n", "ok": True, "card": card},
        {"type": "case.updated", "case": case},
        {"type": "escalation", "escalation": escalation},
        {"type": "sources", "sources": [SOURCE]},
        {
            "type": "message.completed",
            "message_id": ids["message_id"],
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cached_tokens": 0},
        },
        {"type": "error", "code": "x", "message": "y", "retry_after": None},
    ]
    adapter = TypeAdapter(Event)

    assert [adapter.validate_python(sample).type for sample in samples] == [
        sample["type"] for sample in samples
    ]


def test_registry_exports_openai_tools_with_a_stable_order():
    exported = registry.openai_tools()
    names = [tool["function"]["name"] for tool in exported]

    assert names[:2] == ["upsert_case_step", "set_case_summary"]
    assert exported == registry.openai_tools()
    for tool in exported:
        assert tool["type"] == "function"
        assert "Nutze" in tool["function"]["description"]
        assert tool["function"]["parameters"]["type"] == "object"


def test_system_prompt_has_no_dynamic_data_or_phone_numbers():
    prompt = load_system_prompt()

    assert "Lotse" in prompt and "höchstens 2 Fragen" in prompt
    assert not any(number in prompt for number in ("144", "1450", "2026"))


def test_build_messages_without_search_or_documents_has_no_block():
    case = SimpleNamespace(title="Fall", subject="self", summary="", steps=[])

    messages = build_messages(
        profile=None, case=case, today=date(2026, 11, 5), history=[], content="Hallo"
    )

    assert [message["role"] for message in messages] == ["system", "user"]
    assert "05.11.2026" in messages[0]["content"]
