"""Owner-only audit and transparency routes for assistant messages."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.log import _scrub
from app.deps import api_error, current_user, get_db
from app.models import AuditLog, Conversation, Escalation, Message, User
from app.schemas.audit import (
    AuditEntry,
    Confidence,
    EscalationInfo,
    GuardrailInfo,
    MessageTransparency,
    RetrievalInfo,
    ToolInfo,
)
from app.schemas.cards import Source

router = APIRouter(tags=["transparency"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]

# Only expose metadata that the audit writer records. Unknown fields can contain text.
_DETAIL_KEYS = {
    "llm_call": {
        "model",
        "provider",
        "finish_reason",
        "tool_choice",
        "prompt_tokens",
        "completion_tokens",
        "cached_tokens",
        "latency_ms",
        "request_id",
        "rate_limit",
    },
    "tool_call": {"name", "call_id", "ok", "argument_keys", "error", "latency_ms"},
    "retrieval": {"chunk_count", "sources"},
    "guardrail": {"reason_code", "contact_ids"},
    "escalation": {"escalation_id", "reason_code"},
    "error": {"code", "status"},
}


async def _load(
    id: UUID, db: AsyncSession, user: User
) -> tuple[Message, list[AuditEntry]]:
    message = await db.scalar(
        select(Message)
        .join(Conversation)
        .where(
            Message.id == id,
            Message.role == "assistant",
            Conversation.user_id == user.id,
        )
    )
    if message is None:
        raise api_error(404, "not_found", "Diese Nachricht wurde nicht gefunden.")
    rows = (
        await db.scalars(
            select(AuditLog)
            .where(AuditLog.message_id == id)
            .order_by(AuditLog.created_at, AuditLog.id)
        )
    ).all()
    entries = [
        AuditEntry(
            id=row.id,
            created_at=row.created_at,
            event_type=row.event_type,
            summary=row.summary,
            detail={
                key: _scrub(value)
                for key, value in (row.detail or {}).items()
                if key in _DETAIL_KEYS.get(row.event_type, set())
            },
        )
        for row in rows
    ]
    return message, entries


def _confidence(
    sources: list[Source], tools: list[ToolInfo], reason: str | None
) -> Confidence:
    """Use niedrig without sources or for no_source.

    Use mittel for one source or a failed tool; use hoch otherwise.
    """
    if not sources or reason == "no_source":
        return Confidence(
            level="niedrig",
            reason="Es fehlt eine ausreichende Quelle für diese Antwort.",
        )
    if len(sources) == 1 or any(not tool.ok for tool in tools):
        return Confidence(
            level="mittel",
            reason="Es liegt nur eine Quelle vor oder ein Werkzeug ist fehlgeschlagen.",
        )
    return Confidence(
        level="hoch",
        reason="Mehrere Quellen liegen vor und alle Werkzeuge waren erfolgreich.",
    )


@router.get("/messages/{id}/audit", response_model=list[AuditEntry])
async def read_audit(id: UUID, db: DbSession, user: CurrentUser) -> list[AuditEntry]:
    _, entries = await _load(id, db, user)
    return entries


@router.get("/messages/{id}/transparency", response_model=MessageTransparency)
async def read_transparency(
    id: UUID, db: DbSession, user: CurrentUser
) -> MessageTransparency:
    message, entries = await _load(id, db, user)
    sources = [Source.model_validate(source) for source in (message.sources or [])]
    tools = [
        ToolInfo(name=e.detail["name"], label=e.summary, ok=e.detail["ok"])
        for e in entries
        if e.event_type == "tool_call"
        and isinstance(e.detail.get("name"), str)
        and isinstance(e.detail.get("ok"), bool)
    ]
    guardrails = [
        GuardrailInfo(
            code=str(e.detail.get("reason_code") or "unknown"), summary=e.summary
        )
        for e in entries
        if e.event_type == "guardrail"
    ]
    calls = [e.detail for e in entries if e.event_type == "llm_call"]
    last_call: dict[str, Any] = calls[-1] if calls else {}
    escalation_row = (
        await db.scalar(
            select(Escalation).where(
                Escalation.id == message.escalation_id,
                Escalation.conversation_id == message.conversation_id,
            )
        )
        if message.escalation_id
        else None
    )
    escalation = (
        EscalationInfo(
            reason_code=escalation_row.reason_code, target=escalation_row.target
        )
        if escalation_row
        else None
    )
    escalation_reason = escalation.reason_code if escalation else None
    if any(
        e.event_type == "escalation" and e.detail.get("reason_code") == "no_source"
        for e in entries
    ):
        escalation_reason = "no_source"
    return MessageTransparency(
        message_id=id,
        model=last_call.get("model") or (message.usage or {}).get("model"),
        provider=last_call.get("provider"),
        sources=sources,
        tools=tools,
        retrieval=RetrievalInfo(),
        guardrails=guardrails,
        escalation=escalation,
        confidence=_confidence(sources, tools, escalation_reason),
        entries=entries,
    )
