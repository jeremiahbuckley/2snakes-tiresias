"""
Integration test fixtures.

Integration tests may spin up a real (test) database and call across
service boundaries. They should NOT call external APIs — use fixtures or
a local stub server instead.

Setup:
  - Requires a running PostgreSQL instance (see docker-compose.test.yml, TODO)
  - Set DATABASE_URL env var to point at the test DB
"""

import os
import pytest
import pytest_asyncio

# Ensure tests use a separate test database
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/tiresias_test",
)


# TODO: add fixture to create/drop tables before/after test session
# @pytest_asyncio.fixture(scope="session")
# async def db_engine():
#     from data.database import engine, Base
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
#     yield engine
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.drop_all)
