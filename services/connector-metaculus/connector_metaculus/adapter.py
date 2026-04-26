"""
Metaculus → Tiresias adapter (v2.0 OAS3 API).

API data model notes:
- The top-level entity is a Post, which wraps a Question (or a Conditional /
  GroupOfQuestions for v2+ question types — both are TODO for v1).
- Resolution is now a string: "yes" | "no" | "annulled" | "ambiguous" | None.
  The old API used integers (1/0/-1); the new API uses strings directly.
- Market timestamps are ISO-8601 strings (e.g. "2025-01-01T00:00:00Z").
- Tags/categories live on the Post, not the Question: post["categories"] is a
  list of {"id": int, "name": str, "slug": str, "description": str}.
- User forecast data (my_forecasts) comes from the detail endpoint only
  (GET /api/posts/{id}/), as a dict:
    { "history": [...], "latest": {...} | None, "score_data": {} }
  Each entry has:
    - forecast_values  [P(NO), P(YES)]  ← binary questions; index 1 = P(YES)
    - start_time       Unix float        ← when this forecast was submitted
    - end_time         Unix float        ← when it was superseded or withdrawn
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

    The detail endpoint (GET /api/posts/{id}/) returns my_forecasts as:
        { "history": [...], "latest": {...} | None, "score_data": {} }
    We prefer `latest` as the user's current forecast; fall back to the last
    history entry. Each entry uses forecast_values[1] for P(YES) and Unix
    float timestamps. The external_id is compound (post_id + user_id) since
    the REST endpoint does not return a unique forecast record ID.
    """
    question = raw_post.get("question") or {}
    post_id = raw_post.get("id")

    my_forecasts_raw = question.get("my_forecasts")
    if isinstance(my_forecasts_raw, dict):
        last_forecast = my_forecasts_raw.get("latest") or {}
        if not last_forecast:
            history = my_forecasts_raw.get("history") or []
            last_forecast = history[-1] if history else {}
    elif isinstance(my_forecasts_raw, list):
        last_forecast = my_forecasts_raw[-1] if my_forecasts_raw else {}
    else:
        last_forecast = {}

    return {
        "external_id": f"metaculus-{post_id}-{user_id}",
        "source": "metaculus",
        "user_external_id": user_id,
        "market_external_id": str(post_id),
        "predicted_probability": _extract_probability_yes(last_forecast),
        "placed_at": _parse_ts(last_forecast.get("start_time")),
        "raw": last_forecast,
    }


def _extract_probability_yes(forecast: dict[str, Any]) -> float | None:
    """Extract P(YES) from a forecast entry.

    v2 API: forecast_values = [P(NO), P(YES)]; index 1 is P(YES).
    Legacy list format: probability_yes field directly.
    """
    forecast_values = forecast.get("forecast_values")
    if forecast_values is not None and len(forecast_values) >= 2:
        return forecast_values[1]
    return forecast.get("probability_yes")


def _parse_ts(ts: str | float | int | None) -> datetime | None:
    """Parse a timestamp into an aware datetime.

    Accepts ISO-8601 strings (market timestamps) and Unix floats (forecast timestamps).
    """
    if not ts and ts != 0:
        return None
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
