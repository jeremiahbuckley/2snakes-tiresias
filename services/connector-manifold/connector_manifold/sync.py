"""Manifold sync entrypoint — called by the scheduler."""

from __future__ import annotations

from .adapter import normalise_market, normalise_prediction
from .client import ManifoldClient


async def sync_markets() -> list[dict]:
    client = ManifoldClient()
    raw = await client.get_markets(sort="newest", limit=500)
    return [normalise_market(m) for m in raw]


async def sync_user_predictions(user_id: str, manifold_username: str) -> list[dict]:
    client = ManifoldClient()
    raw = await client.get_user_bets(manifold_username)
    return [normalise_prediction(b, user_id) for b in raw]
