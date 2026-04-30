"""Tests for POST /users/{user_id}/sync endpoint."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from api_gateway.app import app
from auth_service.api import get_current_user
from data.database import get_db


def _make_user(user_id=None):
    user = MagicMock()
    user.id = user_id or uuid4()
    return user


def _make_db(scalar_value=None):
    """Return a mock AsyncSession where the rate-limit query returns scalar_value."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_value
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    return db


@pytest.mark.asyncio
async def test_trigger_sync_returns_202():
    user_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: _make_user(user_id)
    app.dependency_overrides[get_db] = lambda: _make_db(scalar_value=None)
    try:
        with patch("api_gateway.router._background_sync", new=AsyncMock()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(f"/users/{user_id}/sync")
        assert response.status_code == 202
        assert response.json() == {"status": "syncing"}
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_trigger_sync_returns_403_for_wrong_user():
    user_id = uuid4()
    other_user_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: _make_user(other_user_id)
    app.dependency_overrides[get_db] = lambda: _make_db()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/users/{user_id}/sync")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_trigger_sync_returns_429_when_rate_limited():
    user_id = uuid4()
    recent_ts = datetime.now(timezone.utc)
    app.dependency_overrides[get_current_user] = lambda: _make_user(user_id)
    app.dependency_overrides[get_db] = lambda: _make_db(scalar_value=recent_ts)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/users/{user_id}/sync")
        assert response.status_code == 429
        assert "too recently" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
