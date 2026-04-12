"""
Metaculus sync entrypoint.

V1 scope:
  - Pull all posts where the user has forecasted.
  - Filter to binary questions only (numeric/multiple-choice are TODO).
  - Pull post/question metadata on-demand for each unique post.

Posts (markets) are stored separately from forecasts; the link is
market_external_id = str(post_id). Resolution outcome is embedded in the
post's question record.

Auth note: Metaculus requires a token for all requests. The MetaculusClient
will raise ValueError at init if METACULUS_TOKEN is not set.
"""

from __future__ import annotations

from .adapter import normalise_forecast, normalise_market
from .client import MetaculusClient


async def sync_user_forecasts(user_id: str, metaculus_user_id: int) -> list[dict]:
    """Fetch all posts where the user has forecasted and return normalised forecasts.

    Only binary questions are included in v1; other types are silently skipped.

    Args:
        user_id: Tiresias internal user ID.
        metaculus_user_id: The user's integer ID on Metaculus.
    """
    client = MetaculusClient()
    posts = await client.get_user_posts(metaculus_user_id)
    results = []
    for post in posts:
        question = post.get("question") or {}
        if question.get("type") == "binary":
            results.append(normalise_forecast(post, user_id))
    return results


async def sync_market(post_id: int) -> dict:
    """Fetch metadata for a single Metaculus post by ID.

    Called after sync_user_forecasts to hydrate the unique posts referenced by
    those forecasts. Fetching the full post via GET /api/posts/{id}/ also
    returns the authenticated user's my_forecasts, so the two operations can
    be combined if needed.
    """
    client = MetaculusClient()
    raw = await client.get_post(post_id)
    return normalise_market(raw)
