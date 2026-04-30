"""Unit tests for sync_one_user sync status writing."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from scheduler.sync import sync_one_user


def _make_account(platform: str = "kalshi", user_id=None) -> MagicMock:
    acct = MagicMock()
    acct.platform = platform
    acct.user_id = user_id or uuid4()
    acct.is_enabled = True
    acct.is_verified = True
    acct.last_synced_at = None
    acct.last_sync_error = None
    return acct


def _make_db(accounts: list) -> AsyncMock:
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = accounts
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    return db


@pytest.mark.asyncio
async def test_sync_one_user_sets_last_synced_at_on_success():
    user_id = uuid4()
    account = _make_account("kalshi", user_id)
    db = _make_db([account])

    with patch("scheduler.sync._sync_kalshi", new=AsyncMock(return_value=3)):
        total = await sync_one_user(db, user_id)

    assert account.last_synced_at is not None
    assert account.last_sync_error is None
    assert total == 3


@pytest.mark.asyncio
async def test_sync_one_user_sets_last_sync_error_on_failure():
    user_id = uuid4()
    account = _make_account("manifold", user_id)
    db = _make_db([account])

    with patch("scheduler.sync._sync_manifold", new=AsyncMock(side_effect=RuntimeError("API timeout"))):
        total = await sync_one_user(db, user_id)

    assert account.last_synced_at is not None
    assert account.last_sync_error == "API timeout"
    assert total == 0


@pytest.mark.asyncio
async def test_sync_one_user_partial_success():
    """One platform succeeds, one fails — both get last_synced_at set."""
    user_id = uuid4()
    kalshi_account = _make_account("kalshi", user_id)
    manifold_account = _make_account("manifold", user_id)
    db = _make_db([kalshi_account, manifold_account])

    with patch("scheduler.sync._sync_kalshi", new=AsyncMock(return_value=5)), \
         patch("scheduler.sync._sync_manifold", new=AsyncMock(side_effect=RuntimeError("timeout"))):
        total = await sync_one_user(db, user_id)

    assert kalshi_account.last_synced_at is not None
    assert kalshi_account.last_sync_error is None
    assert manifold_account.last_synced_at is not None
    assert manifold_account.last_sync_error == "timeout"
    assert total == 5
