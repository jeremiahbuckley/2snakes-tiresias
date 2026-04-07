"""
Notification dispatcher.

Routes notification events to the appropriate channel handler.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class NotificationType(StrEnum):
    MARKET_RESOLVED = "market_resolved"
    BADGE_EARNED = "badge_earned"
    RANK_CHANGE = "rank_change"


@dataclass
class Notification:
    user_id: str
    type: NotificationType
    payload: dict[str, Any]


async def dispatch(notification: Notification) -> None:
    """
    Route a notification to the correct handler based on type.
    TODO: implement channel routing (email, push, in-app).
    """
    handlers = {
        NotificationType.MARKET_RESOLVED: _handle_market_resolved,
        NotificationType.BADGE_EARNED: _handle_badge_earned,
        NotificationType.RANK_CHANGE: _handle_rank_change,
    }
    handler = handlers.get(notification.type)
    if handler:
        await handler(notification)


async def _handle_market_resolved(n: Notification) -> None:
    """Notify user that a market they predicted on has resolved."""
    # TODO: fetch user email, render template, send via email provider
    raise NotImplementedError


async def _handle_badge_earned(n: Notification) -> None:
    """Notify user they earned a new badge."""
    # TODO: render badge earned template, send
    raise NotImplementedError


async def _handle_rank_change(n: Notification) -> None:
    """Notify user their leaderboard rank has changed."""
    # TODO: only notify on significant changes (e.g. top 10 entry)
    raise NotImplementedError
