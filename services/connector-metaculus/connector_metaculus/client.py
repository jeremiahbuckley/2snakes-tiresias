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

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

METACULUS_API_BASE = os.environ.get("METACULUS_API_BASE", "https://www.metaculus.com")
METACULUS_TOKEN = os.environ.get("METACULUS_TOKEN", "")

# Page size for list requests. Metaculus allows up to 100.
_PAGE_LIMIT = 100


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
        """Return ALL posts where the given user has submitted a forecast.

        Auto-paginates using the `next` URL returned in each response envelope
        until there are no more pages. The response envelope contains:
            results  — current page of Post objects
            next     — absolute URL of the next page, or null when done
            count    — total number of matching posts across all pages

        Each returned Post's embedded question object includes `my_forecasts`
        (the authenticated user's full forecast history for that question)
        when the token owner is querying their own forecaster_id.

        Args:
            metaculus_user_id: Integer user ID on Metaculus (not username).
            **params: Additional query params forwarded to the API
                      (e.g. statuses=["resolved"], forecast_type=["binary"]).
        """
        all_results: list[dict] = []

        async with httpx.AsyncClient(headers=self._headers) as client:
            # First request — include forecaster_id and any extra params
            resp = await client.get(
                f"{self._base}/api/posts/",
                params={"forecaster_id": metaculus_user_id, "limit": _PAGE_LIMIT, **params},
            )
            resp.raise_for_status()
            body = resp.json()
            all_results.extend(body.get("results", []))

            total = body.get("count", 0)
            logger.debug(
                "Metaculus get_user_posts: fetched page 1, %d/%d posts",
                len(all_results),
                total,
            )

            # Follow `next` links until exhausted
            next_url: str | None = body.get("next")
            page = 2
            while next_url:
                resp = await client.get(next_url)
                resp.raise_for_status()
                body = resp.json()
                page_results = body.get("results", [])
                all_results.extend(page_results)
                logger.debug(
                    "Metaculus get_user_posts: fetched page %d, %d/%d posts",
                    page,
                    len(all_results),
                    total,
                )
                next_url = body.get("next")
                page += 1

        return all_results

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
