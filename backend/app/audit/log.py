"""Write audit events. The log holds ids and summaries, never document content."""

import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog

AuditEventType = Literal[
    "llm_call", "tool_call", "retrieval", "guardrail", "escalation", "error"
]

# These keys carry document text, chunk text or form values in our payloads.
_CONTENT_KEYS = frozenset(
    {
        "arguments",
        "chunks",
        "content",
        "document_text",
        "extracted",
        "extraction",
        "messages",
        "quote",
        "raw_arguments",
        "raw_text",
        "text",
        "values",
    }
)
_MAX_STRING_CHARS = 500
_REMOVED = "[entfernt]"
_SHORTENED = " [gekürzt]"


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _REMOVED if key in _CONTENT_KEYS else _scrub(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, str) and len(value) > _MAX_STRING_CHARS:
        return value[:_MAX_STRING_CHARS] + _SHORTENED
    return value


async def audit(
    session: AsyncSession,
    event_type: AuditEventType,
    summary: str,
    detail: dict[str, Any],
    *,
    conversation_id: UUID | None = None,
    message_id: UUID | None = None,
    user_id: UUID | None = None,
) -> AuditLog:
    """Add one audit row and flush it. The caller commits.

    The function removes content keys and shortens long strings in `detail`.
    A wrong caller therefore cannot store a raw document.
    """
    entry = AuditLog(
        id=uuid4(),
        created_at=datetime.now(UTC),
        conversation_id=conversation_id,
        message_id=message_id,
        user_id=user_id,
        event_type=event_type,
        summary=summary,
        detail=_scrub(json.loads(json.dumps(detail, default=str))),
    )
    session.add(entry)
    await session.flush()
    return entry
