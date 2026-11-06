from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from alembic import command
from app.config import settings
from app.main import app


@pytest.fixture(scope="session")
def db_url() -> Iterator[str]:
    # Keep Docker optional for tests that do not request the database fixture.
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:pg16", driver=None) as postgres:
        url = (
            make_url(postgres.get_connection_url())
            .set(drivername="postgresql+asyncpg")
            .render_as_string(hide_password=False)
        )
        original_url = settings.database_url
        try:
            settings.database_url = url
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            command.upgrade(config, "head")
            yield url
        finally:
            settings.database_url = original_url


@pytest_asyncio.fixture
async def db_session(db_url: str) -> AsyncIterator[AsyncSession]:
    # Each test can commit; the outer transaction still rolls everything back.
    engine = create_async_engine(db_url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as session:
                    yield session
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
