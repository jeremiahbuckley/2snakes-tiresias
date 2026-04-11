"""
Polymarket sync entrypoint.

V1 scope:
  - Pull a user's trades (by wallet address).
  - Pull market metadata on-demand for each unique market in those trades.

Markets are stored separately from trades; the link is market_external_id.
Resolution outcome (if any) is embedded in the market record itself.
"""

from __future__ import annotations

from .adapter import normalise_market, normalise_prediction
from .client import PolymarketClient


async def sync_user_trades(user_id: str, wallet_address: str) -> list[dict]:
    """Fetch a user's Polymarket trade history and return normalised bets."""
    client = PolymarketClient()
    raw = await client.get_trades(wallet_address)
    return [normalise_prediction(t, user_id) for t in raw]


async def sync_market(condition_id: str) -> dict:
    """
    Fetch metadata for a single market by condition ID.

    Called after sync_user_trades to hydrate the unique markets referenced
    by those trades. Only fetches markets the user has actually traded in.
    Resolution outcome (if any) is included in the market record.
    """
    client = PolymarketClient()
    raw = await client.get_market(condition_id)
    return normalise_market(raw)
