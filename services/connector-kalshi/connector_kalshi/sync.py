"""
Kalshi sync entrypoint.

Called by the scheduler. V1 scope:
  - Pull a user's fills (bets placed) and settlements (resolved outcomes).
  - Pull market metadata on-demand for each unique market in those fills.

Markets are stored separately from bets; the link is market_external_id.
"""

from __future__ import annotations

from .adapter import normalise_fill, normalise_market, normalise_settlement
from .client import KalshiClient


async def sync_user_fills(user_id: str) -> list[dict]:
    """Fetch the authenticated user's fill history and return normalised bets."""
    client = KalshiClient()
    raw_fills = await client.get_fills()
    return [normalise_fill(f, user_id) for f in raw_fills]


async def sync_user_settlements(user_id: str) -> list[dict]:
    """Fetch the authenticated user's settlement history (resolved bet outcomes)."""
    client = KalshiClient()
    raw_settlements = await client.get_settlements()
    return [normalise_settlement(s, user_id) for s in raw_settlements]


async def sync_market(ticker: str) -> dict:
    """
    Fetch metadata for a single market by ticker.

    Called after sync_user_fills to hydrate the unique markets referenced
    by those fills. Only fetches markets the user has actually bet on.
    """
    client = KalshiClient()
    raw = await client.get_market(ticker)
    return normalise_market(raw)
