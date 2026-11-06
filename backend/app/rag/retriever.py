"""Hybrid knowledge search: pgvector cosine + German full-text, merged by RRF."""

from __future__ import annotations

import re
from collections.abc import Hashable, Sequence
from datetime import date
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Select, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.rag.embedder import Embedder, get_embedder

CANDIDATES = 20
RRF_K = 60


class ChunkSource(BaseModel):
    title: str
    url: str
    publisher: str
    retrieved: date | None = None


class RetrievedChunk(BaseModel):
    slug: str
    heading: str
    content: str
    score: float
    source: ChunkSource


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[Hashable]], k: int = RRF_K
) -> list[tuple[Hashable, float]]:
    """Score each id by sum(1 / (k + rank)) over all rankings, rank starting at 1."""
    scores: dict[Hashable, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)


# Same content, same order: chunk ids change with every fresh ingest.
_STABLE_ORDER = (KnowledgeDocument.slug, KnowledgeChunk.chunk_index)


def _base_query(category: str | None, bundesland: str | None = None) -> Select:
    query = select(KnowledgeChunk.id).join(KnowledgeChunk.document)
    if category:
        query = query.where(KnowledgeDocument.category == category)
    if bundesland:
        # National documents have no Bundesland and apply everywhere.
        query = query.where(
            or_(
                KnowledgeDocument.bundesland.is_(None),
                func.lower(KnowledgeDocument.bundesland) == bundesland.lower(),
            )
        )
    return query


async def vector_ranking(
    session: AsyncSession,
    vector: list[float],
    category: str | None = None,
    bundesland: str | None = None,
) -> list[UUID]:
    distance = KnowledgeChunk.embedding.cosine_distance(vector)
    # The tie-breaker keeps the order stable across fresh ingests (chunk ids are
    # random), so replay hashes match. It also makes pgvector search exactly
    # instead of through the approximate HNSW index; the KB is small enough.
    query = (
        _base_query(category, bundesland)
        .order_by(distance, *_STABLE_ORDER)
        .limit(CANDIDATES)
    )
    return list(await session.scalars(query))


def any_word_query(text: str) -> str:
    """Join the words with OR: an AND query matches almost no natural question."""
    return " or ".join(re.findall(r"\w+", text))


async def fulltext_ranking(
    session: AsyncSession,
    text: str,
    category: str | None = None,
    bundesland: str | None = None,
) -> list[UUID]:
    # Inline the regconfig so asyncpg never has to encode a regconfig parameter.
    tsquery = func.websearch_to_tsquery(
        literal_column("'german'::regconfig"), any_word_query(text)
    )
    rank = func.ts_rank_cd(KnowledgeChunk.tsv, tsquery)
    query = (
        _base_query(category, bundesland)
        .where(KnowledgeChunk.tsv.op("@@")(tsquery))
        .order_by(rank.desc(), *_STABLE_ORDER)
        .limit(CANDIDATES)
    )
    return list(await session.scalars(query))


async def search(
    session: AsyncSession,
    query: str,
    *,
    top_k: int = settings.rag_top_k,
    category: str | None = None,
    bundesland: str | None = None,
    embedder: Embedder | None = None,
) -> list[RetrievedChunk]:
    """Search the KB. A Bundesland keeps national documents and its own ones."""
    query = query.strip()
    if not query:
        return []
    embedder = embedder or get_embedder()
    vector = await embedder.embed_query(query)
    fused = reciprocal_rank_fusion(
        [
            await vector_ranking(session, vector, category, bundesland),
            await fulltext_ranking(session, query, category, bundesland),
        ]
    )[:top_k]
    if not fused:
        return []

    rows = await session.execute(
        select(
            KnowledgeChunk.id,
            KnowledgeChunk.heading,
            KnowledgeChunk.content,
            KnowledgeDocument.slug,
            KnowledgeDocument.title,
            KnowledgeDocument.source_url,
            KnowledgeDocument.publisher,
            KnowledgeDocument.retrieved,
        )
        .join(KnowledgeChunk.document)
        .where(KnowledgeChunk.id.in_([chunk_id for chunk_id, _ in fused]))
    )
    by_id = {row.id: row for row in rows}
    results = []
    for chunk_id, score in fused:
        row = by_id[chunk_id]
        source = ChunkSource(
            title=row.title,
            url=row.source_url,
            publisher=row.publisher,
            retrieved=row.retrieved,
        )
        results.append(
            RetrievedChunk(
                slug=row.slug,
                heading=row.heading,
                content=row.content,
                score=score,
                source=source,
            )
        )
    return results
