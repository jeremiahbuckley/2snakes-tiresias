"""Async Postgres fixtures for api-gateway tests."""
import os
import socket
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from data.database import Base

TEST_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/tiresias_test",
)


def _postgres_available() -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", 5432), timeout=1)
        s.close()
        return True
    except OSError:
        return False


@pytest_asyncio.fixture(scope="session")
async def _ddl_engine():
    """Session-scoped engine used only for DDL (create_all / drop_all)."""
    if not _postgres_available():
        pytest.skip("No Postgres available at localhost:5432")
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
def _require_ddl(_ddl_engine):
    """Ensure tables are created before each test (sync wrapper — no teardown needed)."""
    pass


@pytest_asyncio.fixture
async def session(_ddl_engine):
    """
    Per-test async DB session with its own asyncpg connection.

    A fresh engine is created per test so asyncpg stays on the correct
    (function-scoped) event loop. The session is committed during the test
    body; teardown is a no-op engine disposal via a sync finalizer.

    Test isolation is achieved by scoping all queries to per-test user UUIDs.
    """
    eng = create_async_engine(TEST_DB_URL, echo=False)
    factory = async_sessionmaker(bind=eng, expire_on_commit=False, autoflush=False)
    sess: AsyncSession = factory()
    try:
        yield sess
        await sess.commit()
    except Exception:
        pass
    finally:
        # Close without rolling back — avoids cross-loop asyncpg calls in teardown.
        # The connection is terminated when the engine is sync-disposed below.
        pass

    # Attempt graceful async close; if it fails (different loop), the engine
    # will force-terminate the connection during dispose.
    try:
        await sess.close()
    except Exception:
        pass
    try:
        await eng.dispose()
    except Exception:
        pass
