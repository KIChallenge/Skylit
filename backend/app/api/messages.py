"""POST /api/conversations/{id}/messages: one agent turn as an SSE stream."""

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, aclosing
from typing import Annotated
from uuid import UUID

import anyio
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import SessionLocal
from app.deps import api_error, current_user, get_db
from app.guardrails import red_flags
from app.llm.orchestrator import run_turn
from app.models import Conversation, Profile, User
from app.rag import retriever
from app.schemas.events import to_sse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["conversations"])

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


class GeoLocation(BaseModel):
    """Browser location for distance ranking. Used in this turn only, never stored."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    document_ids: list[UUID] = Field(default_factory=list)
    location: GeoLocation | None = None


def stream_sessions() -> SessionFactory:
    """The stream opens its own session: a request-scoped one may close too early."""
    return SessionLocal


async def _turn_events(
    request: Request,
    sessions: SessionFactory,
    user_id: UUID,
    conversation_id: UUID,
    body: MessageCreate,
) -> AsyncIterator[str]:
    async with sessions() as session:
        try:
            user = await session.get(
                User, user_id, options=[selectinload(User.profile)]
            )
            conversation = await session.get(Conversation, conversation_id)
            bundesland = await session.scalar(
                select(Profile.bundesland).where(Profile.user_id == user_id)
            )
            turn = run_turn(
                session,
                user,
                conversation,
                body.content,
                body.document_ids,
                location=(body.location.lat, body.location.lon)
                if body.location
                else None,
                red_flag_check=red_flags.check,
                retrieve=lambda query: retriever.search(
                    session, query, bundesland=bundesland
                ),
            )
            async with aclosing(turn) as events:
                async for event in events:
                    if await request.is_disconnected():
                        logger.info("Client disconnected, stopped the turn")
                        break
                    yield to_sse(event)
        finally:
            # A cancelled stream must still give the connection back cleanly.
            with anyio.CancelScope(shield=True):
                await session.rollback()


@router.post(
    "/conversations/{conversation_id}/messages",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def post_message(
    conversation_id: UUID,
    body: MessageCreate,
    request: Request,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    sessions: Annotated[SessionFactory, Depends(stream_sessions)],
) -> StreamingResponse:
    found = await db.scalar(
        select(Conversation.id).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    if found is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND, "not_found", "Diesen Fall gibt es nicht."
        )
    return StreamingResponse(
        _turn_events(request, sessions, user.id, conversation_id, body),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
