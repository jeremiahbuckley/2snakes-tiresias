"""
Metaculus API client (v2.0 OAS3).

Docs: https://www.metaculus.com/api/
Auth: ALL requests require a token — Authorization: Token <token>
      Generate one at https://www.metaculus.com/accounts/profile/ → API Access.

Key concepts:
- Posts are the top-level feed entity. Each post may contain:
    - question        → single question (binary, numeric, multiple_choice, date, …)
    - conditional     → if/then conditional pair
    - group_of_questions → grouped questions sharing a resolution variable
- V1 only handles posts with a single binary question.
- User forecasts are accessed via GET /api/posts/?forecaster_id=<id>.
  The question object embedded in each returned post includes `my_forecasts`
  (list of the authenticated user's forecast history on that question).

Rate limits: not documented explicitly; ~60 req/min is a safe default.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

METACULUS_API_BASE = os.environ.get("METACULUS_API_BASE", "https://www.metaculus.com")
METACULUS_TOKEN = os.environ.get("METACULUS_TOKEN", "")


class MetaculusClient:
    """Thin async wrapper around the Metaculus v2 REST API."""

    def __init__(self, token: str = METACULUS_TOKEN) -> None:
        self._base = METACULUS_API_BASE.rstrip("/")
        if not token:
            raise ValueError("METACULUS_TOKEN is required — all endpoints need auth")
        self._headers = {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
        }

    async def get_user_posts(
        self, metaculus_user_id: int, **params: Any
    ) -> list[dict]:
        """Return all posts where the given user has submitted a forecast.

        Metaculus uses offset/limit pagination. The response envelope contains
        `results` (current page) and `next` (URL of next page, or null).
        TODO: auto-paginate using the `next` link (see FUTURE_FEATURES.md).

        Args:
            metaculus_user_id: Integer user ID on Metaculus (not username).
            **params: Additional query params forwarded to the API
                      (e.g. statuses=["resolved"], forecast_type=["binary"]).
        """
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.get(
                f"{self._base}/api/posts/",
                params={"forecaster_id": metaculus_user_id, **params},
            )
            resp.raise_for_status()
            return resp.json().get("results", [])

    async def get_post(self, post_id: int) -> dict:
        """Return full post details including the embedded question.

        When authenticated, the question object includes a `my_forecasts` list
        containing the user's forecast history for that question, with the most
        recent entry last. For binary questions each entry has `probability_yes`.
        """
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.get(f"{self._base}/api/posts/{post_id}/")
            resp.raise_for_status()
            return resp.json()

    async def get_current_user(self) -> dict:
        """Return the authenticated user's profile (to resolve Metaculus user ID)."""
        async with httpx.AsyncClient(headers=self._headers) as client:
            resp = await client.get(f"{self._base}/api/users/me/")
            resp.raise_for_status()
            return resp.json()
