"""Unit tests for Brier score calculations."""

import pytest
from scoring_engine.brier import brier_score, mean_brier_score, brier_skill_score


def test_brier_perfect_yes():
    assert brier_score(1.0, True) == pytest.approx(0.0)


def test_brier_perfect_no():
    assert brier_score(0.0, False) == pytest.approx(0.0)


def test_brier_worst_yes():
    assert brier_score(0.0, True) == pytest.approx(1.0)


def test_brier_midpoint():
    # Predicting 0.5 on any outcome = 0.25
    assert brier_score(0.5, True) == pytest.approx(0.25)
    assert brier_score(0.5, False) == pytest.approx(0.25)


def test_mean_brier_empty():
    assert mean_brier_score([]) is None


def test_mean_brier_single():
    assert mean_brier_score([(0.8, True)]) == pytest.approx(0.04)


def test_brier_skill_score_baseline():
    # A mean BS equal to the baseline (0.25) should give BSS = 0
    assert brier_skill_score(0.25) == pytest.approx(0.0)


def test_brier_skill_score_perfect():
    assert brier_skill_score(0.0) == pytest.approx(1.0)
