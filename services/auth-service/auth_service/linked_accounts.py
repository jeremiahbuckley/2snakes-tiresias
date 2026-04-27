"""
Platform catalogue and credential-verification helpers for the auth service.

The canonical Platform / PlatformType enums live in data.models.linked_account
so all services share one definition.  This module re-exports them for
convenience and adds per-platform credential-verification helpers.

Verifier contract
-----------------
All verifiers are `async` and return ``bool``:
  * ``True``  — the credential is valid
  * ``False`` — the credential is syntactically parseable but rejected by
                the platform (HTTP 401/403, signature mismatch, etc.)

Verifiers raise on *unexpected* errors (network failures, DNS issues,
unparseable input, 5xx responses, library misuse). Callers are expected to
treat "could not tell" differently from "definitely invalid".

Social verifiers (X, Bluesky) are intentionally left as stubs — they're
tracked under "Auth & Account Linking" in FUTURE_FEATURES.md.
"""

from __future__ import annotations

import base64
import datetime
import logging
from typing import Awaitable, Callable, Union

import httpx

# Re-export canonical enums so other auth-service modules only need one import.
from data.models.linked_account import (  # noqa: F401
    Platform,
    PlatformType,
    MARKET_PLATFORMS,
    SOCIAL_PLATFORMS,
    platform_type,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Kalshi — RSA-PSS signed request against a lightweight authenticated endpoint
# ---------------------------------------------------------------------------

# Base URL for Kalshi verification calls. Mirrors connector_kalshi.client.KALSHI_API_BASE
# but we don't import it to avoid pulling the connector as a hard dependency of
# the auth service.
_KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"
_KALSHI_VERIFY_PATH = "/trade-api/v2/portfolio/fills"


async def verify_kalshi_credential(key_id: str, private_key_pem: Union[str, bytes]) -> bool:
    """
    Verify a Kalshi credential pair by signing and making one authenticated request.

    Kalshi auth headers are:
      KALSHI-ACCESS-KEY        — the Key ID from the user's Kalshi profile
      KALSHI-ACCESS-TIMESTAMP  — current time in milliseconds
      KALSHI-ACCESS-SIGNATURE  — base64(RSA-PSS-SHA256(timestamp + METHOD + path))

    Args:
        key_id: The Kalshi Key ID (stored as LinkedAccount.external_identifier).
        private_key_pem: The RSA private key in PEM format, either as a string
                         or bytes.

    Returns:
        True  — credentials accepted by Kalshi.
        False — server returned 401 or 403 (invalid key_id, bad signature,
                revoked key).

    Raises:
        ValueError  — key_id is empty, or the PEM cannot be parsed.
        httpx.HTTPError — network or 5xx failure (couldn't reach Kalshi).
    """
    if not key_id:
        raise ValueError("Kalshi key_id is required")

    # Lazy import so the auth service doesn't hard-require `cryptography` at
    # module-load time. (It's listed in requirements.txt, but this keeps the
    # import graph minimal for tests that don't exercise Kalshi.)
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    pem_bytes = private_key_pem.encode() if isinstance(private_key_pem, str) else private_key_pem
    try:
        private_key = serialization.load_pem_private_key(
            pem_bytes, password=None, backend=default_backend()
        )
    except Exception as exc:  # unparseable PEM is a caller error, not a credential-invalid signal
        raise ValueError(f"Could not parse Kalshi private key PEM: {exc}") from exc

    timestamp_ms = str(int(datetime.datetime.now().timestamp() * 1000))
    message = (timestamp_ms + "GET" + _KALSHI_VERIFY_PATH).encode("utf-8")
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )

    headers = {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("utf-8"),
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{_KALSHI_API_BASE}/portfolio/fills",
            headers=headers,
            params={"limit": 1},
        )

    if resp.status_code == 200:
        return True
    if resp.status_code in (401, 403):
        logger.info("Kalshi verification failed for key_id=%s: %s", key_id, resp.status_code)
        return False

    # Anything else (500s, 429, unexpected) — propagate so callers know we
    # couldn't actually tell.
    resp.raise_for_status()
    # raise_for_status() is a no-op for 2xx/3xx; if we somehow reach here
    # with a non-standard success code, treat it as unverifiable.
    raise httpx.HTTPStatusError(
        f"Unexpected Kalshi response: {resp.status_code}",
        request=resp.request,
        response=resp,
    )


