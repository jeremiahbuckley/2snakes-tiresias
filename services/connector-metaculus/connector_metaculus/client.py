"""
Metaculus API client.

Docs: https://www.metaculus.com/api2/
Auth: Token auth for write endpoints; GET endpoints are public.

Rate limits: ~100 requests/minute unauthenticated; higher with token.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

METACULUS_API_BASE = os.environ.get("METACULUS_API_BASE", "https://www.metaculus.com/api2")
METACULUS_TOKEN = os.environ.get("METACULUS_TOKEN", "")


class MetaculusClient:
    """Thin async wrapper around the Metaculus REST API."""

    def __init__(self, token: str = METACULUS_TOKEN) -> None:
        self._base = METACULUS_API_BASE.rstrip("/")
        self._headers = {"Authorization": f"Token {token}"} if token else {}

    async def get_questions(self, **params: Any) -> list[dict]:
        """Return a page of questions. Metaculus uses offset-based pagination."""
        # TODO: auto-paginate using 'next' link in response
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.get(f"{self._base}/questions/", params=params)
            resp.raise_for_status()
            return resp.json().get("results", [])

    async def get_question(self, question_id: int) -> dict:
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.get(f"{self._base}/questions/{question_id}/")
            resp.raise_for_status()
            return resp.json()

    async def get_user_predictions(self, user_id: int, **params: Any) -> list[dict]:
        """Return prediction history for a Metaculus user ID."""
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.get(
                f"{self._base}/predictions/",
                params={"author": user_id, **params},
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
