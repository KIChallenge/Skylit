import hashlib
import math
import os
import re
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select

import app.rag.ingest as ingest_module
from app.config import settings
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.rag.ingest import (
    KB_DIR,
    OVERLAP_WORDS,
    WINDOW_WORDS,
    chunk_document,
    embedding_text,
    ingest,
    parse_front_matter,
)
from app.rag.retriever import (
    fulltext_ranking,
    reciprocal_rank_fusion,
    search,
    vector_ranking,
)


class FakeEmbedder:
    """Deterministic bag-of-words vectors: shared words give a higher cosine."""

    def __init__(self) -> None:
        self.calls = 0

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * settings.embedding_dim
        vector[0] = 0.1
        for word in re.findall(r"\w+", text.lower()):
            digest = hashlib.sha256(word.encode()).digest()
            vector[int.from_bytes(digest[:4]) % settings.embedding_dim] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector]

    async def embed(self, texts):
        self.calls += 1
        return [self._vector(text) for text in texts]

    async def embed_query(self, text):
        return self._vector(text)


def front_matter(title: str, category: str) -> str:
    return (
        "---\n"
        f"title: {title}\n"
        "source_url: https://example.at/quelle\n"
        "publisher: example.at\n"
        f"category: {category}\n"
        "bundesland: null          # oder Wien\n"
        "leistung_ids: [demo]\n"
        "retrieved: 2026-11-05\n"
        "---\n\n"
    )


KB_FILES = {
    "kosten/rezeptgebuehr.md": front_matter("Rezeptgebühr", "kosten")
    + "## Wer ist befreit?\n"
    "Die Rezeptgebührenbefreiung gilt bei niedrigem Einkommen.\n"
    "Den Antrag stellen Sie bei der Krankenkasse.\n\n"
    "## Offene Punkte\n"
    "Geheimwort Zitronenfalter prüfen.\n",
    "pflege/pflegegeld.md": front_matter("Pflegegeld", "pflege")
    + "## Wer bekommt Pflegegeld?\n"
    "Pflegegeld bekommen Menschen mit ständigem Pflegebedarf.\n\n"
    "## Wo stelle ich den Antrag?\n"
    "Den Antrag auf Pflegegeld stellen Sie bei der Pensionsversicherung.\n",
    "reha/reha.md": front_matter("Rehabilitation Spezial", "reha")
    + "## Was ist Reha?\n"
    "Die medizinische Rehabilitation hilft nach einer Operation.\n",
}


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    for name, text in KB_FILES.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


async def chunk_count(session) -> int:
    return await session.scalar(select(func.count()).select_from(KnowledgeChunk))


def test_parse_front_matter():
    meta, body = parse_front_matter(KB_FILES["kosten/rezeptgebuehr.md"])
    assert meta["title"] == "Rezeptgebühr"
    assert meta["bundesland"] is None
    assert meta["leistung_ids"] == ["demo"]
    assert body.lstrip().startswith("## Wer ist befreit?")


def test_chunking_skips_open_points_and_overlaps_long_sections():
    _, body = parse_front_matter(KB_FILES["kosten/rezeptgebuehr.md"])
    chunks = chunk_document("Rezeptgebühr", body)
    assert [chunk.heading for chunk in chunks] == ["Wer ist befreit?"]

    words = [f"wort{i}" for i in range(900)]
    long = chunk_document("Lang", "## Lang\n" + " ".join(words))
    assert len(long) == 3
    assert all(len(chunk.content.split()) <= WINDOW_WORDS for chunk in long)
    first, second = long[0].content.split(), long[1].content.split()
    assert first[-OVERLAP_WORDS:] == second[:OVERLAP_WORDS]
    assert long[-1].content.split()[-1] == "wort899"


def test_embedding_text_includes_title_and_heading():
    chunk = chunk_document("Pflegegeld", "## Antrag\nEinreichen.")[0]
    assert embedding_text("Pflegegeld", chunk) == "Pflegegeld – Antrag\nEinreichen."


