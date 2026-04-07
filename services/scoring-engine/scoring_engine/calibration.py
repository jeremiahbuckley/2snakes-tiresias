"""
Calibration analysis.

A forecaster is well-calibrated if events they assign X% probability to
occur roughly X% of the time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class CalibrationBucket:
    lower: float
    upper: float
    count: int
    correct: int

    @property
    def midpoint(self) -> float:
        return (self.lower + self.upper) / 2

    @property
    def empirical_frequency(self) -> float | None:
        if self.count == 0:
            return None
        return self.correct / self.count


def calibration_buckets(
    predictions: list[tuple[float, bool]],
    n_bins: int = 10,
) -> list[CalibrationBucket]:
    """
    Bin predictions into equal-width probability buckets and compute
    empirical frequencies per bucket.

    Args:
        predictions: list of (predicted_probability, outcome) tuples
        n_bins:      number of equal-width bins between 0 and 1

    Returns:
        List of CalibrationBucket, one per bin.
    """
    step = 1.0 / n_bins
    buckets = [
        CalibrationBucket(lower=i * step, upper=(i + 1) * step, count=0, correct=0)
        for i in range(n_bins)
    ]

    for prob, outcome in predictions:
        idx = min(int(prob * n_bins), n_bins - 1)
        buckets[idx].count += 1
        if outcome:
            buckets[idx].correct += 1

    return buckets


def expected_calibration_error(buckets: list[CalibrationBucket], total: int) -> float:
    """
    Expected Calibration Error (ECE) — weighted average of per-bucket
    absolute calibration error.
    """
    if total == 0:
        return 0.0
    ece = 0.0
    for b in buckets:
        if b.count == 0 or b.empirical_frequency is None:
            continue
        ece += (b.count / total) * abs(b.empirical_frequency - b.midpoint)
    return ece
