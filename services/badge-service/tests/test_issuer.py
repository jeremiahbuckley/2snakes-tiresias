"""Unit tests for badge evaluation logic."""

import pytest
from badge_service.issuer import evaluate_badges, diff_badges
from scoring_engine.engine import UserScoreResult


def make_score(**kwargs) -> UserScoreResult:
    defaults = dict(
        user_id="test-user",
        total_predictions=0,
        mean_brier_score=None,
        brier_skill_score=None,
        expected_calibration_error=None,
        per_source={},
        per_domain={},
    )
    return UserScoreResult(**{**defaults, **kwargs})


def test_no_badges_for_new_user():
    score = make_score()
    assert evaluate_badges(score) == []


def test_first_prediction_badge():
    score = make_score(total_predictions=1)
    assert "first-prediction" in evaluate_badges(score)


def test_above_baseline_badge():
    score = make_score(total_predictions=20, brier_skill_score=0.1)
    assert "above-baseline" in evaluate_badges(score)


def test_well_calibrated_requires_50_predictions():
    score = make_score(total_predictions=40, expected_calibration_error=0.03)
    assert "well-calibrated" not in evaluate_badges(score)

    score2 = make_score(total_predictions=50, expected_calibration_error=0.03)
    assert "well-calibrated" in evaluate_badges(score2)


def test_diff_badges_grant_and_revoke():
    current = {"first-prediction", "old-badge"}
    earned = ["first-prediction", "ten-predictions"]
    to_grant, to_revoke = diff_badges(current, earned)
    assert "ten-predictions" in to_grant
    assert "old-badge" in to_revoke