async def test_ingest_is_idempotent(db_session, kb_dir, embedder):
    stats = await ingest(db_session, kb_dir, embedder=embedder)
    assert (stats.files, stats.ingested, stats.skipped) == (3, 3, 0)
    assert stats.chunks == 4
    slugs = set(await db_session.scalars(select(KnowledgeDocument.slug)))
    assert slugs == {"kosten/rezeptgebuehr", "pflege/pflegegeld", "reha/reha"}
    assert await chunk_count(db_session) == 4

    calls = embedder.calls
    stats = await ingest(db_session, kb_dir, embedder=embedder)
    assert (stats.files, stats.ingested, stats.skipped, stats.chunks) == (3, 0, 3, 0)
    assert embedder.calls == calls
    assert await chunk_count(db_session) == 4


async def test_ingest_reindexes_when_chunk_format_changes(
    db_session, kb_dir, embedder, monkeypatch
):
    await ingest(db_session, kb_dir, embedder=embedder)
    old_hashes = set(await db_session.scalars(select(KnowledgeDocument.content_hash)))
    monkeypatch.setattr(ingest_module, "CHUNK_FORMAT", "test-next-format")
    stats = await ingest(db_session, kb_dir, embedder=embedder)
    new_hashes = set(await db_session.scalars(select(KnowledgeDocument.content_hash)))
    assert stats.ingested == 3
    assert old_hashes.isdisjoint(new_hashes)


async def test_ingest_indexes_title_in_content_and_fulltext(
    db_session, kb_dir, embedder
):
    await ingest(db_session, kb_dir, embedder=embedder)
    chunks = list(await db_session.scalars(select(KnowledgeChunk)))
    assert any(
        c.content.startswith("Rehabilitation Spezial – Was ist Reha?\n") for c in chunks
    )
    assert len(await fulltext_ranking(db_session, "Spezial")) == 1


async def test_ingest_updates_changed_and_removes_deleted_files(
    db_session, kb_dir, embedder
):
    await ingest(db_session, kb_dir, embedder=embedder)
    (kb_dir / "reha/reha.md").unlink()
    path = kb_dir / "pflege/pflegegeld.md"
    path.write_text(
        front_matter("Pflegegeld", "pflege") + "## Neu\nNur ein Abschnitt.\n"
    )

    stats = await ingest(db_session, kb_dir, embedder=embedder)
    assert (stats.ingested, stats.skipped, stats.removed) == (1, 1, 1)
    headings = set(await db_session.scalars(select(KnowledgeChunk.heading)))
    assert headings == {"Wer ist befreit?", "Neu"}

    stats = await ingest(db_session, kb_dir, embedder=embedder, reset=True)
    assert (stats.ingested, stats.skipped) == (2, 0)
    assert await chunk_count(db_session) == 2


async def test_open_points_are_not_indexed(db_session, kb_dir, embedder):
    await ingest(db_session, kb_dir, embedder=embedder)
    headings = set(await db_session.scalars(select(KnowledgeChunk.heading)))
    assert "Offene Punkte" not in headings
    assert await fulltext_ranking(db_session, "Zitronenfalter") == []


async def test_fulltext_finds_exact_term(db_session, kb_dir, embedder):
    await ingest(db_session, kb_dir, embedder=embedder)
    ids = await fulltext_ranking(db_session, "Rezeptgebührenbefreiung")
    assert len(ids) == 1

    results = await search(db_session, "Rezeptgebührenbefreiung", embedder=embedder)
    top = results[0]
    assert top.slug == "kosten/rezeptgebuehr"
    assert top.heading == "Wer ist befreit?"
    assert top.source.title == "Rezeptgebühr"
    assert top.source.url == "https://example.at/quelle"
    assert top.source.publisher == "example.at"
    assert top.source.retrieved == date(2026, 11, 5)


async def test_category_filter(db_session, kb_dir, embedder):
    await ingest(db_session, kb_dir, embedder=embedder)
    results = await search(
        db_session, "Antrag stellen", category="pflege", embedder=embedder
    )
    assert results
    assert {result.slug for result in results} == {"pflege/pflegegeld"}
    empty = await search(db_session, "Antrag", category="vorsorge", embedder=embedder)
    assert empty == []


