"""Liveness and backing-service status without startup dependencies."""

import asyncio
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.rag.embedder import EmbedderState, get_embedder_state

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    db: Literal["ok", "down"]
    llm_provider: Literal["eustella", "azure", "fake", "replay"]
    embedder: EmbedderState = "not_loaded"
    kb_chunks: int = 0


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    db_status: Literal["ok", "down"] = "down"
    kb_chunks = 0
    try:
        async with asyncio.timeout(2):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
                kb_chunks = await connection.scalar(
                    text("SELECT count(*) FROM knowledge_chunks")
                )
        db_status = "ok"
    except Exception:
        # Health stays available when the database fails or times out.
        kb_chunks = 0
    return HealthResponse(
        db=db_status,
        llm_provider=settings.llm_provider,
        embedder=get_embedder_state(),
        kb_chunks=kb_chunks,
    )
