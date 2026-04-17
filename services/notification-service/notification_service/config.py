"""
Configuration for notification-service.

All values are read from environment variables so the service can be
reconfigured without code changes. Sensible defaults are provided for
local development; production deployments should set every value
explicitly.
"""

from __future__ import annotations

import os


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


# ---------------------------------------------------------------------------
# Resend API
# ---------------------------------------------------------------------------

# Resend API key. If empty, the Resend client operates in "dry run" mode:
# it logs the outbound message and returns a fake message id instead of
# calling the API. This lets unit tests and dev environments exercise the
# full pipeline without credentials.
RESEND_API_KEY: str = _env("RESEND_API_KEY", "")

# From header. Both name and email must match a verified Resend sender.
RESEND_FROM_EMAIL: str = _env("RESEND_FROM_EMAIL", "noreply@tiresias.app")
RESEND_FROM_NAME: str = _env("RESEND_FROM_NAME", "Tiresias")


# ---------------------------------------------------------------------------
# Public app / unsubscribe URL
# ---------------------------------------------------------------------------

# Base URL used to build unsubscribe links (e.g. https://tiresias.app).
# The unsubscribe handler lives in auth-service at
# /auth/notifications/unsubscribe — we assume it's reachable under this
# base URL via api-gateway.
PUBLIC_APP_URL: str = _env("PUBLIC_APP_URL", "https://tiresias.app").rstrip("/")

# HMAC secret for unsubscribe JWT tokens. Shared with auth-service so the
# endpoint can verify the signature. Falls back to JWT_SECRET_KEY (the
# auth-service global secret) if dedicated secret is not configured.
UNSUBSCRIBE_TOKEN_SECRET: str = (
    _env("UNSUBSCRIBE_TOKEN_SECRET")
    or _env("JWT_SECRET_KEY")
    or "change-me-in-production"
)

# Unsubscribe tokens are long-lived — they need to stay valid for months
# after the email lands in an inbox.
UNSUBSCRIBE_TOKEN_EXPIRE_DAYS: int = int(_env("UNSUBSCRIBE_TOKEN_EXPIRE_DAYS", "365"))


def unsubscribe_url(token: str) -> str:
    """Build the public unsubscribe URL for a signed token."""
    return f"{PUBLIC_APP_URL}/auth/notifications/unsubscribe?token={token}"


def is_dry_run() -> bool:
    """True when no Resend API key is configured (dev/test mode)."""
    return not RESEND_API_KEY
