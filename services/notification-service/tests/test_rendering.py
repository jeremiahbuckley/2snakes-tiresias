"""Tests for Jinja2 template rendering (HTML + plaintext)."""

from __future__ import annotations

from notification_service import templates


USER_ID = "00000000-0000-0000-0000-000000000001"


def test_render_market_resolved_single_resolution():
    out = templates.render(
        "market_resolved",
        {
            "user_id": USER_ID,
            "display_name": "Jeremiah",
            "resolutions": [
                {
                    "market_id": "m-1",
                    "market_title": "Will X happen?",
                    "outcome": "yes",
                    "brier_score": 0.04,
                }
            ],
        },
    )

    assert out["subject"] == "Market resolved: Will X happen?"
    # Plaintext body
    assert "Will X happen?" in out["text"]
    assert "YES" in out["text"]
    assert "0.0400" in out["text"]
    assert "Jeremiah" in out["text"]
    # HTML body
    assert "Will X happen?" in out["html"]
    assert "<html" in out["html"].lower()
    # Footer
    assert "Unsubscribe" in out["text"]
    assert out["unsubscribe_url"].startswith("http")


def test_render_market_resolved_multiple_batched():
    out = templates.render(
        "market_resolved",
        {
            "user_id": USER_ID,
            "display_name": "Jeremiah",
            "resolutions": [
                {"market_id": "m-1", "market_title": "First market", "outcome": "yes", "brier_score": 0.04},
                {"market_id": "m-2", "market_title": "Second market", "outcome": "no", "brier_score": 0.16},
                {"market_id": "m-3", "market_title": "Third market", "outcome": "yes", "brier_score": 0.25},
            ],
        },
    )
    assert "3 markets" in out["subject"]
    assert "First market" in out["text"]
    assert "Second market" in out["text"]
    assert "Third market" in out["text"]
    assert "0.0400" in out["text"]
    assert "0.1600" in out["text"]


def test_render_badge_earned():
    out = templates.render(
        "badge_earned",
        {
            "user_id": USER_ID,
            "display_name": "Jeremiah",
            "username": "jbuckley",
            "badge_id": "well-calibrated",
            "badge_name": "Well Calibrated",
            "badge_description": "ECE below 0.05 with 50+ predictions.",
        },
    )
    assert "Well Calibrated" in out["subject"]
    assert "Well Calibrated" in out["text"]
    assert "ECE below 0.05" in out["text"]
    # HTML renders a CTA to the public profile
    assert "/u/jbuckley" in out["html"]


def test_render_rank_change():
    out = templates.render(
        "rank_change",
        {
            "user_id": USER_ID,
            "display_name": "Jeremiah",
            "username": "jbuckley",
            "new_rank": 7,
            "previous_rank": 15,
            "total_users": 500,
            "milestone_label": "the top 10",
        },
    )
    assert "#7" in out["subject"]
    assert "the top 10" in out["text"]
    assert "500" in out["text"]
    assert "Previously" in out["text"] and "#15" in out["text"]


def test_render_rank_change_no_previous_rank_omits_section():
    out = templates.render(
        "rank_change",
        {
            "user_id": USER_ID,
            "display_name": "Jeremiah",
            "username": "jbuckley",
            "new_rank": 1,
            "previous_rank": None,
            "total_users": 500,
            "milestone_label": "#1 on the leaderboard",
        },
    )
    assert "Previously" not in out["text"]


def test_render_unknown_event_raises():
    import pytest

    with pytest.raises(ValueError):
        templates.render("weekly_digest", {"user_id": USER_ID, "display_name": "x"})


def test_unsubscribe_url_contains_valid_token():
    from notification_service.unsubscribe import decode_token

    out = templates.render(
        "market_resolved",
        {
            "user_id": USER_ID,
            "display_name": "Jeremiah",
            "resolutions": [
                {"market_id": "m-1", "market_title": "T", "outcome": "yes", "brier_score": 0.1}
            ],
        },
    )
    url = out["unsubscribe_url"]
    token = url.split("token=", 1)[1]
    claims = decode_token(token)
    assert claims["pref"] == "email_on_resolution"
    assert claims["sub"] == USER_ID


def test_html_output_escapes_user_provided_strings():
    """Autoescape must neutralize HTML injected through the market title."""
    out = templates.render(
        "market_resolved",
        {
            "user_id": USER_ID,
            "display_name": "Jeremiah",
            "resolutions": [
                {
                    "market_id": "m-1",
                    "market_title": "<script>alert('xss')</script>",
                    "outcome": "yes",
                    "brier_score": 0.04,
                }
            ],
        },
    )
    assert "<script>" not in out["html"]
    assert "&lt;script&gt;" in out["html"]
