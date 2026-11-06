"""Response models for message audit and transparency."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.audit.log import AuditEventType
from app.schemas.cards import Contact, Source


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    event_type: AuditEventType
    summary: str
    detail: dict[str, Any]


class ToolInfo(BaseModel):
    name: str
    label: str
    ok: bool


class RetrievalChunk(BaseModel):
    slug: str
    heading: str
    score: float


class RetrievalInfo(BaseModel):
    query: str | None = None
    chunks: list[RetrievalChunk] = []


class GuardrailInfo(BaseModel):
    code: str
    summary: str


class EscalationInfo(BaseModel):
    reason_code: str
    target: Contact


class Confidence(BaseModel):
    level: Literal["hoch", "mittel", "niedrig"]
    reason: str


class MessageTransparency(BaseModel):
    message_id: UUID
    model: str | None
    provider: str | None
    sources: list[Source]
    tools: list[ToolInfo]
    retrieval: RetrievalInfo
    guardrails: list[GuardrailInfo]
    escalation: EscalationInfo | None
    confidence: Confidence
    entries: list[AuditEntry]
