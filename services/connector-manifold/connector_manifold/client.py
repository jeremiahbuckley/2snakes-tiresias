"""
Manifold Markets API client.

Docs: https://docs.manifold.markets/api
Auth: API key passed as Authorization header. Public endpoints are open.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

MANIFOLD_API_BASE = os.environ.get("MANIFOLD_API_BASE", "https://api.manifold.markets/v0")
MANIFOLD_API_KEY = os.environ.get("MANIFOLD_API_KEY", "")


class ManifoldClient:
    """Thin async wrapper around the Manifold REST API."""

    def __init__(self, api_key: str = MANIFOLD_API_KEY) -> None:
        self._base = MANIFOLD_API_BASE.rstrip("/")
        self._headers = {"Authorization": f"Key {api_key}"} if api_key else {}

    async def get_markets(self, **params: Any) -> list[dict]:
        """Return all markets, paginating via the `before` cursor (last seen market ID)."""
        limit = int(params.pop("limit", 500))
        all_markets: list[dict] = []
        before: str | None = None
        async with httpx.AsyncClient() as client:
            while True:
                p = {**params, "limit": limit}
                if before:
                    p["before"] = before
                resp = await client.get(f"{self._base}/markets", params=p)
                resp.raise_for_status()
                page = resp.json()
                all_markets.extend(page)
                if len(page) < limit:
                    break
                before = page[-1]["id"]
        return all_markets

    async def get_market(self, market_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._base}/market/{market_id}")
            resp.raise_for_status()
            return resp.json()

    async def get_user_bets(self, username: str, **params: Any) -> list[dict]:
        """Return all bets for a Manifold username, paginating via the `before` cursor."""
        limit = int(params.pop("limit", 1000))
        all_bets: list[dict] = []
        before: str | None = None
        async with httpx.AsyncClient() as client:
            while True:
                p = {"username": username, "limit": limit, **params}
                if before:
                    p["before"] = before
                resp = await client.get(f"{self._base}/bets", params=p)
                resp.raise_for_status()
                page = resp.json()
                all_bets.extend(page)
                if len(page) < limit:
                    break
                before = page[-1]["id"]
        return all_bets
