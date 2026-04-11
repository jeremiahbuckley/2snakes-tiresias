"""
Polymarket sync entrypoint.

V1 scope:
  - Pull a user's trades and closed positions (by wallet address).
  - Pull market metadata on-demand for each unique market in those trades.

Markets are stored separately from trades; the link is market_external_id
(conditionId). Resolution outcome is embedded in the market record itself.

Note on market lookup:
  Trades and positions use conditionId as the market key, but the Gamma API's
  direct endpoint requires an integer id. sync_market() therefore accepts a
  slug (which is included in every trade/position record) and uses a slug-based
  Gamma query. Pass the slug from the trade/position, not the conditionId.
"""

from __future__ import annotations

from .adapter import normalise_closed_position, normalise_market, normalise_trade
from .client import PolymarketClient


async def sync_user_trades(user_id: str, wallet_address: str) -> list[dict]:
    """Fetch a user's Polymarket trade history and return normalised trades."""
    client = PolymarketClient()
    raw = await client.get_user_trades(wallet_address)
    return [normalise_trade(t, user_id) for t in raw]


async def sync_user_closed_positions(user_id: str, wallet_address: str) -> list[dict]:
    """
    Fetch a user's closed (resolved) positions and return normalised records.

    Equivalent to Kalshi settlements — one record per resolved market the user
    held a position in, with realizedPnl and the winning outcome.
    """
    client = PolymarketClient()
    raw = await client.get_closed_positions(wallet_address)
    return [normalise_closed_position(p, user_id) for p in raw]


async def sync_market(slug: str) -> dict | None:
    """
    Fetch metadata for a single market by slug.

    Called after sync_user_trades to hydrate the unique markets referenced
    by those trades. Pass the `slug` field from a trade or closed position
    record — do not pass the conditionId here.

    Returns None if the market is not found.
    """
    client = PolymarketClient()
    raw = await client.get_market_by_slug(slug)
    if raw is None:
        return None
    return normalise_market(raw)
