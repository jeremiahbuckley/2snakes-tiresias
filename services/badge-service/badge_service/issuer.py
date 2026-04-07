"""
Badge issuer.

Evaluates all badge criteria against a UserScoreResult and returns
the set of badge IDs the user should hold.

Does NOT write to the DB — callers are responsible for persistence.
"""

from __future__ import annotations

from .badges import BADGES, BadgeDefinition
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scoring_engine.engine import UserScoreResult


def evaluate_badges(score: "UserScoreResult") -> list[str]:
    """
    Return a list of badge IDs that the user qualifies for based on
    their current score result.
    """
    return [b.id for b in BADGES if b.check(score)]


def diff_badges(
    current_badge_ids: set[str],
    earned_badge_ids: list[str],
) -> tuple[list[str], list[str]]:
    """
    Compute which badges to grant and which to revoke.

    Returns:
        (to_grant, to_revoke) — lists of badge IDs
    """
    earned = set(earned_badge_ids)
    to_grant = sorted(earned - current_badge_ids)
    to_revoke = sorted(current_badge_ids - earned)
    return to_grant, to_revoke
