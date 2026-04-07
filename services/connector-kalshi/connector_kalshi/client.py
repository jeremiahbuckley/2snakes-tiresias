"""
Kalshi API client.

Docs: https://trading-api.readme.io/reference/getting-started
Auth: API key passed as header KALSHI-ACCESS-KEY.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

KALSHI_API_BASE = os.environ.get("KALSHI_API_BASE", "https://trading-api.kalshi.com/trade-api/v2")
KALSHI_API_KEY = os.environ.get("KALSHI_API_KEY", "")


class KalshiClient:
    """Thin async wrapper around the Kalshi REST API."""

    def __init__(self, api_key: str = KALSHI_API_KEY, base_url: str = KALSHI_API_BASE) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "KALSHI-ACCESS-KEY": api_key,
            "Accept": "application/json",
        }

    async def get_markets(self, **params: Any) -> list[dict]:
        """Return a list of raw market objects from Kalshi."""
        # TODO: implement pagination (cursor-based)
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.get(f"{self._base_url}/markets", params=params)
            resp.raise_for_status()
            return resp.json().get("markets", [])

    async def get_market(self, ticker: str) -> dict:
        """Return a single raw market by ticker."""
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.get(f"{self._base_url}/markets/{ticker}")
            resp.raise_for_status()
            return resp.json().get("market", {})

    async def get_user_trades(self, user_id: str, **params: Any) -> list[dict]:
        """Return raw trade history for a user."""
        # TODO: implement pagination
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.get(f"{self._base_url}/portfolio/trades", params=params)
            resp.raise_for_status()
            return resp.json().get("trades", [])
