"""
Integration test fixtures.

Connects to a local Postgres instance and creates a dedicated
`tiresias_test` database (automatically, if it doesn't already exist).
Tables are created at session start via SQLAlchemy metadata and dropped
at session end. Each test gets a fresh session that is rolled back after
the test completes, so tests are fully isolated.

Requires a running Postgres instance:
  podman compose up -d db        # starts Postgres on localhost:5432
"""

import os

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Must be set before data.database is imported (it reads DATABASE_URL at module level)
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/tiresias_test",
)

from data.database import Base  # noqa: E402
from data.models import User, Market, MarketOutcome, Prediction, UserScore  # noqa: F401,E402

_TEST_DB_URL = os.environ["DATABASE_URL"]
_ADMIN_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine():
    """
    Session-scoped engine. Creates the tiresias_test database if absent,
    builds the full schema, yields the engine, then tears the schema down.
    """
    # Ensure the test database exists
    admin_engine = create_async_engine(_ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = 'tiresias_test'")
        )
        if not exists:
            await conn.execute(text("CREATE DATABASE tiresias_test"))
    await admin_engine.dispose()

    # Create schema
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Tear down schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def db(db_engine):
    """
    Function-scoped session. Every test gets a clean session; any writes
    are rolled back after the test so tests don't bleed into each other.
    """
    factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session
        await session.rollback()
