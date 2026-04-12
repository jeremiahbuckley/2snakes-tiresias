"""
Metaculus → Tiresias adapter (v2.0 OAS3 API).

API data model notes:
- The top-level entity is a Post, which wraps a Question (or a Conditional /
  GroupOfQuestions for v2+ question types — both are TODO for v1).
- Resolution is now a string: "yes" | "no" | "annulled" | "ambiguous" | None.
  The old API used integers (1/0/-1); the new API uses strings directly.
- Timestamps are ISO-8601 strings (e.g. "2025-01-01T00:00:00Z"), not Unix ints.
- Tags/categories live on the Post, not the Question: post["categories"] is a
  list of {"id": int, "name": str, "slug": str, "description": str}.
- User forecast data is embedded in the Question object when the authenticated
  user fetches the post. The `my_forecasts` list (most recent last) contains
  entries with:
    - probability_yes  (float 0-1)  ← binary questions
    - start_time       (ISO-8601)   ← when this forecast was submitted
    - end_time         (ISO-8601)   ← when it was superseded or withdrawn
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def normalise_market(raw_post: dict[str, Any]) -> dict[str, Any]:
    """Map a raw Metaculus Post to the internal Market schema.

    For v1, only posts with a single `question` field are handled. Posts with
    `group_of_questions` or `conditional` are passed through with
    question_type="unsupported".
    """
    question = raw_post.get("question") or {}
    categories = raw_post.get("categories") or []

    resolution = question.get("resolution")   # str | None
    resolved = raw_post.get("resolved", False)

    # Prefer actual over scheduled timestamps; fall back gracefully.
    closes_at = _parse_ts(
        question.get("actual_close_time") or question.get("scheduled_close_time")
    )
    resolves_at = _parse_ts(
        question.get("actual_resolve_time") or question.get("scheduled_resolve_time")
    )

    return {
        "external_id": str(raw_post.get("id")),
        "source": "metaculus",
        "title": raw_post.get("title") or question.get("title"),
        "description": question.get("description"),
        "resolution_criteria": question.get("resolution_criteria"),
        "fine_print": question.get("fine_print"),
        "closes_at": closes_at,
        "resolves_at": resolves_at,
        "resolved": resolved,
        "outcome": resolution,                   # "yes" | "no" | "annulled" | "ambiguous" | None
        "question_type": question.get("type"),   # "binary" | "numeric" | etc.
        "tags": [c["slug"] for c in categories if c.get("slug")],
        "raw": raw_post,
    }


def normalise_forecast(raw_post: dict[str, Any], user_id: str) -> dict[str, Any]:
    """Map a Metaculus Post (with embedded my_forecasts) to the internal Prediction schema.

    When the authenticated user fetches a post via GET /api/posts/{id}/, the
    question includes a `my_forecasts` list sorted oldest-first. We take the
    last entry as the user's current forecast.

    For binary questions the entry has:
        probability_yes : float (0–1) — the user's stated YES probability.
        start_time      : ISO-8601    — when this forecast was made.

    The external_id is a compound of post_id + user_id since the REST endpoint
    does not return a unique forecast record ID.
    """
    question = raw_post.get("question") or {}
    post_id = raw_post.get("id")

    my_forecasts = question.get("my_forecasts") or []
    last_forecast = my_forecasts[-1] if my_forecasts else {}

    return {
        "external_id": f"metaculus-{post_id}-{user_id}",
        "source": "metaculus",
        "user_external_id": user_id,
        "market_external_id": str(post_id),
        "predicted_probability": last_forecast.get("probability_yes"),
        "placed_at": _parse_ts(last_forecast.get("start_time")),
        "raw": last_forecast,
    }


def _parse_ts(ts: str | None) -> datetime | None:
    """Parse an ISO-8601 string (with or without trailing Z) into an aware datetime."""
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
