"""
Polymarket API client.

Polymarket uses two endpoints:
  - CLOB API (https://clob.polymarket.com) — order book, trade history
  - Gamma API (https://gamma-api.polymarket.com) — market metadata

Auth: API key + secret for private endpoints; public endpoints are open.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

CLOB_BASE = os.environ.get("POLYMARKET_CLOB_BASE", "https://clob.polymarket.com")
GAMMA_BASE = os.environ.get("POLYMARKET_GAMMA_BASE", "https://gamma-api.polymarket.com")
POLY_API_KEY = os.environ.get("POLYMARKET_API_KEY", "")


class PolymarketClient:
    """Thin async wrapper around the Polymarket CLOB and Gamma APIs."""

    def __init__(self, api_key: str = POLY_API_KEY) -> None:
        self._clob = CLOB_BASE.rstrip("/")
        self._gamma = GAMMA_BASE.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async def get_markets(self, **params: Any) -> list[dict]:
        """Return active markets from the Gamma API."""
        # TODO: pagination (next_cursor)
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._gamma}/markets", params=params)
            resp.raise_for_status()
            return resp.json()

    async def get_market(self, condition_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._gamma}/markets/{condition_id}")
            resp.raise_for_status()
            return resp.json()

    async def get_trades(self, maker_address: str, **params: Any) -> list[dict]:
        """Return trade history for a wallet address via the CLOB API."""
        # TODO: pagination
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.get(
                f"{self._clob}/data/trades",
                params={"maker_address": maker_address, **params},
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
