import asyncio
import sys
import threading
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.api import health
from app.config import Settings, settings
from app.rag import embedder


@pytest.fixture(autouse=True)
def unloaded_embedder(monkeypatch):
    monkeypatch.setattr(embedder, "_embedder", None)


async def test_health_without_database(client, monkeypatch):
    engine = create_async_engine(
        "postgresql+asyncpg://lotse:unused@127.0.0.1:1/lotse"
    )
    monkeypatch.setattr(health, "engine", engine)
    try:
        response = await client.get("/api/health")
    finally:
        await engine.dispose()
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "db": "down",
        "llm_provider": settings.llm_provider,
        "embedder": "not_loaded",
        "kb_chunks": 0,
    }


@pytest.mark.parametrize("kb_chunks", [0, 42])
async def test_health_with_database(client, monkeypatch, kb_chunks):
    connection = AsyncMock()
    connection.scalar.return_value = kb_chunks

    @asynccontextmanager
    async def connect():
        yield connection

    monkeypatch.setattr(health, "engine", SimpleNamespace(connect=connect))
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["db"] == "ok"
    assert response.json()["kb_chunks"] == kb_chunks
    assert response.json()["embedder"] == "not_loaded"
    connection.execute.assert_awaited_once()
    assert str(connection.execute.call_args.args[0]) == "SELECT 1"
    connection.scalar.assert_awaited_once()
    assert str(connection.scalar.call_args.args[0]) == (
        "SELECT count(*) FROM knowledge_chunks"
    )


async def test_health_chunk_count_failure(client, monkeypatch):
    connection = AsyncMock()
    connection.scalar.side_effect = RuntimeError("database unavailable")

    @asynccontextmanager
    async def connect():
        yield connection

    monkeypatch.setattr(health, "engine", SimpleNamespace(connect=connect))
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["db"] == "down"
    assert response.json()["kb_chunks"] == 0


async def test_health_database_timeout(client, monkeypatch):
    cancelled = asyncio.Event()

    @asynccontextmanager
    async def connect():
        try:
            await asyncio.sleep(30)
            yield
        finally:
            cancelled.set()

    monkeypatch.setattr(health, "engine", SimpleNamespace(connect=connect))
    response = await asyncio.wait_for(client.get("/api/health"), timeout=3)
    assert response.status_code == 200
    assert response.json()["db"] == "down"
    assert response.json()["kb_chunks"] == 0
    assert cancelled.is_set()


async def test_health_during_embedder_loading(client, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    model = SimpleNamespace()

    def load_model(*args, **kwargs):
        started.set()
        if not release.wait(timeout=5):
            raise TimeoutError("test did not release model loading")
        return model

    monkeypatch.setitem(
        sys.modules, "fastembed", SimpleNamespace(TextEmbedding=load_model)
    )
    connection = AsyncMock()
    connection.scalar.return_value = 7

    @asynccontextmanager
    async def connect():
        yield connection

    monkeypatch.setattr(health, "engine", SimpleNamespace(connect=connect))
    instance = embedder.get_embedder()
    assert embedder.get_embedder_state() == "not_loaded"
    loader = threading.Thread(target=instance._load)
    loader.start()
    try:
        assert started.wait(timeout=1)
        response = await asyncio.wait_for(client.get("/api/health"), timeout=1)
        assert response.json()["embedder"] == "loading"
        assert response.json()["kb_chunks"] == 7
    finally:
        release.set()
        loader.join(timeout=2)
    assert not loader.is_alive()

    response = await client.get("/api/health")
    assert response.json()["embedder"] == "ready"


def test_embedder_failed_loading_can_retry(monkeypatch):
    def fail_loading(*args, **kwargs):
        assert embedder.get_embedder_state() == "loading"
        raise RuntimeError("model unavailable")

    module = SimpleNamespace(TextEmbedding=fail_loading)
    monkeypatch.setitem(sys.modules, "fastembed", module)
    instance = embedder.get_embedder()
    with pytest.raises(RuntimeError, match="model unavailable"):
        instance._load()
    assert embedder.get_embedder_state() == "not_loaded"

    model = SimpleNamespace()
    monkeypatch.setattr(module, "TextEmbedding", lambda *args, **kwargs: model)
    instance._load()
    assert embedder.get_embedder_state() == "ready"


def test_embedder_state_does_not_create_model():
    assert embedder.get_embedder_state() == "not_loaded"
    assert embedder._embedder is None


async def test_cors_allows_credentials(client):
    response = await client.options(
        "/api/health",
        headers={
            "Origin": settings.backend_cors_origins[0],
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] != "*"


@pytest.mark.parametrize(
    "origins",
    [
        "https://one.example, https://two.example/",
        '["https://one.example", "https://two.example"]',
    ],
)
def test_config_parses_cors(origins):
    config = Settings(_env_file=None, backend_cors_origins=origins)
    assert config.backend_cors_origins == [
        "https://one.example", "https://two.example"
    ]


def test_config_rejects_wildcard_cors():
    with pytest.raises(ValueError, match="explicit origins"):
        Settings(_env_file=None, backend_cors_origins="*")
