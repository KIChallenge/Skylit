"""Owner-only escalation read route, authorized through the conversation."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import api_error, current_user, get_db
from app.models import Conversation, Escalation, User
from app.schemas import cards

router = APIRouter(tags=["escalations"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]


@router.get("/escalations/{id}", response_model=cards.Escalation)
async def read_escalation(
    id: UUID, db: DbSession, user: CurrentUser
) -> cards.Escalation:
    row = await db.scalar(
        select(Escalation)
        .join(Conversation, Conversation.id == Escalation.conversation_id)
        .where(Escalation.id == id, Conversation.user_id == user.id)
    )
    if row is None:
        raise api_error(404, "not_found", "Diese Übergabe wurde nicht gefunden.")
    return cards.Escalation.model_validate(row)
