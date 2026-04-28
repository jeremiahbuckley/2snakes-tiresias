"""
Polymarket API client.

Polymarket has three separate APIs:

  Gamma API  https://gamma-api.polymarket.com   — market metadata, tags, events
  Data API   https://data-api.polymarket.com    — user trades, positions, activity
  CLOB API   https://clob.polymarket.com        — orderbook, pricing, order management

All three are fully public for read operations — no authentication required.
CLOB auth (L1 EIP-712 + L2 HMAC) is only needed for placing/cancelling orders,
which is out of scope for this project.

V1 usage:
  - Data API for user trade history and closed positions
  - Gamma API for per-market metadata

Note on market identifiers:
  Trades and positions reference markets by conditionId (0x-prefixed 64-hex string).
  The Gamma API's GET /markets/{id} endpoint takes an integer id, not conditionId.
  Trade objects include a `slug` field which can be used with GET /markets?slug=<slug>
  to retrieve full market metadata. sync_market() accepts a slug for this reason.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

GAMMA_BASE = os.environ.get("POLYMARKET_GAMMA_BASE", "https://gamma-api.polymarket.com")
DATA_BASE = os.environ.get("POLYMARKET_DATA_BASE", "https://data-api.polymarket.com")


class PolymarketClient:
    """Thin async wrapper around the Polymarket Gamma and Data APIs."""

    def __init__(
        self,
        gamma_base: str = GAMMA_BASE,
        data_base: str = DATA_BASE,
    ) -> None:
        self._gamma = gamma_base.rstrip("/")
        self._data = data_base.rstrip("/")

    # ------------------------------------------------------------------
    # Data API — user activity (all public, no auth)
    # ------------------------------------------------------------------

    async def get_user_trades(self, wallet_address: str, **params: Any) -> list[dict]:
        """
        Return all trades for a wallet address, paginating via offset.

        GET https://data-api.polymarket.com/trades?user=<address>

        Key params: limit (default 100, max 10000), offset, side (BUY|SELL),
                    takerOnly (bool, default true).
        Each trade includes: conditionId, side, price, size, outcome,
                             outcomeIndex, timestamp, title, slug.
        """
        limit = int(params.pop("limit", 100))
        all_trades: list[dict] = []
        offset = 0
        async with httpx.AsyncClient() as client:
            while True:
                resp = await client.get(
                    f"{self._data}/trades",
                    params={"user": wallet_address, "limit": limit, "offset": offset, **params},
                )
                resp.raise_for_status()
                page = resp.json()
                all_trades.extend(page)
                if len(page) < limit:
                    break
                offset += limit
        return all_trades

    async def get_closed_positions(self, wallet_address: str, **params: Any) -> list[dict]:
        """
        Return all closed (resolved) positions for a wallet address, paginating via offset.

        GET https://data-api.polymarket.com/closed-positions?user=<address>

        Equivalent to Kalshi settlements — shows final outcome and realizedPnl
        for each market the user held a position in when it resolved.

        Key params: limit (default 50, max 50), offset, sortBy (REALIZEDPNL etc).
        Each position includes: conditionId, outcome, realizedPnl, avgPrice,
                                totalBought, endDate, title, slug.
        """
        limit = int(params.pop("limit", 50))
        all_positions: list[dict] = []
        offset = 0
        async with httpx.AsyncClient() as client:
            while True:
                resp = await client.get(
                    f"{self._data}/closed-positions",
                    params={"user": wallet_address, "limit": limit, "offset": offset, **params},
                )
                resp.raise_for_status()
                page = resp.json()
                all_positions.extend(page)
                if len(page) < limit:
                    break
                offset += limit
        return all_positions

    async def get_open_positions(self, wallet_address: str, **params: Any) -> list[dict]:
        """
        Return all open positions for a wallet address, paginating via offset.

        GET https://data-api.polymarket.com/positions?user=<address>

        Key params: limit (default 500, max 500), offset.
        Each position includes: conditionId, size, avgPrice, currentValue,
                                cashPnl, outcome, title, slug.
        """
        limit = int(params.pop("limit", 500))
        all_positions: list[dict] = []
        offset = 0
        async with httpx.AsyncClient() as client:
            while True:
                resp = await client.get(
                    f"{self._data}/positions",
                    params={"user": wallet_address, "limit": limit, "offset": offset, **params},
                )
                resp.raise_for_status()
                page = resp.json()
                all_positions.extend(page)
                if len(page) < limit:
                    break
                offset += limit
        return all_positions

    # ------------------------------------------------------------------
    # Gamma API — market metadata (public, no auth)
    # ------------------------------------------------------------------

    async def get_market_by_slug(self, slug: str) -> dict | None:
        """
        Return full market metadata for a single market by slug.

        Uses GET /markets?slug=<slug> as a filtered list query, since trades
        return slug but the direct endpoint GET /markets/{id} requires the
        Gamma integer id (not the conditionId used by the Data API).

        Passes include_tag=true to embed tags in the response.
        Returns the first match, or None if not found.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._gamma}/markets",
                params={"slug": slug, "include_tag": "true"},
            )
            resp.raise_for_status()
            results = resp.json()
            if isinstance(results, list) and results:
                return results[0]
            return None

    async def get_market_by_id(self, gamma_id: int) -> dict:
        """
        Return full market metadata by Gamma integer id.

        Use this when you already have the integer id. For lookups from
        trade data (which provides slug/conditionId), use get_market_by_slug().
        """
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._gamma}/markets/{gamma_id}",
                params={"include_tag": "true"},
            )
            resp.raise_for_status()
            return resp.json()