async def test_bundesland_filter_keeps_national_and_own_documents(
    db_session, kb_dir, embedder
):
    wien = kb_dir / "pflege/mobile-dienste-wien.md"
    wien.write_text(
        front_matter("Mobile Pflege Wien", "pflege").replace(
            "bundesland: null          # oder Wien", "bundesland: Wien"
        )
        + "## Wo beantrage ich mobile Pflege?\n"
        "Den Antrag auf mobile Pflege stellen Sie beim Fonds Soziales Wien.\n",
        encoding="utf-8",
    )
    await ingest(db_session, kb_dir, embedder=embedder)
    query = "Antrag Pflege stellen"

    def slugs(results):
        return {result.slug for result in results}

    everything = await search(db_session, query, top_k=10, embedder=embedder)
    assert "pflege/mobile-dienste-wien" in slugs(everything)
    vienna = await search(
        db_session, query, top_k=10, bundesland="wien", embedder=embedder
    )
    assert slugs(vienna) == slugs(everything)
    tirol = await search(
        db_session, query, top_k=10, bundesland="Tirol", embedder=embedder
    )
    assert "pflege/mobile-dienste-wien" not in slugs(tirol)
    assert "pflege/pflegegeld" in slugs(tirol)


async def test_ties_keep_a_stable_order_across_ingests(db_session, tmp_path, embedder):
    # Chunk ids are random per ingest. Equal scores must not depend on them,
    # or the replay hash of the demo changes on every fresh database.
    text = front_matter("Zwilling", "pflege") + "## Gleich\nPflegegeld Antrag.\n"
    for name in ("b/zwilling.md", "a/zwilling.md"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding="utf-8")
    await ingest(db_session, tmp_path, embedder=embedder)
    ids = select(KnowledgeChunk.id).join(KnowledgeChunk.document)
    expected = [
        await db_session.scalar(ids.where(KnowledgeDocument.slug == slug))
        for slug in ("a/zwilling", "b/zwilling")
    ]
    vector = await embedder.embed_query("Pflegegeld Antrag Zwilling")
    assert await vector_ranking(db_session, vector) == expected
    assert await fulltext_ranking(db_session, "Pflegegeld Antrag Zwilling") == expected
    results = await search(db_session, "Pflegegeld Antrag Zwilling", embedder=embedder)
    assert [result.slug for result in results] == ["a/zwilling", "b/zwilling"]


def test_reciprocal_rank_fusion():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["c", "d"]], k=60)
    scores = dict(fused)
    assert fused[0][0] == "c"
    assert set(scores) == {"a", "b", "c", "d"}
    assert scores["c"] == pytest.approx(1 / 63 + 1 / 61)
    assert scores["a"] == pytest.approx(1 / 61)
    assert scores["d"] == pytest.approx(1 / 62)


async def test_search_merges_vector_and_fulltext(db_session, kb_dir, embedder):
    await ingest(db_session, kb_dir, embedder=embedder)
    query = "Pensionsversicherung"
    vector_ids = await vector_ranking(db_session, await embedder.embed_query(query))
    text_ids = await fulltext_ranking(db_session, query)
    assert len(vector_ids) == 4
    assert len(text_ids) == 1

    results = await search(db_session, query, top_k=10, embedder=embedder)
    assert len(results) == 4
    scores = [result.score for result in results]
    assert scores == sorted(scores, reverse=True)
    # The full-text hit also ranks in the vector list, so RRF puts it first.
    assert results[0].heading == "Wo stelle ich den Antrag?"
    assert results[0].score > 1 / 61
    assert len(await search(db_session, query, top_k=2, embedder=embedder)) == 2
    assert await search(db_session, "   ", embedder=embedder) == []


@pytest.mark.slow
@pytest.mark.skipif(os.environ.get("RUN_SLOW") != "1", reason="set RUN_SLOW=1")
async def test_real_embedder_finds_pflegegeld(db_session):
    from app.rag.embedder import FastEmbedder

    embedder = FastEmbedder()
    await ingest(db_session, KB_DIR, embedder=embedder)
    results = await search(
        db_session, "Pflegegeld beantragen", top_k=3, embedder=embedder
    )
    assert any(result.slug.startswith("pflege/") for result in results)
