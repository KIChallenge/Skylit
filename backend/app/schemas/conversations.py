"""Conversation and message models from docs/contracts.md section 1."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.cards import Source
from app.schemas.cases import Case

__all__ = [
    "Conversation",
    "ConversationCreate",
    "ConversationSummary",
    "Message",
    "Source",
]


class ConversationSummary(BaseModel):
    id: UUID
    title: str
    updated_at: datetime
    open_steps: int


class Message(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    document_ids: list[UUID]
    # The card models live in app.schemas.cards; their owner types this field.
    cards: list[dict[str, Any]]
    sources: list[Source]
    escalation_id: UUID | None


class Conversation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[Message]
    case: Case


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
