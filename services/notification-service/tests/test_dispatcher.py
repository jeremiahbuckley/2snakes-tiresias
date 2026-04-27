"""
Tests for the dispatch pipeline.

Strategy: mock the DB session, the delivery CRUD, and the Resend client.
This exercises the full handler logic — preference check, dedupe claim,
template render, send, delivery-record update — without requiring
PostgreSQL or network calls.
"""

from __future__ import annotations

import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from notification_service.dispatcher import (
    Notification,
    NotificationType,
    dispatch,
)


# ---------------------------------------------------------------------------
# Fake fixtures
# ---------------------------------------------------------------------------

def _make_user(
    user_id: uuid.UUID | None = None,
    email: str = "test@example.com",
    username: str = "testuser",
    display_name: str = "Test User",
) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = email
    user.username = username
    user.display_name = display_name
    return user


def _make_prefs(
    email_on_resolution: bool = True,
    email_on_badge: bool = True,
    email_on_rank_change: bool = True,
) -> MagicMock:
    prefs = MagicMock()
    prefs.email_on_resolution = email_on_resolution
    prefs.email_on_badge = email_on_badge
    prefs.email_on_rank_change = email_on_rank_change
    return prefs


def _patched_handler_deps(
    *,
    user=None,
    prefs=None,
    claim_returns=None,
    send_returns="fake-id-123",
    send_raises=None,
):
    """
    Build the full set of mocks used by the handler. Returns a dict of
    patchers the test body should enter as context managers.
    """

    # The DB session — we don't exercise it, just pass it through.
    db = AsyncMock()
    db.get = AsyncMock(return_value=user)

    # Query for NotificationPreferences
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=prefs)
    db.execute = AsyncMock(return_value=result)

    # Delivery claim: default = fresh claim (returns a row)
    if claim_returns is None:
        claim_returns = MagicMock(id=uuid.uuid4())

    crud_claim = AsyncMock(return_value=claim_returns)
    crud_mark_sent = AsyncMock()
    crud_mark_failed = AsyncMock()

    send_mock = AsyncMock(
        return_value=send_returns,
        side_effect=send_raises if send_raises is not None else None,
    )

    return {
        "db": db,
        "user": user,
        "prefs": prefs,
        "crud_claim": crud_claim,
        "crud_mark_sent": crud_mark_sent,
        "crud_mark_failed": crud_mark_failed,
        "send_mock": send_mock,
    }


async def _dispatch_with_mocks(
    notification: Notification,
    mocks: dict,
):
    """Run dispatch with the standard set of patches applied."""
    # Bypass the real SQLAlchemy ORM call: hand the handlers a pre-built
    # (user, prefs) pair so we don't need real declarative models.
    load_user = AsyncMock(return_value=(mocks["user"], mocks["prefs"]))

    with patch(
        "notification_service.dispatcher._load_user_with_prefs", load_user
    ), patch(
        "notification_service.dispatcher.EmailDeliveryCRUD.claim",
        mocks["crud_claim"],
    ), patch(
        "notification_service.dispatcher.EmailDeliveryCRUD.mark_sent",
        mocks["crud_mark_sent"],
    ), patch(
        "notification_service.dispatcher.EmailDeliveryCRUD.mark_failed",
        mocks["crud_mark_failed"],
    ), patch(
        "notification_service.dispatcher.send_email",
        mocks["send_mock"],
    ):
        await dispatch(notification, db=mocks["db"])


# ---------------------------------------------------------------------------
# market_resolved
# ---------------------------------------------------------------------------

