"""
Scoring engine entrypoint.

Orchestrates score computation for a user across all their resolved
predictions and persists results to the data layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .brier import brier_score, mean_brier_score, brier_skill_score
from .calibration import calibration_buckets, expected_calibration_error


@dataclass
class PredictionRecord:
    """Minimal representation of a resolved prediction."""
    prediction_id: str
    predicted_probability: float
    outcome: bool           # True = YES resolved
    source: str             # "kalshi" | "polymarket" | "manifold" | "metaculus"
    domain: str | None = None  # e.g. "politics", "science", "crypto"


@dataclass
class UserScoreResult:
    user_id: str
    total_predictions: int
    mean_brier_score: float | None
    brier_skill_score: float | None
    expected_calibration_error: float | None
    per_source: dict[str, float]   # source → mean Brier score
    per_domain: dict[str, float]   # domain → mean Brier score


def score_user(user_id: str, predictions: Sequence[PredictionRecord]) -> UserScoreResult:
    """
    Compute all scores for a user given their resolved predictions.

    This is the main entry point called by the scheduler after resolution.
    """
    resolved = list(predictions)
    pairs = [(p.predicted_probability, p.outcome) for p in resolved]

    mbs = mean_brier_score(pairs)
    bss = brier_skill_score(mbs) if mbs is not None else None
    buckets = calibration_buckets(pairs)
    ece = expected_calibration_error(buckets, len(pairs))

    per_source = _group_scores(resolved, key=lambda p: p.source)
    per_domain = _group_scores(resolved, key=lambda p: p.domain or "unknown")

    return UserScoreResult(
        user_id=user_id,
        total_predictions=len(resolved),
        mean_brier_score=mbs,
        brier_skill_score=bss,
        expected_calibration_error=ece,
        per_source=per_source,
        per_domain=per_domain,
    )


def _group_scores(
    predictions: list[PredictionRecord],
    key,
) -> dict[str, float]:
    from itertools import groupby
    result = {}
    keyed = sorted(predictions, key=key)
    for k, group in groupby(keyed, key=key):
        pairs = [(p.predicted_probability, p.outcome) for p in group]
        mbs = mean_brier_score(pairs)
        if mbs is not None:
            result[k] = mbs
    return result
