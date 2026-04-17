"""
Tests for the /auth/notifications/unsubscribe endpoint.

Focus: the ``_apply_unsubscribe`` helper, which does all the real work
(token decode → preference flip → commit). The GET/POST handlers are
thin wrappers around it and share all its behaviour.

We mock the SQLAlchemy session to avoid needing a live Postgres and to
keep these tests hermetic.
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from auth_service.api import _apply_unsubscribe
from notification_service import config, unsubscribe


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(existing_prefs: MagicMock | None) -> MagicMock:
    """
    Build an AsyncSession-shaped mock.

    ``existing_prefs``:
      - a MagicMock → _apply_unsubscribe finds a prefs row and updates it
      - None         → _apply_unsubscribe creates a new prefs row
    """
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=existing_prefs)
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _make_prefs(
    email_on_resolution: bool = True,
    email_on_badge: bool = True,
    email_on_rank_change: bool = True,
) -> MagicMock:
    """Lightweight stand-in for a NotificationPreferences ORM row."""
    prefs = MagicMock()
    prefs.email_on_resolution = email_on_resolution
    prefs.email_on_badge = email_on_badge
    prefs.email_on_rank_change = email_on_rank_change
    return prefs


# ---------------------------------------------------------------------------
# Happy paths — one per preference field
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "event_type,pref_field",
    [
        ("market_resolved", "email_on_resolution"),
        ("badge_earned", "email_on_badge"),
        ("rank_change", "email_on_rank_change"),
    ],
)
async def test_unsubscribe_flips_the_right_preference(event_type, pref_field):
    user_id = str(uuid.uuid4())
    token = unsubscribe.issue_token(user_id, pref_field)

    prefs = _make_prefs()
    db = _make_db(existing_prefs=prefs)

    result = await _apply_unsubscribe(db, token)

    # The targeted preference was flipped; others are untouched.
    assert getattr(prefs, pref_field) is False
    for other in (
        "email_on_resolution",
        "email_on_badge",
        "email_on_rank_change",
    ):
        if other == pref_field:
            continue
        assert getattr(prefs, other) is True

    # Commit + refresh happened.
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(prefs)

    # Return shape matches the schema.
    assert getattr(result, pref_field) is False


# ---------------------------------------------------------------------------
# Creates a prefs row on demand when none exists
# ---------------------------------------------------------------------------

async def test_unsubscribe_creates_prefs_row_when_missing():
    user_id = str(uuid.uuid4())
    token = unsubscribe.issue_token(user_id, "email_on_resolution")

    db = _make_db(existing_prefs=None)

    # Patch NotificationPreferences + select() so (a) select(NotificationPreferences)
    # doesn't blow up because our fake class is not a SQLA mapped class, and
    # (b) db.add(NotificationPreferences(user_id=...)) returns a usable stub.
    fake_prefs_cls = MagicMock(
        return_value=_make_prefs(
            email_on_resolution=True,
            email_on_badge=True,
            email_on_rank_change=True,
        )
    )
    fake_select = MagicMock()
    fake_select.return_value.where.return_value = MagicMock()  # passed to db.execute

    with patch("auth_service.api.NotificationPreferences", fake_prefs_cls), \
         patch("auth_service.api.select", fake_select):
        result = await _apply_unsubscribe(db, token)

    fake_prefs_cls.assert_called_once()
    db.add.assert_called_once()
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()
    assert result.email_on_resolution is False


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

async def test_garbage_token_returns_400():
    db = _make_db(existing_prefs=_make_prefs())
    with pytest.raises(HTTPException) as exc_info:
        await _apply_unsubscribe(db, "not.a.real.token")
    assert exc_info.value.status_code == 400
    db.commit.assert_not_awaited()


async def test_expired_token_returns_400():
    """A JWT with exp in the past is rejected by PyJWT during decode."""
    past_payload = {
        "sub": str(uuid.uuid4()),
        "pref": "email_on_resolution",
        "typ": "unsubscribe",
        "iat": int(time.time()) - 3600,
        "exp": int(time.time()) - 600,
    }
    token = jwt.encode(
        past_payload, config.UNSUBSCRIBE_TOKEN_SECRET, algorithm="HS256"
    )

    db = _make_db(existing_prefs=_make_prefs())
    with pytest.raises(HTTPException) as exc_info:
        await _apply_unsubscribe(db, token)
    assert exc_info.value.status_code == 400


async def test_token_with_wrong_typ_is_rejected():
    """Access tokens must not double as unsubscribe tokens."""
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "pref": "email_on_resolution",
            "typ": "access",  # wrong!
        },
        config.UNSUBSCRIBE_TOKEN_SECRET,
        algorithm="HS256",
    )
    db = _make_db(existing_prefs=_make_prefs())
    with pytest.raises(HTTPException) as exc_info:
        await _apply_unsubscribe(db, token)
    assert exc_info.value.status_code == 400


async def test_token_with_unknown_pref_returns_400():
    """notification-service validates this too, but auth-service double-checks."""
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "pref": "email_on_something_new",  # not in our allow-list
            "typ": "unsubscribe",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        config.UNSUBSCRIBE_TOKEN_SECRET,
        algorithm="HS256",
    )
    db = _make_db(existing_prefs=_make_prefs())
    with pytest.raises(HTTPException) as exc_info:
        await _apply_unsubscribe(db, token)
    assert exc_info.value.status_code == 400


async def test_token_with_invalid_sub_returns_400():
    """Token with a non-UUID subject is an error, not a 500."""
    # Bypass issue_token (which would otherwise reject non-UUID sub).
    token = jwt.encode(
        {
            "sub": "not-a-uuid",
            "pref": "email_on_resolution",
            "typ": "unsubscribe",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        config.UNSUBSCRIBE_TOKEN_SECRET,
        algorithm="HS256",
    )
    db = _make_db(existing_prefs=_make_prefs())
    with pytest.raises(HTTPException) as exc_info:
        await _apply_unsubscribe(db, token)
    assert exc_info.value.status_code == 400
