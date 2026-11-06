"""The agent turn: red-flag check → context → stream → tool loop → persist."""

import inspect
import logging
import time
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import aclosing
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.log import audit
from app.config import settings
from app.llm.client import get_llm_client
from app.llm.context import (
    RetrievedChunk,
    build_messages,
    stored_call,
    tool_call_message,
    tool_result_message,
)
from app.llm.types import LLMChunk, LLMError, Messages, ToolCall, Usage
from app.models import (
    Case,
    Conversation,
    Document,
    Escalation,
    Leistung,
    Message,
    Profile,
    User,
)
from app.schemas import cards
from app.schemas.events import (
    CaseUpdated,
    EmergencyEvent,
    ErrorEvent,
    EscalationEvent,
    MessageCompleted,
    MessageCreated,
    SourcesEvent,
    StatusEvent,
    TextDelta,
    ToolCalled,
    ToolResult,
)
from app.seed import SEED_DIR, load_records
from app.tools import ToolContext, registry
from app.tools.leistung_tools import FindOfficeInput, find_office
from app.tools.registry import ToolError, ToolExecution

logger = logging.getLogger(__name__)

RedFlagCheck = Callable[[str], Any]
Retrieve = Callable[[str], Any]

# Contacts that every emergency shows, if the check names none that we know.
DEFAULT_EMERGENCY_CONTACT_IDS = ("rettung_144", "euronotruf_112")
RETRIEVAL_CONTEXT_CHARS = 500

_EMERGENCY_MESSAGES = {
    # The banner names contacts only; it never assesses the situation.
    "de": "Bei akuter Gefahr wenden Sie sich bitte sofort an: {}.",
    "en": "If there is acute danger, please contact right away: {}.",
}
_EMERGENCY_FALLBACK = {"de": "den Notruf", "en": "the emergency services"}
_INTERNAL_MESSAGE = (
    "Beim Bearbeiten Ihrer Nachricht ist ein Fehler aufgetreten. "
    "Bitte versuchen Sie es erneut."
)
_EMPTY_MESSAGE = (
    "Der Dienst hat keine Antwort geliefert. Bitte versuchen Sie es erneut."
)
_DOCUMENT_PUBLISHER = "Von Ihnen hochgeladenes Dokument"

_STATUS_RETRIEVING = StatusEvent(stage="retrieving", label="Suche passende Leistungen…")
_STATUS_THINKING = StatusEvent(
    stage="thinking", label="Der Lotse prüft die nächsten Schritte…"
)
_STATUS_WRITING = StatusEvent(stage="writing", label="Der Lotse schreibt die Antwort…")


@dataclass
class _Turn:
    """The state of one turn. It holds plain ids: a rollback expires ORM rows."""

    session: AsyncSession
    user_id: UUID
    conversation_id: UUID
    assistant_id: UUID = field(default_factory=uuid4)
    announced: bool = False
    # One entry per model reply: {text, calls: [{id, name, arguments, result}]}.
    rounds: list[dict[str, Any]] = field(default_factory=list)
    round_text: str = ""
    card_payloads: list[dict[str, Any]] = field(default_factory=list)
    document_card_ids: set[UUID] = field(default_factory=set)
    office_card_ids: set[str] = field(default_factory=set)
    # A SAMPLER question card is a complete answer, even without text.
    asked_sampler: bool = False
    sources: dict[str, cards.Source] = field(default_factory=dict)
    usage: Usage = field(default_factory=Usage)
    model: str | None = None
    escalation_id: UUID | None = None

    async def audit(
        self, event_type: Any, summary: str, detail: dict[str, Any]
    ) -> None:
        await audit(
            self.session,
            event_type,
            summary,
            detail,
            conversation_id=self.conversation_id,
            message_id=self.assistant_id,
            user_id=self.user_id,
        )

    def add_sources(self, sources: Sequence[cards.Source]) -> None:
        for source in sources:
            self.sources.setdefault(source.url, source)

    def add_usage(self, usage: Usage | None) -> None:
        if usage is None:
            return
        self.usage = Usage(
            prompt_tokens=self.usage.prompt_tokens + usage.prompt_tokens,
            completion_tokens=self.usage.completion_tokens + usage.completion_tokens,
            cached_tokens=self.usage.cached_tokens + usage.cached_tokens,
        )

    @property
    def text(self) -> str:
        return "".join(entry["text"] for entry in self.rounds) + self.round_text

    @property
    def has_output(self) -> bool:
        return bool(self.rounds or self.round_text)


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


