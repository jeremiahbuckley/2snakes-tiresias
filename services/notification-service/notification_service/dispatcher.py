"""
Notification dispatcher.

Routes notification events to the appropriate channel handler. For V1
only email is supported (via Resend). Each handler is responsible for:

  1. Loading the target user + their NotificationPreferences.
  2. Checking the relevant preference flag; skip if the user opted out.
  3. Atomically claiming an email_deliveries dedupe slot; skip if the
     email has already been sent for this (user, event, entity).
  4. Rendering Jinja2 HTML + text templates.
  5. Sending via the Resend client (with a one-click List-Unsubscribe
     header for Gmail/Yahoo bulk-sender compliance).
  6. Recording the provider message id (or marking the row failed).

Send failures are logged and the exception is swallowed — the scheduler
is not responsible for notification reliability. If we later want
retries we can re-drive off the ``status="failed"`` rows in
``email_deliveries``.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:  # pragma: no cover — polyfill for Python 3.10 environments (tests)
    from enum import Enum

    class StrEnum(str, Enum):
        """Minimal 3.10 backport of stdlib ``enum.StrEnum``."""

        def __str__(self) -> str:  # pragma: no cover
            return self.value

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data.crud.email_delivery import EmailDeliveryCRUD
from data.database import db_context
from data.models.email_delivery import EmailDelivery
from data.models.notification_preferences import NotificationPreferences
from data.models.user import User

from . import templates
from .resend_client import EmailMessage, send_email
from .unsubscribe import unsubscribe_url_for_event

logger = logging.getLogger(__name__)


class NotificationType(StrEnum):
    MARKET_RESOLVED = "market_resolved"
    BADGE_EARNED = "badge_earned"
    RANK_CHANGE = "rank_change"


@dataclass
class Notification:
    user_id: str
    type: NotificationType
    payload: dict[str, Any]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def dispatch(
    notification: Notification,
    *,
    db: Optional[AsyncSession] = None,
) -> None:
    """
    Route a notification to the correct handler based on type.

    If ``db`` is provided, the handler runs inside the caller's session
    (useful when the caller already holds a transaction). Otherwise a
    fresh session is opened via ``db_context()``.
    """
    handlers = {
        NotificationType.MARKET_RESOLVED: _handle_market_resolved,
        NotificationType.BADGE_EARNED: _handle_badge_earned,
        NotificationType.RANK_CHANGE: _handle_rank_change,
    }
    handler = handlers.get(notification.type)
    if handler is None:
        logger.warning("No handler for notification type %s", notification.type)
        return

    if db is not None:
        await handler(notification, db)
    else:
        async with db_context() as session:
            await handler(notification, session)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_user_with_prefs(
    db: AsyncSession, user_id: UUID
) -> tuple[Optional[User], Optional[NotificationPreferences]]:
    """Fetch the user and (separately) their notification preferences."""
    user = await db.get(User, user_id)
    if user is None:
        return None, None

    result = await db.execute(
        select(NotificationPreferences).where(
            NotificationPreferences.user_id == user_id
        )
    )
    prefs = result.scalar_one_or_none()
    return user, prefs


async def _deliver(
    *,
    db: AsyncSession,
    user: User,
    event_type: str,
    dedupe_key: str,
    template_context: dict[str, Any],
) -> None:
    """
    Render + send a single email, recording success/failure in
    ``email_deliveries``. No-op if a delivery row already exists.
    """
    delivery = await EmailDeliveryCRUD.claim(
        db,
        user_id=user.id,
        event_type=event_type,
        dedupe_key=dedupe_key,
    )
    if delivery is None:
        logger.info(
            "notification skip (already delivered): user=%s event=%s key=%s",
            user.id, event_type, dedupe_key,
        )
        return

    # Build the rendered email. Add user-specific fields expected by all
    # templates but not supplied by callers.
    ctx = {
        "user_id": str(user.id),
        "display_name": user.display_name or user.username,
        "username": user.username,
        **template_context,
    }
    rendered = templates.render(event_type, ctx)

    unsub_url = rendered["unsubscribe_url"]
    # RFC 8058 one-click unsubscribe: Gmail/Yahoo require both headers.
    # ``List-Unsubscribe-Post`` tells MUAs they can POST to the same URL
    # without user interaction (for the top-of-inbox "Unsubscribe" button).
    headers = {
        "List-Unsubscribe": f"<{unsub_url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }

    message = EmailMessage(
        to=user.email,
        subject=rendered["subject"],
        text=rendered["text"],
        html=rendered["html"],
        headers=headers,
    )

    try:
        provider_id = await send_email(message)
    except Exception as exc:
        logger.warning(
            "notification send failed: user=%s event=%s key=%s error=%s",
            user.id, event_type, dedupe_key, exc,
        )
        await EmailDeliveryCRUD.mark_failed(db, delivery=delivery)
        return

    await EmailDeliveryCRUD.mark_sent(
        db, delivery=delivery, provider_message_id=provider_id
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _handle_market_resolved(n: Notification, db: AsyncSession) -> None:
    """
    Notify a user that one or more markets they predicted on have resolved.

    Payload shape:
      - "resolutions": list of
            {"market_id", "market_title", "outcome", "brier_score"}
        (When the scheduler dispatches per-market, this list has one item.
        When it batches a run's worth of resolutions together, it has many.)

    Dedupe key: sorted comma-joined market_ids. Identical payload in the
    next scheduler run is a no-op; a different subset triggers a new send.
    """
    user, prefs = await _load_user_with_prefs(db, UUID(n.user_id))
    if user is None:
        logger.warning("notification: user %s not found", n.user_id)
        return
    if prefs and not prefs.email_on_resolution:
        logger.info("notification skip (opted out): user=%s event=market_resolved", user.id)
        return

    resolutions = n.payload.get("resolutions") or []
    if not resolutions:
        logger.warning(
            "notification: market_resolved payload has no resolutions (user=%s)",
            n.user_id,
        )
        return

    market_ids = sorted(str(r["market_id"]) for r in resolutions)
    dedupe_key = ",".join(market_ids)

    await _deliver(
        db=db,
        user=user,
        event_type="market_resolved",
        dedupe_key=dedupe_key,
        template_context={"resolutions": resolutions},
    )


async def _handle_badge_earned(n: Notification, db: AsyncSession) -> None:
    """
    Notify a user they earned a new badge.

    Payload shape:
      - "badge_id"         (str, required) — stable slug from badge catalogue
      - "badge_name"       (str, required) — human-readable name
      - "badge_description" (str, required) — one-line description

    The caller (scheduler) is responsible for enriching the payload with
    name/description from the badge catalogue before dispatch, so this
    handler does no cross-service lookups.

    Dedupe key: badge_id. A badge can only be earned (and emailed about) once.
    """
    user, prefs = await _load_user_with_prefs(db, UUID(n.user_id))
    if user is None:
        logger.warning("notification: user %s not found", n.user_id)
        return
    if prefs and not prefs.email_on_badge:
        logger.info("notification skip (opted out): user=%s event=badge_earned", user.id)
        return

    badge_id = n.payload.get("badge_id")
    badge_name = n.payload.get("badge_name")
    badge_description = n.payload.get("badge_description")
    if not badge_id or not badge_name or not badge_description:
        logger.warning(
            "notification: badge_earned payload incomplete (user=%s payload=%s)",
            n.user_id, n.payload,
        )
        return

    await _deliver(
        db=db,
        user=user,
        event_type="badge_earned",
        dedupe_key=str(badge_id),
        template_context={
            "badge_name": badge_name,
            "badge_description": badge_description,
        },
    )


async def _handle_rank_change(n: Notification, db: AsyncSession) -> None:
    """
    Notify a user that their leaderboard rank crossed a significant milestone.

    Payload shape:
      - "new_rank"         (int, required)
      - "total_users"      (int, required)
      - "milestone"        (str, required) — e.g. "top10" | "top100" | "top1"
      - "milestone_label"  (str, required) — display text, e.g. "the top 10"
      - "previous_rank"    (int, optional)

    Dedupe key: ``"{milestone}:{new_rank}"`` — if a user leaves and re-enters
    the same milestone band we still suppress the email (intentional: no spam
    from noisy rank jitter at the boundary).
    """
    user, prefs = await _load_user_with_prefs(db, UUID(n.user_id))
    if user is None:
        logger.warning("notification: user %s not found", n.user_id)
        return
    if prefs and not prefs.email_on_rank_change:
        logger.info("notification skip (opted out): user=%s event=rank_change", user.id)
        return

    milestone = n.payload.get("milestone")
    new_rank = n.payload.get("new_rank")
    total_users = n.payload.get("total_users")
    milestone_label = n.payload.get("milestone_label")
    if milestone is None or new_rank is None or total_users is None or milestone_label is None:
        logger.warning(
            "notification: rank_change payload incomplete (user=%s payload=%s)",
            n.user_id, n.payload,
        )
        return

    # Dedupe on the milestone (not the exact rank) so repeated visits to
    # the same band don't re-email. The first entry wins.
    dedupe_key = str(milestone)

    await _deliver(
        db=db,
        user=user,
        event_type="rank_change",
        dedupe_key=dedupe_key,
        template_context={
            "new_rank": new_rank,
            "total_users": total_users,
            "milestone_label": milestone_label,
            "previous_rank": n.payload.get("previous_rank"),
        },
    )
