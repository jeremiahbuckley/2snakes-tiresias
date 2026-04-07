"""
Notification templates.

Returns plain-text and HTML bodies for each notification type.
TODO: replace with a proper templating engine (e.g. Jinja2).
"""

from __future__ import annotations


def market_resolved_email(market_title: str, outcome: str, brier_score: float) -> dict:
    subject = f"Market resolved: {market_title}"
    body = (
        f"The market '{market_title}' has resolved {outcome.upper()}.\n\n"
        f"Your Brier score for this prediction: {brier_score:.4f}\n\n"
        "Log in to view your updated stats and badges."
    )
    return {"subject": subject, "body": body}


def badge_earned_email(badge_name: str, badge_description: str) -> dict:
    subject = f"You earned a badge: {badge_name}!"
    body = (
        f"Congratulations! You've earned the '{badge_name}' badge.\n\n"
        f"{badge_description}\n\n"
        "View your profile to share your achievement."
    )
    return {"subject": subject, "body": body}


def rank_change_email(new_rank: int, total_users: int) -> dict:
    subject = f"You're now ranked #{new_rank} on the leaderboard!"
    body = (
        f"Your prediction accuracy has moved you to rank #{new_rank} "
        f"out of {total_users} forecasters.\n\n"
        "Keep it up!"
    )
    return {"subject": subject, "body": body}