class TestMarketResolved:

    async def test_happy_path_single_resolution(self):
        user = _make_user()
        prefs = _make_prefs(email_on_resolution=True)
        mocks = _patched_handler_deps(user=user, prefs=prefs)

        n = Notification(
            user_id=str(user.id),
            type=NotificationType.MARKET_RESOLVED,
            payload={
                "resolutions": [
                    {
                        "market_id": "market-1",
                        "market_title": "Will X happen?",
                        "outcome": "yes",
                        "brier_score": 0.04,
                    }
                ]
            },
        )

        await _dispatch_with_mocks(n, mocks)

        # Claimed the right dedupe slot
        mocks["crud_claim"].assert_awaited_once()
        kwargs = mocks["crud_claim"].call_args.kwargs
        assert kwargs["event_type"] == "market_resolved"
        assert kwargs["dedupe_key"] == hashlib.sha256(b"market-1").hexdigest()

        # Actually tried to send
        mocks["send_mock"].assert_awaited_once()
        sent = mocks["send_mock"].call_args.args[0]
        assert sent.to == user.email
        assert "Will X happen?" in sent.subject
        assert "<html" in sent.html.lower()
        # List-Unsubscribe headers present for RFC 8058 compliance
        assert "List-Unsubscribe" in sent.headers
        assert sent.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"

        # Delivery record marked sent with provider id
        mocks["crud_mark_sent"].assert_awaited_once()
        assert (
            mocks["crud_mark_sent"].call_args.kwargs["provider_message_id"]
            == "fake-id-123"
        )

    async def test_dedupe_key_sorts_multiple_market_ids(self):
        user = _make_user()
        prefs = _make_prefs()
        mocks = _patched_handler_deps(user=user, prefs=prefs)

        n = Notification(
            user_id=str(user.id),
            type=NotificationType.MARKET_RESOLVED,
            payload={
                "resolutions": [
                    {"market_id": "zebra", "market_title": "z", "outcome": "yes", "brier_score": 0.1},
                    {"market_id": "alpha", "market_title": "a", "outcome": "no", "brier_score": 0.2},
                ]
            },
        )

        await _dispatch_with_mocks(n, mocks)

        assert (
            mocks["crud_claim"].call_args.kwargs["dedupe_key"]
            == hashlib.sha256(b"alpha,zebra").hexdigest()
        )

    async def test_skips_when_user_opted_out(self):
        user = _make_user()
        prefs = _make_prefs(email_on_resolution=False)
        mocks = _patched_handler_deps(user=user, prefs=prefs)

        n = Notification(
            user_id=str(user.id),
            type=NotificationType.MARKET_RESOLVED,
            payload={
                "resolutions": [
                    {"market_id": "m", "market_title": "t", "outcome": "yes", "brier_score": 0.1}
                ]
            },
        )

        await _dispatch_with_mocks(n, mocks)

        mocks["crud_claim"].assert_not_awaited()
        mocks["send_mock"].assert_not_awaited()

    async def test_skips_when_already_delivered(self):
        """If the claim returns None, a prior send exists — skip."""
        user = _make_user()
        prefs = _make_prefs()
        mocks = _patched_handler_deps(user=user, prefs=prefs, claim_returns=None)
        # Override: claim returns None on conflict
        mocks["crud_claim"] = AsyncMock(return_value=None)

        n = Notification(
            user_id=str(user.id),
            type=NotificationType.MARKET_RESOLVED,
            payload={
                "resolutions": [
                    {"market_id": "m", "market_title": "t", "outcome": "yes", "brier_score": 0.1}
                ]
            },
        )

        await _dispatch_with_mocks(n, mocks)

        mocks["send_mock"].assert_not_awaited()
        mocks["crud_mark_sent"].assert_not_awaited()

    async def test_marks_failed_on_send_error(self):
        user = _make_user()
        prefs = _make_prefs()
        mocks = _patched_handler_deps(
            user=user, prefs=prefs, send_raises=RuntimeError("provider down")
        )

        n = Notification(
            user_id=str(user.id),
            type=NotificationType.MARKET_RESOLVED,
            payload={
                "resolutions": [
                    {"market_id": "m", "market_title": "t", "outcome": "yes", "brier_score": 0.1}
                ]
            },
        )

        await _dispatch_with_mocks(n, mocks)

        mocks["crud_mark_failed"].assert_awaited_once()
        mocks["crud_mark_sent"].assert_not_awaited()

    async def test_missing_resolutions_is_a_noop(self):
        user = _make_user()
        prefs = _make_prefs()
        mocks = _patched_handler_deps(user=user, prefs=prefs)

        n = Notification(
            user_id=str(user.id),
            type=NotificationType.MARKET_RESOLVED,
            payload={"resolutions": []},
        )

        await _dispatch_with_mocks(n, mocks)

        mocks["crud_claim"].assert_not_awaited()
        mocks["send_mock"].assert_not_awaited()

    async def test_unknown_user_is_a_noop(self):
        mocks = _patched_handler_deps(user=None, prefs=None)

        n = Notification(
            user_id=str(uuid.uuid4()),
            type=NotificationType.MARKET_RESOLVED,
            payload={
                "resolutions": [
                    {"market_id": "m", "market_title": "t", "outcome": "yes", "brier_score": 0.1}
                ]
            },
        )

        await _dispatch_with_mocks(n, mocks)

        mocks["crud_claim"].assert_not_awaited()
        mocks["send_mock"].assert_not_awaited()


