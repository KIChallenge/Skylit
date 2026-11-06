"""Development and demo helpers. Production answers 404 for every route here."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import api_error, current_user, get_db
from app.models import (
    Appointment,
    Conversation,
    Document,
    Escalation,
    FormDraft,
    User,
)


def require_dev_env() -> None:
    # Read the setting per request so a changed APP_ENV takes effect at once.
    if settings.app_env not in ("development", "demo"):
        raise api_error(
            status.HTTP_404_NOT_FOUND, "not_found", "Diese Seite gibt es nicht."
        )


router = APIRouter(prefix="/dev", tags=["dev"], dependencies=[Depends(require_dev_env)])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]


@router.post(
    "/reset", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
async def reset(user: CurrentUser, db: DbSession) -> Response:
    """Wipe the current persona's demo data. Other personas keep theirs."""
    own_conversations = select(Conversation.id).where(Conversation.user_id == user.id)
    await db.execute(
        delete(Escalation).where(Escalation.conversation_id.in_(own_conversations))
    )
    for model in (FormDraft, Appointment, Document):
        await db.execute(delete(model).where(model.user_id == user.id))
    # The foreign keys cascade to messages, cases and case steps.
    await db.execute(delete(Conversation).where(Conversation.user_id == user.id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
