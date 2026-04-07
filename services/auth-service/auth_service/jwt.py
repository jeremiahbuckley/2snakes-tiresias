"""
JWT token creation and validation.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", 60))


def create_access_token(user_id: str, extra_claims: dict | None = None) -> str:
    """Issue a signed JWT for the given user."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        **(extra_claims or {}),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT. Raises jwt.ExpiredSignatureError or
    jwt.InvalidTokenError on failure.
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
