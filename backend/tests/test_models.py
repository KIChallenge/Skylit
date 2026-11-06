"""Exercise the real PostgreSQL migration, seeding, and retrieval storage."""

import json
import logging
import re
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import selectinload

from app.models import (
    Base,
    Conversation,
    KnowledgeChunk,
    KnowledgeDocument,
    Leistung,
    Office,
    Profile,
    Provider,
    User,
)
from app.seed import SEED_DIR, seed


async def test_migration(db_session):
    connection = await db_session.connection()
    tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
    assert set(Base.metadata.tables) == set(tables) - {"alembic_version"}
    differences = await connection.run_sync(
        lambda conn: compare_metadata(MigrationContext.configure(conn), Base.metadata)
    )
    assert differences == []
    assert await db_session.scalar(text("SELECT version_num FROM alembic_version")) == (
        "0005"
    )
    extensions = set(
        (await db_session.scalars(text("SELECT extname FROM pg_extension"))).all()
    )
    assert {"vector", "pgcrypto"} <= extensions
    indexes = dict(
        (
            await db_session.execute(
                text(
                    "SELECT indexname, indexdef FROM pg_indexes "
                    "WHERE schemaname = 'public'"
                )
            )
        ).all()
    )
    assert (
        "USING hnsw (embedding vector_cosine_ops)"
        in indexes["ix_knowledge_chunks_embedding"]
    )
    assert "USING gin (tsv)" in indexes["ix_knowledge_chunks_tsv"]
    assert "(message_id)" in indexes["ix_audit_log_message_id"]


async def _provider_count(db_session, source: str) -> int:
    return await db_session.scalar(
        select(func.count()).select_from(Provider).where(Provider.source == source)
    )


async def test_seed_personas_and_providers(db_session):
    assert await seed(db_session)
    await db_session.commit()
    db_session.expunge_all()
    assert await db_session.scalar(select(func.count()).select_from(Profile)) == 3
    assert await _provider_count(db_session, "demo") == 12
    doctors = json.loads((SEED_DIR / "vienna_doctors.json").read_text(encoding="utf-8"))
    assert await _provider_count(db_session, "wien_ogd") == len(doctors) > 7000
    users = {
        user.persona_id: user
        for user in (
            await db_session.scalars(select(User).options(selectinload(User.profile)))
        ).all()
    }
    assert set(users) == {"maria", "stefan", "elif"}
    assert users["maria"].display_name == "Maria Berger"
    assert users["maria"].profile.date_of_birth == date(1974, 6, 2)
    assert users["maria"].profile.extra["relative"]["name"] == "Anna Berger"
    assert users["stefan"].profile.insurer == "SVS"
    assert users["stefan"].profile.depth == "detailed"
    assert users["elif"].profile.language == "en"
    assert all(isinstance(user.id, UUID) and user.created_at for user in users.values())

    ids = {user.id for user in users.values()}
    assert not await seed(db_session)
    assert set((await db_session.scalars(select(User.id))).all()) == ids
    assert await _provider_count(db_session, "demo") == 12


async def test_seed_reset_clears_dependent_demo_records(db_session):
    await seed(db_session)
    original_ids = set((await db_session.scalars(select(User.id))).all())
    db_session.add(Conversation(user_id=next(iter(original_ids))))
    await db_session.commit()
    assert await seed(db_session, reset=True)
    assert await db_session.scalar(select(func.count()).select_from(User)) == 3
    assert await _provider_count(db_session, "demo") == 12
    assert await db_session.scalar(select(func.count()).select_from(Conversation)) == 0
    assert original_ids.isdisjoint((await db_session.scalars(select(User.id))).all())


