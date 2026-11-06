"""GET /api/_schema/events: puts the SSE event union into OpenAPI (contracts.md)."""

from fastapi import APIRouter, Depends

from app.deps import current_user
from app.schemas.events import Event, StatusEvent

router = APIRouter(tags=["schema"])


@router.get(
    "/_schema/events",
    response_model=Event,
    dependencies=[Depends(current_user)],
    summary="SSE event types (schema only)",
)
async def event_schema() -> Event:
    """The frontend generates its event types from this response model.

    The stream itself is POST /api/conversations/{id}/messages.
    """
    return StatusEvent(stage="thinking", label="Der Lotse prüft die nächsten Schritte…")
