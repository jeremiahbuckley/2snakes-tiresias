"""Polymarket sync entrypoint — called by the scheduler."""

from __future__ import annotations

from .adapter import normalise_market, normalise_prediction
from .client import PolymarketClient


async def sync_markets() -> list[dict]:
    client = PolymarketClient()
    raw = await client.get_markets(active=True, closed=False)
    return [normalise_market(m) for m in raw]


async def sync_user_predictions(user_id: str, wallet_address: str) -> list[dict]:
    client = PolymarketClient()
    raw = await client.get_trades(wallet_address)
    return [normalise_prediction(t, user_id) for t in raw]