async def test_seed_optional_catalogues(db_session, tmp_path, caplog):
    for filename in ("personas.json", "providers.json", "sv_register.json"):
        (tmp_path / filename).write_text(
            (SEED_DIR / filename).read_text(encoding="utf-8"), encoding="utf-8"
        )
    leistung = {
        "id": "demo-leistung",
        "title": "Demo-Leistung",
        "category": "pflege",
        "short": "Synthetisches Angebot",
        "conditions": ["Demo-Bedingung"],
        "office_kind": "demo",
        "form_ids": ["demo-form"],
        "documents_needed": ["Demo-Nachweis"],
        "source_url": "https://example.org",
    }
    office = {
        "id": "demo-office",
        "organisation": "Demo-Stelle",
        "name": "Demo-Beratung",
        "kind": "demo",
        "bundesland": "Wien",
        "address": "Demogasse 1",
        "postal_code": "1030",
        "city": "Wien",
        "phone": "+43 1 000 0099",
        "email": None,
        "url": "https://example.org",
        "hours": None,
        "lat": None,
        "lon": None,
    }
    (tmp_path / "leistungen.json").write_text(json.dumps([leistung]), encoding="utf-8")
    (tmp_path / "offices.json").write_text(json.dumps([office]), encoding="utf-8")
    await seed(db_session, seed_dir=tmp_path)
    assert (await db_session.get(Leistung, "demo-leistung")).form_ids == ["demo-form"]
    assert (await db_session.get(Office, "demo-office")).postal_code == "1030"

    (tmp_path / "leistungen.json").unlink()
    (tmp_path / "offices.json").unlink()
    with caplog.at_level(logging.INFO, logger="app.seed"):
        await seed(db_session, seed_dir=tmp_path, reset=True)
    assert "leistungen.json" in caplog.text
    assert "offices.json" in caplog.text
    assert await db_session.scalar(select(func.count()).select_from(User)) == 3


async def test_knowledge_vector_round_trip(db_session):
    document = KnowledgeDocument(
        slug="demo-pflege",
        title="Demo-Pflege",
        source_url="https://example.org",
        publisher="Demo",
        category="pflege",
        content_hash="document-hash",
    )
    chunk = KnowledgeChunk(
        document=document,
        chunk_index=0,
        heading="Pflegeberatung",
        content="Pflegeberatung unterstützt pflegende Angehörige.",
        content_hash="chunk-hash",
        embedding=[0.5] * 384,
    )
    db_session.add(chunk)
    await db_session.commit()
    chunk_id = chunk.id
    db_session.expunge_all()
    stored = await db_session.get(KnowledgeChunk, chunk_id)
    assert len(stored.embedding) == 384
    assert list(stored.embedding) == pytest.approx([0.5] * 384)
    assert (
        await db_session.scalar(
            select(KnowledgeChunk.id).where(
                KnowledgeChunk.tsv.op("@@")(
                    func.plainto_tsquery("german", "Angehörigen")
                )
            )
        )
        == chunk_id
    )
    stored.content = "Therapie hilft bei der Bewegung."
    await db_session.flush()
    assert (
        await db_session.scalar(
            select(KnowledgeChunk.id).where(
                KnowledgeChunk.tsv.op("@@")(
                    func.plainto_tsquery("german", "Angehörigen")
                )
            )
        )
        is None
    )
    distance = await db_session.scalar(
        select(KnowledgeChunk.embedding.cosine_distance([0.5] * 384)).where(
            KnowledgeChunk.id == chunk_id
        )
    )
    assert distance == pytest.approx(0, abs=1e-6)


def test_synthetic_seed_files():
    providers = json.loads((SEED_DIR / "providers.json").read_text(encoding="utf-8"))
    assert len(providers) == len({item["id"] for item in providers}) == 12
    for postal_code in ("1030", "1100", "1160"):
        assert {
            item["kind"] for item in providers if item["postal_code"] == postal_code
        } == {"gp", "care_counselling", "mobile_care", "therapy"}
    assert all(item["demo"] is True for item in providers)
    assert all(re.fullmatch(r"\+43 1 000 00\d{2}", item["phone"]) for item in providers)

    data = (Path(__file__).resolve().parents[2] / "docs/data.md").read_text(
        encoding="utf-8"
    )
    persona_example = data.split("## 5. Personas", 1)[1].split("```json", 1)[1]
    expected = json.loads(persona_example.split("```", 1)[0])
    assert (
        json.loads((SEED_DIR / "personas.json").read_text(encoding="utf-8")) == expected
    )
