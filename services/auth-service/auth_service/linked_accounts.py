"""
Linked external account management.

Stores per-user credentials for each prediction market platform.
Credentials are encrypted at rest (TODO: implement encryption).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Platform(StrEnum):
    KALSHI = "kalshi"
    POLYMARKET = "polymarket"
    MANIFOLD = "manifold"
    METACULUS = "metaculus"


@dataclass
class LinkedAccount:
    user_id: str
    platform: Platform
    external_identifier: str   # username, wallet address, or user ID
    credential: str            # API key, token, etc. — encrypt before storing
    verified: bool = False


def verify_kalshi_credential(api_key: str) -> bool:
    """
    Attempt a lightweight authenticated request to verify the Kalshi API key.
    TODO: implement.
    """
    raise NotImplementedError


def verify_polymarket_signature(wallet_address: str, message: str, signature: str) -> bool:
    """
    Verify an EIP-191 signature to prove ownership of a Polymarket wallet.
    TODO: implement using eth_account.
    """
    raise NotImplementedError


def verify_manifold_credential(api_key: str) -> bool:
    """Verify a Manifold API key by fetching /v0/me. TODO: implement."""
    raise NotImplementedError


def verify_metaculus_token(token: str) -> bool:
    """Verify a Metaculus token by calling the API. TODO: implement."""
    raise NotImplementedError
