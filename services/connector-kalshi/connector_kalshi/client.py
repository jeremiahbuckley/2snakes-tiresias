"""
Kalshi API client.

Docs: https://docs.kalshi.com/welcome
Auth: RSA-PSS request signing.

Every request must include three headers:
  KALSHI-ACCESS-KEY        — the Key ID from your Kalshi profile
  KALSHI-ACCESS-TIMESTAMP  — current time in milliseconds (string)
  KALSHI-ACCESS-SIGNATURE  — base64(RSA-PSS-SHA256(timestamp + METHOD + path))

The private key (PEM format) is generated on https://kalshi.com/account/profile
and stored locally. Its file path is supplied via KALSHI_PRIVATE_KEY_PATH.
The key is never stored by Kalshi after generation, so keep it safe.

Note: sign the path WITHOUT query parameters.
  e.g. /trade-api/v2/portfolio/orders  (not /trade-api/v2/portfolio/orders?limit=5)
"""

from __future__ import annotations

import base64
import datetime
import os
from typing import Any

import httpx
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

KALSHI_API_BASE = os.environ.get("KALSHI_API_BASE", "https://trading-api.kalshi.com/trade-api/v2")
KALSHI_KEY_ID = os.environ.get("KALSHI_KEY_ID", "")
KALSHI_PRIVATE_KEY_PATH = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")


def _load_private_key(path: str):
    """Load an RSA private key from a PEM file."""
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend(),
        )


def _sign_request(private_key, timestamp_ms: str, method: str, path: str) -> str:
    """
    Return a base64-encoded RSASSA-PSS-SHA256 signature.

    Signed payload: timestamp_ms + METHOD + path_without_query_params
    """
    path_without_query = path.split("?")[0]
    message = (timestamp_ms + method.upper() + path_without_query).encode("utf-8")
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def _auth_headers(private_key, method: str, path: str) -> dict[str, str]:
    """Build the three Kalshi auth headers for a single request."""
    timestamp_ms = str(int(datetime.datetime.now().timestamp() * 1000))
    return {
        "KALSHI-ACCESS-KEY": KALSHI_KEY_ID,
        "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
        "KALSHI-ACCESS-SIGNATURE": _sign_request(private_key, timestamp_ms, method, path),
        "Accept": "application/json",
    }


class KalshiClient:
    """Thin async wrapper around the Kalshi REST API."""

    def __init__(
        self,
        key_id: str = KALSHI_KEY_ID,
        private_key_path: str = KALSHI_PRIVATE_KEY_PATH,
        base_url: str = KALSHI_API_BASE,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._key_id = key_id
        self._private_key = _load_private_key(private_key_path)

    def _headers(self, method: str, path: str) -> dict[str, str]:
        """Generate fresh signed headers for each request."""
        timestamp_ms = str(int(datetime.datetime.now().timestamp() * 1000))
        return {
            "KALSHI-ACCESS-KEY": self._key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
            "KALSHI-ACCESS-SIGNATURE": _sign_request(
                self._private_key, timestamp_ms, method, path
            ),
            "Accept": "application/json",
        }

    async def get_markets(self, **params: Any) -> list[dict]:
        """Return a list of raw market objects from Kalshi."""
        # TODO: implement pagination (cursor-based)
        path = "/trade-api/v2/markets"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/markets",
                headers=self._headers("GET", path),
                params=params,
            )
            resp.raise_for_status()
            return resp.json().get("markets", [])

    async def get_market(self, ticker: str) -> dict:
        """Return a single raw market by ticker."""
        path = f"/trade-api/v2/markets/{ticker}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/markets/{ticker}",
                headers=self._headers("GET", path),
            )
            resp.raise_for_status()
            return resp.json().get("market", {})

    async def get_fills(self, **params: Any) -> list[dict]:
        """Return the authenticated user's fill history (bet executions)."""
        # TODO: implement pagination (cursor-based)
        path = "/trade-api/v2/portfolio/fills"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/portfolio/fills",
                headers=self._headers("GET", path),
                params=params,
            )
            resp.raise_for_status()
            return resp.json().get("fills", [])

    async def get_settlements(self, **params: Any) -> list[dict]:
        """Return the authenticated user's settlement history (resolved outcomes)."""
        # TODO: implement pagination (cursor-based)
        path = "/trade-api/v2/portfolio/settlements"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/portfolio/settlements",
                headers=self._headers("GET", path),
                params=params,
            )
            resp.raise_for_status()
            return resp.json().get("settlements", [])
