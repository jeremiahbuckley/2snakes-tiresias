"""
Manifold Markets sync entrypoint.

V1 scope:
  - Pull a user's bets.
  - Pull market metadata on-demand for each unique market in those bets.

Markets are stored separately from bets; the link is market_external_id.
Outcome data (resolution) is embedded in the market record itself.
"""

from __future__ import annotations

from .adapter import normalise_market, normalise_prediction
from .client import ManifoldClient


async def sync_user_bets(user_id: str, manifold_username: str) -> list[dict]:
    """Fetch a user's Manifold bet history and return normalised bets."""
    client = ManifoldClient()
    raw = await client.get_user_bets(manifold_username)
    return [normalise_prediction(b, user_id) for b in raw]


async def sync_market(market_id: str) -> dict:
    """
    Fetch metadata for a single market by ID.

    Called after sync_user_bets to hydrate the unique markets referenced
    by those bets. Only fetches markets the user has actually bet on.
    Resolution outcome (if any) is included in the market record.
    """
    client = ManifoldClient()
    raw = await client.get_market(market_id)
    return normalise_market(raw)
