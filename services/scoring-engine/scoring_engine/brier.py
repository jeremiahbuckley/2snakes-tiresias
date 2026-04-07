"""
Brier score calculation.

The Brier score measures the accuracy of probabilistic predictions.
  BS = (1/N) * Σ (f_t - o_t)²

  f_t = predicted probability (0–1)
  o_t = outcome (1 for YES, 0 for NO)

Lower is better. Perfect score = 0.0, worst = 1.0.
Baseline (always predict 0.5) = 0.25.
"""

from __future__ import annotations


def brier_score(predicted: float, outcome: bool) -> float:
    """
    Compute the Brier score for a single prediction.

    Args:
        predicted: probability assigned to the YES outcome (0–1)
        outcome:   True if the event occurred (YES), False otherwise

    Returns:
        Brier score in [0, 1]
    """
    o = 1.0 if outcome else 0.0
    return (predicted - o) ** 2


def mean_brier_score(predictions: list[tuple[float, bool]]) -> float | None:
    """
    Compute the mean Brier score over a list of (predicted, outcome) pairs.

    Returns None if the list is empty.
    """
    if not predictions:
        return None
    scores = [brier_score(p, o) for p, o in predictions]
    return sum(scores) / len(scores)


def brier_skill_score(mean_bs: float, reference_bs: float = 0.25) -> float:
    """
    Brier Skill Score relative to a naive baseline.

    BSS = 1 - (BS / BS_reference)

    BSS > 0 means better than reference; BSS = 1 is perfect.
    """
    if reference_bs == 0:
        raise ValueError("Reference Brier score cannot be zero.")
    return 1.0 - (mean_bs / reference_bs)