# ---------------------------------------------------------------------------
# badge_earned
# ---------------------------------------------------------------------------

class TestBadgeEarned:

    async def test_happy_path(self):
        user = _make_user()
        prefs = _make_prefs(email_on_badge=True)
        mocks = _patched_handler_deps(user=user, prefs=prefs)

        n = Notification(
            user_id=str(user.id),
            type=NotificationType.BADGE_EARNED,
            payload={
                "badge_id": "well-calibrated",
                "badge_name": "Well Calibrated",
                "badge_description": "ECE below 0.05",
            },
        )

        await _dispatch_with_mocks(n, mocks)

        assert mocks["crud_claim"].call_args.kwargs["dedupe_key"] == "well-calibrated"
        mocks["send_mock"].assert_awaited_once()
        sent = mocks["send_mock"].call_args.args[0]
        assert "Well Calibrated" in sent.subject
        assert "ECE below 0.05" in sent.text

    async def test_missing_fields_skip_dispatch(self):
        user = _make_user()
        prefs = _make_prefs()
        mocks = _patched_handler_deps(user=user, prefs=prefs)

        # Missing name + description
        n = Notification(
            user_id=str(user.id),
            type=NotificationType.BADGE_EARNED,
            payload={"badge_id": "x"},
        )

        await _dispatch_with_mocks(n, mocks)

        mocks["crud_claim"].assert_not_awaited()
        mocks["send_mock"].assert_not_awaited()

    async def test_opt_out_skips(self):
        user = _make_user()
        prefs = _make_prefs(email_on_badge=False)
        mocks = _patched_handler_deps(user=user, prefs=prefs)

        n = Notification(
            user_id=str(user.id),
            type=NotificationType.BADGE_EARNED,
            payload={
                "badge_id": "x",
                "badge_name": "X",
                "badge_description": "d",
            },
        )

        await _dispatch_with_mocks(n, mocks)

        mocks["send_mock"].assert_not_awaited()


# ---------------------------------------------------------------------------
# rank_change
# ---------------------------------------------------------------------------

class TestRankChange:

    async def test_happy_path(self):
        user = _make_user()
        prefs = _make_prefs(email_on_rank_change=True)
        mocks = _patched_handler_deps(user=user, prefs=prefs)

        n = Notification(
            user_id=str(user.id),
            type=NotificationType.RANK_CHANGE,
            payload={
                "new_rank": 7,
                "previous_rank": 15,
                "total_users": 500,
                "milestone": "top10",
                "milestone_label": "the top 10",
            },
        )

        await _dispatch_with_mocks(n, mocks)

        # Dedupe key is the milestone — not the exact rank
        assert mocks["crud_claim"].call_args.kwargs["dedupe_key"] == "top10"
        sent = mocks["send_mock"].call_args.args[0]
        assert "#7" in sent.subject
        assert "the top 10" in sent.text
        assert "500" in sent.text

    async def test_opt_out_skips(self):
        user = _make_user()
        prefs = _make_prefs(email_on_rank_change=False)
        mocks = _patched_handler_deps(user=user, prefs=prefs)

        n = Notification(
            user_id=str(user.id),
            type=NotificationType.RANK_CHANGE,
            payload={
                "new_rank": 1,
                "total_users": 500,
                "milestone": "top1",
                "milestone_label": "#1",
            },
        )

        await _dispatch_with_mocks(n, mocks)

        mocks["send_mock"].assert_not_awaited()

    async def test_incomplete_payload_is_noop(self):
        user = _make_user()
        prefs = _make_prefs()
        mocks = _patched_handler_deps(user=user, prefs=prefs)

        # Missing milestone_label
        n = Notification(
            user_id=str(user.id),
            type=NotificationType.RANK_CHANGE,
            payload={
                "new_rank": 1,
                "total_users": 500,
                "milestone": "top1",
            },
        )

        await _dispatch_with_mocks(n, mocks)

        mocks["crud_claim"].assert_not_awaited()
        mocks["send_mock"].assert_not_awaited()
