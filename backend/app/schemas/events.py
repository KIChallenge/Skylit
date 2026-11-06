"""SSE events of one agent turn (contracts.md §2)."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.llm.types import Usage
from app.schemas.cards import Card, Case, Contact, Escalation, Source


class MessageCreated(BaseModel):
    type: Literal["message.created"] = "message.created"
    message_id: UUID
    conversation_id: UUID


class EmergencyEvent(BaseModel):
    type: Literal["emergency"] = "emergency"
    contacts: list[Contact]
    message: str


class StatusEvent(BaseModel):
    type: Literal["status"] = "status"
    stage: Literal["retrieving", "thinking", "tool", "writing"]
    label: str


class TextDelta(BaseModel):
    type: Literal["text.delta"] = "text.delta"
    delta: str


class ToolCalled(BaseModel):
    type: Literal["tool.called"] = "tool.called"
    call_id: str
    name: str
    label: str


class ToolResult(BaseModel):
    type: Literal["tool.result"] = "tool.result"
    call_id: str
    name: str
    ok: bool
    card: Card | None = None
    error: str | None = None


class CaseUpdated(BaseModel):
    type: Literal["case.updated"] = "case.updated"
    case: Case


class EscalationEvent(BaseModel):
    type: Literal["escalation"] = "escalation"
    escalation: Escalation


class SourcesEvent(BaseModel):
    type: Literal["sources"] = "sources"
    sources: list[Source]


class MessageCompleted(BaseModel):
    type: Literal["message.completed"] = "message.completed"
    message_id: UUID
    finish_reason: str
    usage: Usage


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str
    retry_after: float | None = None


Event = Annotated[
    MessageCreated
    | EmergencyEvent
    | StatusEvent
    | TextDelta
    | ToolCalled
    | ToolResult
    | CaseUpdated
    | EscalationEvent
    | SourcesEvent
    | MessageCompleted
    | ErrorEvent,
    Field(discriminator="type"),
]


def to_sse(event: BaseModel) -> str:
    """Render one event. `type` goes on the `event:` line, not into `data`."""
    # Pydantic writes compact JSON and escapes newlines, so `data` stays on one line.
    data = event.model_dump_json(exclude={"type"})
    return f"event: {event.type}\ndata: {data}\n\n"
