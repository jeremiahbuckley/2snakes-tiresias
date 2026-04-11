"""
Manifold Markets sync entrypoint.

V1 scope:
  - Pull a user's bets.
  - Pull market metadata on-demand for each unique market in those bets.

Markets are stored separately from bets; the link is market_external_id
(Manifold's contractId). Resolution outcome is embedded in the market record.

Note on isRedemption bets:
  Manifold automatically inserts redemption bets during resolution (e.g. to
  cancel paired YES/NO shares). These are not user decisions and should not be
  scored. sync_user_bets filters them out before returning.
"""

from __future__ import annotations

from .adapter import normalise_bet, normalise_market
from .client import ManifoldClient


async def sync_user_bets(user_id: str, manifold_username: str) -> list[dict]:
    """Fetch a user's Manifold bet history and return normalised bets.

    Redemption bets (isRedemption == True) are excluded — they are automated
    resolution events, not user-placed predictions.
    """
    client = ManifoldClient()
    raw = await client.get_user_bets(manifold_username)
    return [
        normalise_bet(b, user_id)
        for b in raw
        if not b.get("isRedemption", False)
    ]


async def sync_market(market_id: str) -> dict:
    """
    Fetch metadata for a single market by ID.

    Called after sync_user_bets to hydrate the unique markets referenced by
    those bets. Only fetches markets the user has actually bet on. Resolution
    outcome (if any) is included in the returned market record.
    """
    client = ManifoldClient()
    raw = await client.get_market(market_id)
    return normalise_market(raw)