@lru_cache
def _known_contacts() -> dict[str, cards.Contact]:
    path = SEED_DIR / "escalation_contacts.json"
    records = load_records(path, optional=True)
    return {record["id"]: cards.Contact.model_validate(record) for record in records}


def _emergency_contacts(contact_ids: Sequence[str]) -> list[cards.Contact]:
    """Resolve the contacts. A broken seed file must not stop the emergency event."""
    try:
        known = _known_contacts()
    except Exception:
        logger.exception("Could not load the escalation contacts")
        return []
    contacts = [known[item] for item in contact_ids if item in known]
    if contacts:
        return contacts
    logger.warning("Red-flag hit without a known contact: %s", contact_ids)
    return [known[item] for item in DEFAULT_EMERGENCY_CONTACT_IDS if item in known]


def _emergency_message(contacts: Sequence[cards.Contact], language: str) -> str:
    lang = "en" if language == "en" else "de"
    numbers = ", ".join(
        f"{contact.name} ({contact.phone})" for contact in contacts if contact.phone
    )
    return _EMERGENCY_MESSAGES[lang].format(numbers or _EMERGENCY_FALLBACK[lang])


def _coerce_ids(document_ids: Sequence[UUID | str] | None) -> list[UUID]:
    ids = []
    for item in document_ids or []:
        try:
            ids.append(item if isinstance(item, UUID) else UUID(str(item)))
        except ValueError:
            logger.warning("Ignored an invalid document id")
    return ids


async def _load_documents(
    session: AsyncSession, user_id: UUID, ids: Sequence[UUID]
) -> list[Document]:
    """Load documents. The owner filter stops access to documents of other users."""
    if not ids:
        return []
    statement = (
        select(Document)
        .where(Document.id.in_(ids), Document.user_id == user_id)
        .order_by(Document.created_at, Document.id)
    )
    return list((await session.scalars(statement)).all())


async def _load_history(session: AsyncSession, conversation_id: UUID) -> list[Message]:
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at, Message.id)
    )
    return list((await session.scalars(statement)).all())


