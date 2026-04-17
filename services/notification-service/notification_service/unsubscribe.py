"""
Unsubscribe token helpers.

A single-click unsubscribe link carries a signed JWT identifying which
preference flag to flip. Tokens are signed with ``UNSUBSCRIBE_TOKEN_SECRET``
(shared with auth-service). Claims:

  sub   — user_id (stringified UUID)
  pref  — NotificationPreferences field to set to False, e.g.
          "email_on_resolution" | "email_on_badge" | "email_on_rank_change"
  exp   — expiration (default: 365 days — tokens must outlive the email)
  iat   — issued-at timestamp
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt  # PyJWT

from . import config

ALGORITHM = "HS256"

PrefField = Literal["email_on_resolution", "email_on_badge", "email_on_rank_change"]

# Event type -> preference field the unsubscribe link should toggle off
EVENT_TO_PREF: dict[str, PrefField] = {
    "market_resolved": "email_on_resolution",
    "badge_earned": "email_on_badge",
    "rank_change": "email_on_rank_change",
}


def pref_field_for_event(event_type: str) -> PrefField:
    """Return the NotificationPreferences field that controls ``event_type``."""
    try:
        return EVENT_TO_PREF[event_type]
    except KeyError as exc:
        raise ValueError(f"No preference field mapped for event {event_type!r}") from exc


def issue_token(user_id: str, pref: PrefField) -> str:
    """Mint a signed unsubscribe token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "pref": pref,
        "iat": now,
        "exp": now + timedelta(days=config.UNSUBSCRIBE_TOKEN_EXPIRE_DAYS),
        "typ": "unsubscribe",
    }
    return jwt.encode(payload, config.UNSUBSCRIBE_TOKEN_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and validate an unsubscribe token.

    Raises jwt.InvalidTokenError (or a subclass) on any problem.
    """
    claims = jwt.decode(
        token,
        config.UNSUBSCRIBE_TOKEN_SECRET,
        algorithms=[ALGORITHM],
    )
    if claims.get("typ") != "unsubscribe":
        raise jwt.InvalidTokenError("Token is not an unsubscribe token")
    if claims.get("pref") not in EVENT_TO_PREF.values():
        raise jwt.InvalidTokenError(
            f"Token carries an invalid pref field: {claims.get('pref')!r}"
        )
    return claims


def unsubscribe_url_for_event(user_id: str, event_type: str) -> str:
    """Build the full unsubscribe URL for a given event type."""
    pref = pref_field_for_event(event_type)
    token = issue_token(user_id, pref)
    return config.unsubscribe_url(token)
