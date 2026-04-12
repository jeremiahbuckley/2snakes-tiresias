"""
Platform catalogue and credential-verification stubs for the auth service.

The canonical Platform / PlatformType enums live in data.models.linked_account
so all services share one definition.  This module re-exports them for
convenience and adds per-platform credential-verification helpers.
"""

from __future__ import annotations

# Re-export canonical enums so other auth-service modules only need one import.
from data.models.linked_account import (  # noqa: F401
    Platform,
    PlatformType,
    MARKET_PLATFORMS,
    SOCIAL_PLATFORMS,
    platform_type,
)


# ---------------------------------------------------------------------------
# Credential verification stubs
# ---------------------------------------------------------------------------
# Each function should make a lightweight authenticated call to the platform
# API to confirm the credential is valid before we store it.

def verify_kalshi_credential(api_key: str) -> bool:
    """
    Attempt a lightweight authenticated request to verify the Kalshi API key.
    Kalshi uses RSA-PSS signed requests; the key is the base64-encoded private key.
    TODO: implement using the connector-kalshi client.
    """
    raise NotImplementedError


def verify_polymarket_credential(wallet_address: str, message: str, signature: str) -> bool:
    """
    Verify an EIP-191 signature to prove ownership of a Polymarket wallet.
    TODO: implement using eth_account.messages / eth_account.Account.recover_message.
    """
    raise NotImplementedError


def verify_manifold_credential(api_key: str) -> bool:
    """Verify a Manifold API key by fetching GET /v0/me. TODO: implement."""
    raise NotImplementedError


def verify_metaculus_credential(token: str) -> bool:
    """Verify a Metaculus token by calling the API. TODO: implement."""
    raise NotImplementedError


def verify_x_credential(api_key: str, api_secret: str, access_token: str, access_secret: str) -> bool:
    """
    Verify X (Twitter) OAuth 1.0a credentials by calling GET /2/users/me.
    TODO: implement using tweepy or requests-oauthlib.
    """
    raise NotImplementedError


def verify_bluesky_credential(handle: str, app_password: str) -> bool:
    """
    Verify Bluesky credentials by calling com.atproto.server.createSession.
    TODO: implement using atproto SDK or direct HTTP call.
    """
    raise NotImplementedError


VERIFIERS = {
    Platform.KALSHI: verify_kalshi_credential,
    Platform.POLYMARKET: verify_polymarket_credential,
    Platform.MANIFOLD: verify_manifold_credential,
    Platform.METACULUS: verify_metaculus_credential,
    Platform.X: verify_x_credential,
    Platform.BLUESKY: verify_bluesky_credential,
}
