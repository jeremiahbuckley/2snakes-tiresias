"""Metaculus sync entrypoint — called by the scheduler."""

from __future__ import annotations

from .adapter import normalise_market, normalise_prediction
from .client import MetaculusClient


async def sync_markets() -> list[dict]:
    client = MetaculusClient()
    raw = await client.get_questions(status="open", type="forecast")
    return [normalise_market(q) for q in raw]


async def sync_user_predictions(user_id: str, metaculus_user_id: int) -> list[dict]:
    client = MetaculusClient()
    raw = await client.get_user_predictions(metaculus_user_id)
    return [normalise_prediction(p, user_id) for p in raw]
