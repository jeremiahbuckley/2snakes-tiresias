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
        """Return a list of markets (public)."""
        # TODO: pagination (before param)
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._base}/markets", params=params)
            resp.raise_for_status()
            return resp.json()

    async def get_market(self, market_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._base}/market/{market_id}")
            resp.raise_for_status()
            return resp.json()

    async def get_user_bets(self, username: str, **params: Any) -> list[dict]:
        """Return bet history for a Manifold username."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base}/bets",
                params={"username": username, **params},
            )
            resp.raise_for_status()
            return resp.json()