# ---------------------------------------------------------------------------
# Polymarket — EIP-191 signature verification (no network call)
# ---------------------------------------------------------------------------

async def verify_polymarket_credential(
    wallet_address: str, message: str, signature: str
) -> bool:
    """
    Verify an EIP-191 (``personal_sign``) signature proves ownership of a wallet.

    The user signs ``message`` client-side with their wallet; we recover the
    signing address from the signature and compare to the claimed wallet.

    Args:
        wallet_address: Claimed wallet address (0x-prefixed, 42 chars).
        message:        The exact string the user signed.
        signature:      Hex-encoded signature (0x-prefixed, 132 chars).

    Returns:
        True  — recovered address matches wallet_address (case-insensitive).
        False — recovered address does not match.

    Raises:
        ValueError — inputs malformed (bad address, bad hex, wrong length).
    """
    if not wallet_address or not message or not signature:
        raise ValueError("wallet_address, message, and signature are all required")

    # Lazy import — eth_account is a heavyweight dep; only pulled in on use.
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ImportError as exc:  # pragma: no cover — dep missing is a deploy error
        raise ImportError(
            "eth-account is required for Polymarket verification. "
            "Add `eth-account>=0.11.0` to requirements.txt."
        ) from exc

    try:
        signable = encode_defunct(text=message)
        recovered = Account.recover_message(signable, signature=signature)
    except Exception as exc:
        # Malformed signature/address — treat as caller error, not invalid credential.
        raise ValueError(f"Could not recover signer from Polymarket signature: {exc}") from exc

    match = recovered.lower() == wallet_address.lower()
    if not match:
        logger.info(
            "Polymarket verification failed: recovered=%s expected=%s",
            recovered,
            wallet_address,
        )
    return match


# ---------------------------------------------------------------------------
# Manifold — authenticated GET /v0/me
# ---------------------------------------------------------------------------

_MANIFOLD_API_BASE = "https://api.manifold.markets/v0"


async def verify_manifold_credential(api_key: str) -> bool:
    """
    Verify a Manifold API key by fetching the authenticated user's profile.

    GET /v0/me returns 200 with the user object on success, 401 on bad key.
    """
    if not api_key:
        raise ValueError("Manifold api_key is required")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{_MANIFOLD_API_BASE}/me",
            headers={"Authorization": f"Key {api_key}"},
        )

    if resp.status_code == 200:
        return True
    if resp.status_code in (401, 403):
        logger.info("Manifold verification failed: %s", resp.status_code)
        return False

    resp.raise_for_status()
    raise httpx.HTTPStatusError(
        f"Unexpected Manifold response: {resp.status_code}",
        request=resp.request,
        response=resp,
    )


# ---------------------------------------------------------------------------
# Metaculus — authenticated GET /api/users/me/
# ---------------------------------------------------------------------------

_METACULUS_API_BASE = "https://www.metaculus.com"


async def verify_metaculus_credential(token: str) -> bool:
    """
    Verify a Metaculus API token by fetching /api/users/me/.

    Metaculus uses Token auth: ``Authorization: Token <token>``.
    Returns 200 on success, 401 on bad token.
    """
    if not token:
        raise ValueError("Metaculus token is required")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{_METACULUS_API_BASE}/api/users/me/",
            headers={"Authorization": f"Token {token}"},
        )

    if resp.status_code == 200:
        return True
    if resp.status_code in (401, 403):
        logger.info("Metaculus verification failed: %s", resp.status_code)
        return False

    resp.raise_for_status()
    raise httpx.HTTPStatusError(
        f"Unexpected Metaculus response: {resp.status_code}",
        request=resp.request,
        response=resp,
    )


# ---------------------------------------------------------------------------
# Metaculus — resolve username to numeric user ID
# ---------------------------------------------------------------------------

