"""Tests for the unsubscribe token helpers."""

from __future__ import annotations

import time
from unittest.mock import patch

import jwt
import pytest

from notification_service import config, unsubscribe


def test_issue_and_decode_roundtrip():
    user_id = "11111111-2222-3333-4444-555555555555"
    token = unsubscribe.issue_token(user_id, "email_on_resolution")

    claims = unsubscribe.decode_token(token)
    assert claims["sub"] == user_id
    assert claims["pref"] == "email_on_resolution"
    assert claims["typ"] == "unsubscribe"
    assert "exp" in claims and "iat" in claims


def test_decode_rejects_tokens_signed_with_wrong_secret():
    other_token = jwt.encode(
        {"sub": "x", "pref": "email_on_resolution", "typ": "unsubscribe"},
        "some-other-secret",
        algorithm="HS256",
    )
    with pytest.raises(jwt.InvalidTokenError):
        unsubscribe.decode_token(other_token)


def test_decode_rejects_wrong_typ_claim():
    token = jwt.encode(
        {"sub": "x", "pref": "email_on_resolution", "typ": "access"},
        config.UNSUBSCRIBE_TOKEN_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(jwt.InvalidTokenError):
        unsubscribe.decode_token(token)


def test_decode_rejects_unknown_pref_field():
    token = jwt.encode(
        {"sub": "x", "pref": "email_on_something_else", "typ": "unsubscribe"},
        config.UNSUBSCRIBE_TOKEN_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(jwt.InvalidTokenError):
        unsubscribe.decode_token(token)


def test_decode_rejects_expired_tokens():
    past_payload = {
        "sub": "x",
        "pref": "email_on_resolution",
        "typ": "unsubscribe",
        "iat": int(time.time()) - 3600,
        "exp": int(time.time()) - 600,
    }
    token = jwt.encode(
        past_payload, config.UNSUBSCRIBE_TOKEN_SECRET, algorithm="HS256"
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        unsubscribe.decode_token(token)


def test_pref_field_for_event_mapping():
    assert unsubscribe.pref_field_for_event("market_resolved") == "email_on_resolution"
    assert unsubscribe.pref_field_for_event("badge_earned") == "email_on_badge"
    assert unsubscribe.pref_field_for_event("rank_change") == "email_on_rank_change"


def test_pref_field_for_unknown_event_raises():
    with pytest.raises(ValueError):
        unsubscribe.pref_field_for_event("weekly_digest")


def test_unsubscribe_url_for_event_includes_token_and_base_url():
    url = unsubscribe.unsubscribe_url_for_event(
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "badge_earned"
    )
    assert url.startswith(config.PUBLIC_APP_URL)
    assert "token=" in url
    # The token itself should decode cleanly.
    token = url.split("token=", 1)[1]
    claims = unsubscribe.decode_token(token)
    assert claims["pref"] == "email_on_badge"
