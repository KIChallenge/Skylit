"""CLI: markdown knowledge base → chunks → embeddings → database.

Run `python -m app.rag.ingest [--reset]`. The CLI skips files whose content
hash is unchanged.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.rag.embedder import Embedder, get_embedder

KB_DIR = Path(__file__).resolve().parents[2] / "seed" / "kb"
CHUNK_FORMAT = "3"

# Tokens are approximated by whitespace-separated words.
MAX_WORDS = 500
WINDOW_WORDS = 400
OVERLAP_WORDS = 50
SKIP_HEADINGS = {"offene punkte"}

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n(.*))?\Z", re.DOTALL)
_HEADING = re.compile(r"^##\s+(.+?)\s*$")


@dataclass
class Chunk:
    heading: str
    content: str

    @property
    def content_hash(self) -> str:
        return sha256(f"{self.heading}\n{self.content}")


@dataclass
class IngestStats:
    files: int = 0
    ingested: int = 0
    skipped: int = 0
    removed: int = 0
    chunks: int = 0

    def __str__(self) -> str:
        return (
            f"{self.files} Dateien: {self.ingested} neu oder geändert, "
            f"{self.skipped} unverändert übersprungen, {self.removed} entfernt, "
            f"{self.chunks} Chunks geschrieben"
        )


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_value(raw: str) -> str | list[str] | None:
    value = re.sub(r"\s+#.*$", "", raw).strip()
    if value in {"", "null", "~"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        items = (item.strip().strip("'\"") for item in value[1:-1].split(","))
        return [item for item in items if item]
    return value.strip("'\"")


def parse_front_matter(text: str) -> tuple[dict[str, str | list[str] | None], str]:
    match = _FRONT_MATTER.match(text.lstrip("﻿"))
    if not match:
        raise ValueError("Front matter fehlt")
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, raw = line.split(":", 1)
            meta[key.strip()] = _parse_value(raw)
    return meta, match.group(2) or ""


def split_sections(body: str, default_heading: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = [(default_heading, [])]
    for line in body.splitlines():
        if match := _HEADING.match(line):
            sections.append((match.group(1), []))
        else:
            sections[-1][1].append(line)
    return [
        (heading, "\n".join(lines).strip())
        for heading, lines in sections
        if "\n".join(lines).strip() and heading.strip().lower() not in SKIP_HEADINGS
    ]


def split_words(text: str) -> list[str]:
    words = text.split()
    if len(words) <= MAX_WORDS:
        return [text]
    step = WINDOW_WORDS - OVERLAP_WORDS
    return [
        " ".join(words[start : start + WINDOW_WORDS])
        for start in range(0, len(words) - OVERLAP_WORDS, step)
    ]


def chunk_document(title: str, body: str) -> list[Chunk]:
    return [
        Chunk(heading=heading, content=part)
        for heading, text in split_sections(body, title)
        for part in split_words(text)
    ]


def embedding_text(title: str, chunk: Chunk) -> str:
    return f"{title} – {chunk.heading}\n{chunk.content}"


def _required(meta: dict, key: str, path: Path) -> str:
    value = meta.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path}: Feld '{key}' fehlt im Front Matter")
    return value


async def ingest(
    session: AsyncSession,
    kb_dir: Path = KB_DIR,
    *,
    embedder: Embedder | None = None,
    reset: bool = False,
) -> IngestStats:
    embedder = embedder or get_embedder()
    stats = IngestStats()
    if reset:
        await session.execute(delete(KnowledgeDocument))
    existing = {
        doc.slug: doc for doc in await session.scalars(select(KnowledgeDocument))
    }

    paths = sorted(kb_dir.glob("*/*.md"))
    seen: set[str] = set()
    for path in paths:
        stats.files += 1
        slug = f"{path.parent.name}/{path.stem}"
        seen.add(slug)
        raw = path.read_text(encoding="utf-8")
        content_hash = sha256(f"{CHUNK_FORMAT}\n{raw}")
        doc = existing.get(slug)
        if doc is not None and doc.content_hash == content_hash:
            stats.skipped += 1
            continue

        meta, body = parse_front_matter(raw)
        title = _required(meta, "title", path)
        chunks = chunk_document(title, body)
        vectors = await embedder.embed([embedding_text(title, c) for c in chunks])

        if doc is None:
            doc = KnowledgeDocument(slug=slug)
            session.add(doc)
        else:
            await session.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id)
            )
        doc.title = title
        doc.source_url = _required(meta, "source_url", path)
        doc.publisher = _required(meta, "publisher", path)
        category = meta.get("category")
        doc.category = category if isinstance(category, str) else path.parent.name
        bundesland = meta.get("bundesland")
        doc.bundesland = bundesland if isinstance(bundesland, str) else None
        retrieved = meta.get("retrieved")
        doc.retrieved = (
            date.fromisoformat(retrieved) if isinstance(retrieved, str) else None
        )
        doc.content_hash = content_hash
        await session.flush()

        session.add_all(
            KnowledgeChunk(
                document_id=doc.id,
                chunk_index=index,
                heading=chunk.heading,
                content=embedding_text(title, chunk),
                embedding=vector,
                content_hash=chunk.content_hash,
            )
            for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
        )
        stats.ingested += 1
        stats.chunks += len(chunks)

    # The KB directory is the source of truth: drop documents whose file is gone.
    stale = set(existing) - seen
    if stale:
        await session.execute(
            delete(KnowledgeDocument).where(KnowledgeDocument.slug.in_(stale))
        )
        stats.removed = len(stale)
    await session.commit()
    return stats


async def _main(reset: bool, kb_dir: Path) -> None:
    from app.db import SessionLocal, engine

    try:
        async with SessionLocal() as session:
            stats = await ingest(session, kb_dir, reset=reset)
        print(stats)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Wissensbasis in die Datenbank laden")
    parser.add_argument(
        "--reset", action="store_true", help="alle Dokumente löschen und neu laden"
    )
    parser.add_argument("--kb-dir", type=Path, default=KB_DIR)
    args = parser.parse_args()
    asyncio.run(_main(args.reset, args.kb_dir))


if __name__ == "__main__":
    main()
