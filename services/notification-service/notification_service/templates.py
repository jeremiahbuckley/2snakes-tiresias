"""
Notification template rendering.

Templates live under ``notification_service/templates/`` as paired
``<event>.html`` and ``<event>.txt`` Jinja2 files. Each template extends
the appropriate ``base.html`` / ``base.txt`` which renders the Tiresias
header and the unsubscribe footer.

Public API:

    render(event, context)  ->  {"subject": ..., "html": ..., "text": ...}

The three convenience functions below (``market_resolved_email``,
``badge_earned_email``, ``rank_change_email``) are preserved for backward
compatibility with existing tests and call sites. They now produce
HTML + plaintext via Jinja2 — not just plaintext.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from . import config
from .unsubscribe import unsubscribe_url_for_event

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=False),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
)


# ---------------------------------------------------------------------------
# Subject lines
# ---------------------------------------------------------------------------

def _subject_market_resolved(context: dict[str, Any]) -> str:
    resolutions = context.get("resolutions") or []
    if len(resolutions) == 1:
        return f"Market resolved: {resolutions[0]['market_title']}"
    return f"{len(resolutions)} markets you predicted on have resolved"


def _subject_badge_earned(context: dict[str, Any]) -> str:
    return f"You earned a badge: {context['badge_name']}!"


def _subject_rank_change(context: dict[str, Any]) -> str:
    return f"You're now ranked #{context['new_rank']} on the leaderboard!"


_SUBJECTS = {
    "market_resolved": _subject_market_resolved,
    "badge_earned": _subject_badge_earned,
    "rank_change": _subject_rank_change,
}


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render(event: str, context: dict[str, Any]) -> dict[str, str]:
    """
    Render a full email payload for the given event.

    Parameters
    ----------
    event
        One of ``"market_resolved"``, ``"badge_earned"``, ``"rank_change"``.
    context
        Template variables. Must include ``user_id`` and ``display_name``
        (always). Event-specific fields described in each handler.

    Returns
    -------
    dict with keys ``subject``, ``html``, ``text``, ``unsubscribe_url``.
    """
    if event not in _SUBJECTS:
        raise ValueError(f"Unknown notification event: {event!r}")

    user_id = context["user_id"]
    ctx = {
        **context,
        "app_url": config.PUBLIC_APP_URL,
        "unsubscribe_url": unsubscribe_url_for_event(str(user_id), event),
    }

    subject = _SUBJECTS[event](ctx)
    ctx["subject"] = subject

    html = _env.get_template(f"{event}.html").render(**ctx)
    text = _env.get_template(f"{event}.txt").render(**ctx)

    return {
        "subject": subject,
        "html": html,
        "text": text,
        "unsubscribe_url": ctx["unsubscribe_url"],
    }


# ---------------------------------------------------------------------------
# Back-compat wrappers (used by existing tests)
# ---------------------------------------------------------------------------

def market_resolved_email(
    market_title: str,
    outcome: str,
    brier_score: float,
    *,
    user_id: str = "00000000-0000-0000-0000-000000000000",
    display_name: str = "there",
) -> dict[str, str]:
    """Backward-compat shim returning ``{"subject", "body"}``."""
    result = render(
        "market_resolved",
        {
            "user_id": user_id,
            "display_name": display_name,
            "resolutions": [
                {
                    "market_title": market_title,
                    "outcome": outcome,
                    "brier_score": brier_score,
                }
            ],
        },
    )
    # Legacy callers expected a plaintext ``body`` key. Preserve it.
    return {"subject": result["subject"], "body": result["text"]}


def badge_earned_email(
    badge_name: str,
    badge_description: str,
    *,
    user_id: str = "00000000-0000-0000-0000-000000000000",
    display_name: str = "there",
    username: str = "you",
) -> dict[str, str]:
    result = render(
        "badge_earned",
        {
            "user_id": user_id,
            "display_name": display_name,
            "username": username,
            "badge_name": badge_name,
            "badge_description": badge_description,
        },
    )
    return {"subject": result["subject"], "body": result["text"]}


def rank_change_email(
    new_rank: int,
    total_users: int,
    *,
    user_id: str = "00000000-0000-0000-0000-000000000000",
    display_name: str = "there",
    milestone_label: str = "a new milestone",
    previous_rank: int | None = None,
) -> dict[str, str]:
    result = render(
        "rank_change",
        {
            "user_id": user_id,
            "display_name": display_name,
            "new_rank": new_rank,
            "total_users": total_users,
            "milestone_label": milestone_label,
            "previous_rank": previous_rank,
        },
    )
    return {"subject": result["subject"], "body": result["text"]}
