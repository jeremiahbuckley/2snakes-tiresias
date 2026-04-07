"""Unit tests for notification templates."""

from notification_service.templates import (
    market_resolved_email,
    badge_earned_email,
    rank_change_email,
)


def test_market_resolved_email():
    result = market_resolved_email("Will X happen?", "yes", 0.04)
    assert "Will X happen?" in result["subject"]
    assert "0.0400" in result["body"]


def test_badge_earned_email():
    result = badge_earned_email("Well Calibrated", "ECE below 0.05")
    assert "Well Calibrated" in result["subject"]
    assert "ECE below 0.05" in result["body"]


def test_rank_change_email():
    result = rank_change_email(7, 500)
    assert "#7" in result["subject"]
    assert "500" in result["body"]
