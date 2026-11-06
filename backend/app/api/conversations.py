"""Conversations, their case and case steps. The message stream has its own router."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import api_error, current_user, get_db
from app.models import User
from app.schemas.cases import Case, CaseStep, CaseStepUpdate
from app.schemas.conversations import (
    Conversation,
    ConversationCreate,
    ConversationSummary,
)
from app.services import case_service, conversation_service

router = APIRouter(tags=["conversations"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]


def _conversation_not_found() -> HTTPException:
    return api_error(
        status.HTTP_404_NOT_FOUND, "not_found", "Dieses Gespräch gibt es nicht."
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    user: CurrentUser, db: DbSession
) -> list[ConversationSummary]:
    return await conversation_service.list_conversations(db, user)


@router.post(
    "/conversations",
    response_model=Conversation,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    user: CurrentUser, db: DbSession, body: ConversationCreate | None = None
) -> Conversation:
    title = body.title if body else None
    conversation = await conversation_service.create_conversation(db, user, title)
    return Conversation.model_validate(conversation)


@router.get("/conversations/{conversation_id}", response_model=Conversation)
async def read_conversation(
    conversation_id: UUID, user: CurrentUser, db: DbSession
) -> Conversation:
    conversation = await conversation_service.get_conversation(
        db, user, conversation_id
    )
    if conversation is None:
        raise _conversation_not_found()
    return Conversation.model_validate(conversation)


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_conversation(
    conversation_id: UUID, user: CurrentUser, db: DbSession
) -> Response:
    if not await conversation_service.delete_conversation(db, user, conversation_id):
        raise _conversation_not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/conversations/{conversation_id}/case", response_model=Case)
async def read_case(conversation_id: UUID, user: CurrentUser, db: DbSession) -> Case:
    case = await case_service.get_case(db, user, conversation_id)
    if case is None:
        raise _conversation_not_found()
    return Case.model_validate(case)


@router.patch("/case-steps/{step_id}", response_model=CaseStep)
async def update_case_step(
    step_id: UUID, body: CaseStepUpdate, user: CurrentUser, db: DbSession
) -> CaseStep:
    step = await case_service.update_step_status(db, user, step_id, body.status)
    if step is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND, "not_found", "Diesen Schritt gibt es nicht."
        )
    return CaseStep.model_validate(step)