async def resolve_metaculus_external_identifier(token: str) -> str:
    """
    Return the authenticated user's numeric Metaculus user ID as a string.

    Calling /api/users/me/ with the user's token returns their profile, which
    includes their integer ``id``. We store this as ``external_identifier``
    rather than whatever the user typed (often a username), because
    ``_sync_metaculus`` in the scheduler needs the numeric ID to query forecasts.

    Raises:
        httpx.HTTPError — network failure or unexpected response.
        KeyError        — response did not contain an ``id`` field.
        ValueError      — token is empty.
    """
    if not token:
        raise ValueError("Metaculus token is required")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{_METACULUS_API_BASE}/api/users/me/",
            headers={"Authorization": f"Token {token}"},
        )
        resp.raise_for_status()
        return str(resp.json()["id"])


# ---------------------------------------------------------------------------
# Social platforms — still stubs. Tracked in FUTURE_FEATURES.md.
# ---------------------------------------------------------------------------

async def verify_x_credential(
    api_key: str, api_secret: str, access_token: str, access_secret: str
) -> bool:
    """
    Verify X (Twitter) OAuth 1.0a credentials by calling GET /2/users/me.

    NOT YET IMPLEMENTED. Social publishing is deferred — see FUTURE_FEATURES.md.
    """
    raise NotImplementedError("X credential verification is deferred — see FUTURE_FEATURES.md")


async def verify_bluesky_credential(handle: str, app_password: str) -> bool:
    """
    Verify Bluesky credentials by calling com.atproto.server.createSession.

    NOT YET IMPLEMENTED. Social publishing is deferred — see FUTURE_FEATURES.md.
    """
    raise NotImplementedError(
        "Bluesky credential verification is deferred — see FUTURE_FEATURES.md"
    )


# ---------------------------------------------------------------------------
# Registry — maps platform → verifier callable
# ---------------------------------------------------------------------------
#
# Signatures differ per platform (Kalshi takes 2 args, Polymarket 3, the
# others 1), so the registry is typed as a generic async callable. Call-sites
# that use it must pass the right arguments for the specific platform.

VerifierFn = Callable[..., Awaitable[bool]]

VERIFIERS: dict[Platform, VerifierFn] = {
    Platform.KALSHI: verify_kalshi_credential,
    Platform.POLYMARKET: verify_polymarket_credential,
    Platform.MANIFOLD: verify_manifold_credential,
    Platform.METACULUS: verify_metaculus_credential,
    Platform.X: verify_x_credential,
    Platform.BLUESKY: verify_bluesky_credential,
}


# ---------------------------------------------------------------------------
# Platforms we skip verification for in the unified upsert flow
# ---------------------------------------------------------------------------
# - X / Bluesky: verifiers are still stubs (raise NotImplementedError).

VERIFICATION_SKIPPED: frozenset[Platform] = frozenset(
    {Platform.POLYMARKET, Platform.X, Platform.BLUESKY}
)


async def verify_upsert_credential(
    platform: Platform, external_identifier: str, credential: str | None, *, message: str | None = None
) -> bool | None:
    """
    Unified dispatch used by ``upsert_linked_account``.

    Returns:
        True   — verified OK.
        False  — platform rejected the credential (credentials are invalid).
        None   — verification skipped (platform in VERIFICATION_SKIPPED, or
                 unexpected error reached the verifier — see contract).

    Raises:
        httpx.HTTPError — network / upstream 5xx. Caller may treat this as
                          "accept but mark unverified" to avoid blocking on
                          upstream outages.
        ValueError      — malformed input (empty required field, bad PEM).

    Per-platform argument mapping:
        Kalshi     → (external_identifier=key_id, credential=PEM)
        Manifold   → (credential=api_key)
        Metaculus  → (credential=token)
        Polymarket → skipped (public API, wallet address only)
        X/Bluesky  → skipped (stubs)
    """
    if platform in VERIFICATION_SKIPPED:
        return None

    if platform is Platform.KALSHI:
        return await verify_kalshi_credential(external_identifier, credential)
    if platform is Platform.MANIFOLD:
        return await verify_manifold_credential(credential)
    if platform is Platform.METACULUS:
        return await verify_metaculus_credential(credential)

    logger.warning("No upsert-verifier mapping for platform=%s; skipping", platform)
    return None
