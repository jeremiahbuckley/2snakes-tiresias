"""
Badge definitions.

Each badge has an id, display name, description, and a predicate function
that takes a UserScoreResult and returns True if the user qualifies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from scoring_engine.engine import UserScoreResult


@dataclass(frozen=True)
class BadgeDefinition:
    id: str
    name: str
    description: str
    check: Callable[["UserScoreResult"], bool]


# ---------------------------------------------------------------------------
# Badge catalogue
# ---------------------------------------------------------------------------

BADGES: list[BadgeDefinition] = [
    BadgeDefinition(
        id="first-prediction",
        name="First Prediction",
        description="Made at least one resolved prediction.",
        check=lambda s: s.total_predictions >= 1,
    ),
    BadgeDefinition(
        id="ten-predictions",
        name="Getting Started",
        description="Made at least 10 resolved predictions.",
        check=lambda s: s.total_predictions >= 10,
    ),
    BadgeDefinition(
        id="hundred-predictions",
        name="Prolific Forecaster",
        description="Made at least 100 resolved predictions.",
        check=lambda s: s.total_predictions >= 100,
    ),
    BadgeDefinition(
        id="above-baseline",
        name="Better Than Coin Flip",
        description="Brier Skill Score > 0 (better than random).",
        check=lambda s: s.brier_skill_score is not None and s.brier_skill_score > 0,
    ),
    BadgeDefinition(
        id="well-calibrated",
        name="Well Calibrated",
        description="Expected Calibration Error below 0.05 with 50+ predictions.",
        check=lambda s: (
            s.total_predictions >= 50
            and s.expected_calibration_error is not None
            and s.expected_calibration_error < 0.05
        ),
    ),
    BadgeDefinition(
        id="multi-platform",
        name="Cross-Platform Forecaster",
        description="Resolved predictions on 3 or more platforms.",
        check=lambda s: len(s.per_source) >= 3,
    ),
    # TODO: add more badges (domain specialist, streak, top-10%, etc.)
]

BADGE_INDEX: dict[str, BadgeDefinition] = {b.id: b for b in BADGES}