async def _load_case(session: AsyncSession, conversation_id: UUID) -> Case:
    """Load the case with its steps. `populate_existing` replaces expired state."""
    statement = (
        select(Case)
        .where(Case.conversation_id == conversation_id)
        .options(selectinload(Case.steps))
        .execution_options(populate_existing=True)
    )
    case = await session.scalar(statement)
    if case is not None:
        return case
    # POST /api/conversations creates the case. This only guards older conversations.
    session.add(
        Case(
            id=uuid4(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            conversation_id=conversation_id,
        )
    )
    await session.flush()
    return await session.scalar(statement)


def _retrieval_query(content: str, history: Sequence[Message]) -> str:
    """Add the end of the last answer, because a follow-up alone says little."""
    for message in reversed(history):
        if message.role == "assistant" and message.content:
            return f"{message.content[-RETRIEVAL_CONTEXT_CHARS:]}\n{content}"
    return content


async def _retrieve(
    turn: _Turn, retrieve: Retrieve, query: str
) -> list[RetrievedChunk]:
    """Search the knowledge base. On failure the model hears that it has no source."""
    try:
        # The savepoint keeps the transaction usable if a retriever query fails.
        async with turn.session.begin_nested():
            found = await _maybe_await(retrieve(query))
        chunks = [RetrievedChunk.model_validate(chunk) for chunk in found]
    except Exception:
        logger.exception("Retrieval failed")
        await turn.audit("error", "Die Suche in der Wissensbasis schlug fehl.", {})
        return []
    await turn.audit(
        "retrieval",
        f"Wissensbasis: {len(chunks)} Auszüge gefunden.",
        {
            "chunk_count": len(chunks),
            "sources": [chunk.source.model_dump(mode="json") for chunk in chunks],
        },
    )
    return chunks


def _output_sources(execution: ToolExecution) -> list[cards.Source]:
    """Read the sources of a tool: `search_knowledge` chunks and a Leistung card."""
    sources: list[cards.Source] = []
    for chunk in execution.result.get("chunks") or []:
        if isinstance(chunk, dict) and chunk.get("source"):
            sources.append(cards.Source.model_validate(chunk["source"]))
    if isinstance(execution.card, cards.LeistungCard):
        sources.append(execution.card.leistung.source)
    return sources


def _document_source(document: Document) -> cards.Source:
    return cards.Source(
        title=document.filename,
        url=f"/api/documents/{document.id}/file",
        publisher=_DOCUMENT_PUBLISHER,
    )


async def _stream_reply(
    turn: _Turn, messages: Messages, tool_choice: str
) -> AsyncIterator[TextDelta | StatusEvent | LLMChunk]:
    """Stream one model call. The last item is the `finish` chunk."""
    started = time.perf_counter()
    finish: LLMChunk | None = None
    client = get_llm_client()
    stream = client.stream_chat(
        messages,
        tools=registry.openai_tools(),
        tool_choice=tool_choice,
        thinking=settings.llm_enable_thinking,
    )
    async with aclosing(stream) as chunks:
        async for chunk in chunks:
            if chunk.type == "text" and chunk.text:
                if not turn.round_text:
                    yield _STATUS_WRITING
                turn.round_text += chunk.text
                yield TextDelta(delta=chunk.text)
            elif chunk.type == "finish":
                finish = chunk
    if finish is None:
        raise LLMError("empty_response", _EMPTY_MESSAGE)

    turn.add_usage(finish.usage)
    turn.model = finish.model or turn.model
    usage = finish.usage or Usage()
    await turn.audit(
        "llm_call",
        f"Modellaufruf: {finish.model}",
        {
            "model": finish.model,
            "finish_reason": finish.finish_reason,
            "tool_choice": tool_choice,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "cached_tokens": usage.cached_tokens,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "request_id": finish.request_id,
            "rate_limit": finish.rate_limit,
        },
    )
    await turn.session.commit()
    yield finish


_CARE_LEISTUNGEN = frozenset(
    {"pflegegeld", "mobile_pflege_wien", "pflegeberatung", "24h_betreuung"}
)


async def _form_offices(
    turn: _Turn, form_id: str, ctx: ToolContext
) -> list[cards.OfficeCard]:
    """Offices for a prepared form: its Leistung's office, plus FSW for care in Wien.

    The demo must not depend on the model calling find_office. The cards stay out
    of the LLM context, so recorded replay fixtures still match.
    """
    leistungen = await turn.session.scalars(select(Leistung).order_by(Leistung.id))
    leistung = next((row for row in leistungen if form_id in row.form_ids), None)
    if leistung is None:
        return []
    queries = [FindOfficeInput(leistung_id=leistung.id)]
    profile = await turn.session.scalar(
        select(Profile).where(Profile.user_id == turn.user_id)
    )
    # FSW counselling helps with care, not with a Reha or Kur application.
    in_wien = profile is not None and (profile.bundesland or "").lower() == "wien"
    if in_wien and leistung.id in _CARE_LEISTUNGEN:
        queries.append(FindOfficeInput(office_kind="care_services_wien"))
    offices: list[cards.OfficeCard] = []
    for query in queries:
        try:
            output = await find_office(query, ctx)
        except ToolError:
            continue
        if isinstance(output.card, cards.OfficeCard):
            offices.append(output.card)
    return offices


async def _run_tool(
    turn: _Turn, call: ToolCall, ctx: ToolContext
) -> AsyncIterator[BaseModel | dict[str, Any]]:
    """Run one tool call and yield its events. The last item is the stored call."""
    label = registry.label(call.name)
    yield StatusEvent(stage="tool", label=label)
    yield ToolCalled(call_id=call.id, name=call.name, label=label)

    started = time.perf_counter()
    execution = await registry.execute(call, ctx)
    await turn.audit(
        "tool_call",
        label,
        {
            "name": call.name,
            "call_id": call.id,
            "ok": execution.ok,
            # The keys explain the call. The values may hold personal data.
            "argument_keys": sorted(call.arguments),
            "error": execution.result.get("error"),
            "latency_ms": round((time.perf_counter() - started) * 1000),
        },
    )
    # A failed handler rolled back its savepoint, which expires the rows it touched.
    if execution.case_changed or not execution.ok:
        ctx.case = await _load_case(turn.session, turn.conversation_id)

    card = execution.card
    # The turn already showed this document's card before the model ran.
    if (
        isinstance(card, cards.DocumentSummaryCard)
        and card.document_id in turn.document_card_ids
    ):
        card = None
    if card is not None:
        turn.card_payloads.append(card.model_dump(mode="json"))
    if isinstance(card, cards.EscalationCard):
        turn.escalation_id = card.escalation.id
    if isinstance(card, cards.OfficeCard):
        turn.office_card_ids.add(card.office.id)
    if execution.ok:
        turn.add_sources(_output_sources(execution))
    offices: list[cards.OfficeCard] = []
    if execution.ok and isinstance(card, cards.FormDraftCard):
        for office in await _form_offices(turn, card.form_draft.form_id, ctx):
            if office.office.id in turn.office_card_ids:
                continue
            turn.office_card_ids.add(office.office.id)
            turn.card_payloads.append(office.model_dump(mode="json"))
            offices.append(office)
    await turn.session.commit()

    yield ToolResult(
        call_id=call.id,
        name=call.name,
        ok=execution.ok,
        card=card,
        error=execution.error,
    )
    for office in offices:
        yield ToolResult(
            call_id=f"{call.id}-office-{office.office.id}",
            name="find_office",
            ok=True,
            card=office,
            error=None,
        )
    if execution.case_changed:
        yield CaseUpdated(case=cards.Case.model_validate(ctx.case))
    if isinstance(card, cards.EscalationCard):
        yield EscalationEvent(escalation=card.escalation)
    yield stored_call(call, execution.result)


async def _tool_loop(
    turn: _Turn, messages: Messages, ctx: ToolContext
) -> AsyncIterator[BaseModel | str]:
    """Call the model until it stops. The last item is the finish reason."""
    limit = settings.llm_max_tool_rounds
    for round_number in range(limit + 1):
        # After the last tool round the model must answer in text.
        forced = round_number == limit
        yield _STATUS_THINKING

        finish: LLMChunk | None = None
        async with aclosing(
            _stream_reply(turn, messages, "none" if forced else "auto")
        ) as replies:
            async for item in replies:
                if isinstance(item, LLMChunk):
                    finish = item
                else:
                    yield item

        calls = [] if forced else finish.tool_calls
        if not calls:
            yield finish.finish_reason or "stop"
            return

        text = turn.round_text
        stored: list[dict[str, Any]] = []
        round_ = {"text": text, "calls": stored}
        turn.rounds.append(round_)
        turn.round_text = ""
        asked = False
        for call in calls:
            async with aclosing(_run_tool(turn, call, ctx)) as events:
                async for item in events:
                    if isinstance(item, dict):
                        stored.append(item)
                    else:
                        if isinstance(item, ToolResult) and isinstance(
                            item.card, cards.SamplerQuestionCard
                        ):
                            asked = True
                        yield item
        # A SAMPLER question ends the turn: the person answers through the card.
        if asked:
            turn.asked_sampler = True
            yield "stop"
            return
        messages.append(tool_call_message(text, stored))
        messages.extend(tool_result_message(call) for call in stored)


async def _persist_assistant(turn: _Turn) -> None:
    """Store the assistant message, and link the escalation to it."""
    rounds = list(turn.rounds)
    if rounds and turn.round_text:
        rounds.append({"text": turn.round_text, "calls": []})
    usage = turn.usage.model_dump()
    turn.session.add(
        Message(
            id=turn.assistant_id,
            created_at=datetime.now(UTC),
            conversation_id=turn.conversation_id,
            role="assistant",
            content=turn.text,
            document_ids=[],
            cards=turn.card_payloads,
            sources=[
                source.model_dump(mode="json") for source in turn.sources.values()
            ],
            tool_calls=rounds,
            escalation_id=turn.escalation_id,
            usage={**usage, "model": turn.model},
        )
    )
    await turn.session.flush()
    if turn.escalation_id is not None:
        await turn.session.execute(
            update(Escalation)
            .where(Escalation.id == turn.escalation_id)
            .values(message_id=turn.assistant_id)
        )
    await _touch_conversation(turn)


async def _touch_conversation(turn: _Turn) -> None:
    await turn.session.execute(
        update(Conversation)
        .where(Conversation.id == turn.conversation_id)
        .values(updated_at=datetime.now(UTC))
    )


async def _run(
    turn: _Turn,
    content: str,
    document_ids: Sequence[UUID | str] | None,
    red_flag_check: RedFlagCheck,
    retrieve: Retrieve,
    user: User,
    conversation: Conversation,
    location: tuple[float, float] | None = None,
) -> AsyncIterator[BaseModel]:
    session = turn.session
    history = await _load_history(session, turn.conversation_id)
    attached = await _load_documents(session, turn.user_id, _coerce_ids(document_ids))
    profile = await session.scalar(
        select(Profile).where(Profile.user_id == turn.user_id)
    )

    # An explicit timestamp keeps the order inside one database transaction too.
    session.add(
        Message(
            id=uuid4(),
            created_at=datetime.now(UTC),
            conversation_id=turn.conversation_id,
            role="user",
            content=content,
            document_ids=[document.id for document in attached],
        )
    )
    await _touch_conversation(turn)
    await session.commit()
    turn.announced = True
    yield MessageCreated(
        message_id=turn.assistant_id, conversation_id=turn.conversation_id
    )

    flag = await _maybe_await(red_flag_check(content))
    contacts: list[cards.Contact] | None = None
    if flag.hit:
        contact_ids = list(flag.contact_ids or [])
        contacts = _emergency_contacts(contact_ids)
        language = profile.language if profile else "de"
        # The event comes first: a failed audit write must not hide the banner.
        yield EmergencyEvent(
            contacts=contacts, message=_emergency_message(contacts, language)
        )
        await turn.audit(
            "guardrail",
            "Der Red-Flag-Check hat einen Notfall erkannt.",
            {
                "reason_code": getattr(flag, "reason_code", None) or "emergency",
                "contact_ids": contact_ids,
            },
        )

    # The quotations card must not depend on the model calling get_document.
    # It stays out of the LLM context, so recorded replay fixtures still match.
    if contacts is None:
        for document in attached:
            if document.status != "ready" or document.extracted is None:
                continue
            card = cards.DocumentSummaryCard(
                document_id=document.id, extraction=document.extracted
            )
            turn.card_payloads.append(card.model_dump(mode="json"))
            turn.document_card_ids.add(document.id)
            yield ToolResult(
                call_id=f"document-{document.id}",
                name="get_document",
                ok=True,
                card=card,
                error=None,
            )

    # An emergency answer discusses no Leistung, so it needs no search and no source.
    chunks: list[RetrievedChunk] | None = None
    if contacts is None:
        yield _STATUS_RETRIEVING
        query = _retrieval_query(content, history)
        chunks = await _retrieve(turn, retrieve, query)
        turn.add_sources([_document_source(document) for document in attached])
        turn.add_sources([chunk.source for chunk in chunks])

    # Facts of earlier uploads stay available: later turns fill forms from them.
    earlier_ids = [item for message in history for item in (message.document_ids or [])]
    known = {document.id for document in attached}
    earlier = await _load_documents(
        session, turn.user_id, [item for item in earlier_ids if item not in known]
    )

    case = await _load_case(session, turn.conversation_id)
    messages = build_messages(
        profile=profile,
        case=case,
        today=date.today(),
        history=history,
        content=content,
        chunks=chunks,
        documents=[*earlier, *attached],
        emergency_contacts=contacts,
    )
    # No transaction stays open during the long LLM stream.
    await session.commit()

    ctx = ToolContext(
        db=session,
        user=user,
        conversation=conversation,
        case=case,
        audit=turn.audit,
        emergency=contacts is not None,
        location=location,
    )
    finish_reason = "stop"
    async with aclosing(_tool_loop(turn, messages, ctx)) as items:
        async for item in items:
            if isinstance(item, str):
                finish_reason = item
            else:
                yield item

    # A card (form, SAMPLER question, …) is a complete answer even without text.
    if not turn.text and not turn.asked_sampler and not turn.card_payloads:
        raise LLMError("empty_response", _EMPTY_MESSAGE)

    await _persist_assistant(turn)
    await session.commit()
    yield SourcesEvent(sources=list(turn.sources.values()))
    yield MessageCompleted(
        message_id=turn.assistant_id, finish_reason=finish_reason, usage=turn.usage
    )


async def _record_failure(turn: _Turn, code: str, status: int | None) -> None:
    """Keep what the user already saw, and audit the failure."""
    if turn.has_output:
        await _persist_assistant(turn)
    await turn.audit(
        "error",
        "Die Antwort endete mit einem Fehler.",
        {"code": code, "status": status},
    )
    await turn.session.commit()


async def run_turn(
    session: AsyncSession,
    user: User,
    conversation: Conversation,
    content: str,
    document_ids: Sequence[UUID | str] | None,
    *,
    red_flag_check: RedFlagCheck,
    retrieve: Retrieve,
    location: tuple[float, float] | None = None,
) -> AsyncIterator[BaseModel]:
    """Run one turn and yield its events (contracts.md §2).

    `message.created` comes first. Exactly one of `message.completed` and `error`
    comes last. `message_id` in the events is the id of the assistant message.

    The function never raises for a failed turn, except for a cancelled request.
    """
    turn = _Turn(session=session, user_id=user.id, conversation_id=conversation.id)
    try:
        run = _run(
            turn,
            content,
            document_ids,
            red_flag_check,
            retrieve,
            user,
            conversation,
            location,
        )
        async with aclosing(run) as events:
            async for event in events:
                yield event
        return
    except LLMError as exc:
        logger.warning("Turn failed: code=%s status=%s", exc.code, exc.status)
        failure = ErrorEvent(
            code=exc.code, message=exc.message, retry_after=exc.retry_after
        )
        status = exc.status
    except Exception:
        logger.exception("Turn failed with an internal error")
        failure = ErrorEvent(code="internal_error", message=_INTERNAL_MESSAGE)
        status = None
        await _safe_rollback(session)

    try:
        await _record_failure(turn, failure.code, status)
    except Exception:
        logger.exception("Could not record the failed turn")
        await _safe_rollback(session)

    if not turn.announced:
        yield MessageCreated(
            message_id=turn.assistant_id, conversation_id=turn.conversation_id
        )
    yield failure


async def _safe_rollback(session: AsyncSession) -> None:
    try:
        await session.rollback()
    except Exception:
        logger.exception("Rollback failed")
