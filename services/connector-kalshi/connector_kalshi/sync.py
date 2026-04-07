"""
Kalshi sync entrypoint.

Called by the scheduler to pull new markets and resolve predictions.
"""

from __future__ import annotations

from .adapter import normalise_market, normalise_prediction
from .client import KalshiClient


async def sync_markets() -> list[dict]:
    """Fetch all active Kalshi markets and return normalised dicts."""
    client = KalshiClient()
    raw_markets = await client.get_markets(status="open")
    return [normalise_market(m) for m in raw_markets]


async def sync_user_predictions(user_id: str, kalshi_user_id: str) -> list[dict]:
    """Fetch a user's Kalshi trade history and return normalised predictions."""
    client = KalshiClient()
    raw_trades = await client.get_user_trades(kalshi_user_id)
    return [normalise_prediction(t, user_id) for t in raw_trades]
